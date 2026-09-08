import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.watcher import DatabaseEventFilter, DatabaseWatcher, DebouncedSync


def event(path, dest=None, is_directory=False):
    return SimpleNamespace(
        src_path=str(path),
        dest_path=str(dest) if dest else "",
        is_directory=is_directory,
    )


@pytest.mark.parametrize("method", ["on_modified", "on_created", "on_deleted"])
def test_filter_accepts_database_wal_and_shm_for_each_event_type(tmp_path, method):
    database = tmp_path / "main.sqlite"
    notify = Mock()
    handler = DatabaseEventFilter(database, notify)

    for suffix in ("", "-wal", "-shm"):
        getattr(handler, method)(event(Path(f"{database}{suffix}")))

    assert notify.call_count == 3


def test_filter_accepts_moved_source_or_destination_and_normalizes_paths(tmp_path):
    database = tmp_path / "main.sqlite"
    notify = Mock()
    handler = DatabaseEventFilter(database, notify)

    handler.on_moved(event(database, tmp_path / "elsewhere"))
    handler.on_moved(event(tmp_path / "elsewhere", database / "../main.sqlite-wal"))

    assert notify.call_count == 2


def test_filter_ignores_unrelated_and_directory_events(tmp_path):
    notify = Mock()
    handler = DatabaseEventFilter(tmp_path / "main.sqlite", notify)

    handler.on_modified(event(tmp_path / "other.sqlite"))
    handler.on_created(event(tmp_path, is_directory=True))
    handler.on_moved(event(tmp_path / "main.sqlite", tmp_path / "other", True))

    assert notify.call_count == 0


class FakeTimer:
    instances = []

    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.started = False
        self.cancelled = False
        type(self).instances.append(self)

    @property
    def daemon(self):
        return getattr(self, "_daemon", None)

    @daemon.setter
    def daemon(self, value):
        self._daemon = value

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.callback()

    @classmethod
    def reset(cls):
        cls.instances.clear()


@pytest.fixture
def timers():
    FakeTimer.reset()
    yield FakeTimer
    FakeTimer.reset()


def test_debounce_uses_trailing_edge_timer(timers):
    request = Mock(return_value=True)
    debounce = DebouncedSync(request, 2.0, timer_factory=timers)

    debounce.notify()
    first = timers.instances[-1]
    debounce.notify()
    second = timers.instances[-1]
    debounce.notify()
    third = timers.instances[-1]

    assert [timer.cancelled for timer in (first, second, third)] == [True, True, False]
    assert third.delay == 2.0
    assert all(timer.daemon for timer in timers.instances)
    third.fire()
    request.assert_called_once_with()
    assert not debounce._pending


def test_notification_during_request_schedules_one_later_timer(timers):
    entered = threading.Event()
    release = threading.Event()
    request = Mock(side_effect=lambda: (entered.set(), release.wait(2), True)[-1])
    debounce = DebouncedSync(request, 1.0, timer_factory=timers)
    debounce.notify()
    worker = threading.Thread(target=timers.instances[-1].fire)
    worker.start()
    assert entered.wait(1)

    debounce.notify()
    assert len(timers.instances) == 1
    release.set()
    worker.join(1)

    assert not worker.is_alive()
    assert len(timers.instances) == 2
    assert not timers.instances[1].cancelled
    timers.instances[1].fire()
    assert request.call_count == 2


def test_false_request_schedules_at_most_one_retry_per_notification_cycle(timers):
    request = Mock(return_value=False)
    debounce = DebouncedSync(request, 1.0, timer_factory=timers)
    debounce.notify()
    timers.instances[0].fire()

    assert request.call_count == 1
    assert len(timers.instances) == 2
    timers.instances[1].fire()
    assert request.call_count == 2
    assert len(timers.instances) == 2

    debounce.notify()
    assert len(timers.instances) == 3
    timers.instances[2].fire()
    assert request.call_count == 3
    assert len(timers.instances) == 4


def test_callback_exception_is_logged_without_exception_details(timers, caplog):
    secret = "password=supersecret"
    request = Mock(side_effect=RuntimeError(secret))
    debounce = DebouncedSync(request, 1.0, timer_factory=timers)
    debounce.notify()
    with caplog.at_level("ERROR"):
        timers.instances[0].fire()

    assert caplog.records[-1].getMessage() == "Debounced sync request failed"
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert caplog.records[-1].exc_info is None

    debounce.notify()
    timers.instances[-1].fire()
    assert request.call_count == 2


def test_stop_cancels_timer_rejects_notifications_and_waits_for_callback(timers):
    entered = threading.Event()
    release = threading.Event()

    def request():
        entered.set()
        release.wait(2)
        return True

    debounce = DebouncedSync(request, 1.0, timer_factory=timers)
    debounce.notify()
    pending = timers.instances[0]
    debounce.stop()
    assert pending.cancelled
    debounce.notify()
    assert len(timers.instances) == 1

    # A callback already executing is allowed to finish before stop returns.
    debounce = DebouncedSync(request, 1.0, timer_factory=timers)
    debounce.notify()
    worker = threading.Thread(target=timers.instances[-1].fire)
    worker.start()
    assert entered.wait(1)
    stopped = threading.Event()
    stopper = threading.Thread(target=lambda: (debounce.stop(), stopped.set()))
    stopper.start()
    assert not stopped.wait(0.05)
    release.set()
    stopper.join(1)
    worker.join(1)
    assert stopped.is_set()


def test_stale_cancelled_timer_callback_does_not_run_request(timers):
    request = Mock(return_value=True)
    debounce = DebouncedSync(request, 1.0, timer_factory=timers)

    debounce.notify()
    stale = timers.instances[0]
    debounce.notify()
    current = timers.instances[1]

    stale.fire()
    request.assert_not_called()
    current.fire()
    request.assert_called_once_with()


def test_stop_without_wait_returns_while_callback_is_running(timers):
    entered = threading.Event()
    release = threading.Event()

    def request():
        entered.set()
        release.wait(2)
        return True

    debounce = DebouncedSync(request, 1.0, timer_factory=timers)
    debounce.notify()
    worker = threading.Thread(target=timers.instances[0].fire)
    worker.start()
    assert entered.wait(1)

    debounce.stop(wait=False)
    assert worker.is_alive()
    release.set()
    worker.join(1)
    assert not worker.is_alive()


def test_callback_can_stop_debouncer_without_deadlocking(timers):
    holder = {}
    stopped = threading.Event()

    def request():
        holder["debounce"].stop()
        stopped.set()
        return True

    debounce = DebouncedSync(request, 1.0, timer_factory=timers)
    holder["debounce"] = debounce
    debounce.notify()
    worker = threading.Thread(target=timers.instances[0].fire)
    worker.start()
    worker.join(1)

    assert stopped.is_set()
    assert not worker.is_alive()
    debounce.notify()
    assert len(timers.instances) == 1


def test_delay_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        DebouncedSync(Mock(), 0)
    with pytest.raises(ValueError, match="positive"):
        DebouncedSync(Mock(), -1)


class FakeObserver:
    def __init__(self, alive=False):
        self.alive = alive
        self.scheduled = []
        self.started = False
        self.stopped = False
        self.join_timeouts = []

    def schedule(self, handler, path, recursive):
        self.scheduled.append((handler, path, recursive))

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def join(self, timeout=None):
        self.join_timeouts.append(timeout)

    def is_alive(self):
        return self.alive


def test_watcher_observer_lifecycle_is_idempotent(tmp_path):
    database = tmp_path / "main.sqlite"
    debounce = Mock()
    observer = FakeObserver()
    factory = Mock(return_value=observer)
    watcher = DatabaseWatcher(database, debounce, observer_factory=factory)

    watcher.stop()
    watcher.start()
    watcher.start()
    watcher.stop()
    watcher.stop()

    assert factory.call_count == 1
    assert observer.started
    assert observer.stopped
    assert observer.join_timeouts == [10]
    assert len(observer.scheduled) == 1
    handler, path, recursive = observer.scheduled[0]
    assert path == str(tmp_path)
    assert recursive is False
    handler.on_modified(event(database))
    debounce.notify.assert_called_once_with()


def test_watcher_requires_existing_database_parent(tmp_path):
    observer_factory = Mock()
    watcher = DatabaseWatcher(
        tmp_path / "missing" / "main.sqlite", Mock(), observer_factory=observer_factory
    )

    with pytest.raises(FileNotFoundError, match="Database directory"):
        watcher.start()
    observer_factory.assert_not_called()


def test_watcher_rejects_regular_file_as_database_parent(tmp_path):
    parent = tmp_path / "not-a-directory"
    parent.write_text("not a directory")
    observer_factory = Mock()
    watcher = DatabaseWatcher(parent / "main.sqlite", Mock(), observer_factory=observer_factory)

    with pytest.raises(FileNotFoundError, match="Database directory"):
        watcher.start()
    observer_factory.assert_not_called()


def test_watcher_cleans_up_observer_when_start_fails(tmp_path):
    startup_error = RuntimeError("observer startup failed")
    observer = Mock()
    observer.start.side_effect = startup_error
    observer.is_alive.return_value = False
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)

    with pytest.raises(RuntimeError, match="observer startup failed") as raised:
        watcher.start()

    assert raised.value is startup_error
    observer.stop.assert_called_once_with()
    observer.join.assert_called_once_with(timeout=10)


def test_watcher_startup_cleanup_logs_fixed_messages_without_exception_details(tmp_path, caplog):
    secret = "password=SECRET database=/private/TARGET/main.sqlite"
    observer = Mock()
    observer.start.side_effect = RuntimeError(secret)
    observer.stop.side_effect = OSError(secret)
    observer.join.side_effect = OSError(secret)
    observer.is_alive.return_value = False
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)

    with caplog.at_level("ERROR"), pytest.raises(RuntimeError):
        watcher.start()

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "Failed to stop database watcher after startup failure",
        "Failed to join database watcher after startup failure",
    ]
    assert secret not in caplog.text
    assert "/private/TARGET/main.sqlite" not in caplog.text
    assert "Traceback" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_watcher_stop_logs_fixed_messages_without_exception_details(tmp_path, caplog):
    secret = "password=SECRET database=/private/TARGET/main.sqlite"
    observer = FakeObserver()
    observer.stop = Mock(side_effect=OSError(secret))
    observer.join = Mock(side_effect=OSError(secret))
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)
    watcher.start()

    with caplog.at_level("ERROR"), pytest.raises(OSError):
        watcher.stop()

    messages = [record.getMessage() for record in caplog.records]
    assert messages == ["Failed to stop database watcher", "Failed to join database watcher"]
    assert secret not in caplog.text
    assert "/private/TARGET/main.sqlite" not in caplog.text
    assert "Traceback" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
def test_watcher_retries_cleanup_when_observer_remains_alive_after_start_failure(tmp_path):
    startup_error = RuntimeError("observer startup failed")
    observer = Mock()
    observer.start.side_effect = startup_error
    observer.is_alive.side_effect = [True, False]
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)

    with pytest.raises(RuntimeError, match="observer startup failed"):
        watcher.start()

    assert watcher._observer is observer
    assert watcher._started
    assert watcher._observer_start_attempted
    watcher.stop()
    assert observer.stop.call_count == 2
    assert observer.join.call_count == 2
    assert watcher._observer is None
    assert not watcher._started
    assert not watcher._observer_start_attempted


def test_watcher_start_registration_boundary_blocks_stop(tmp_path, monkeypatch):
    registration_entered = threading.Event()
    release_registration = threading.Event()
    original_is_dir = Path.is_dir

    def paused_is_dir(path):
        if path == tmp_path:
            registration_entered.set()
            assert release_registration.wait(2)
        return original_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", paused_is_dir)
    observer = FakeObserver()
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)
    start_errors = []
    stop_finished = threading.Event()

    starter = threading.Thread(target=lambda: _call_and_record(watcher.start, start_errors))
    starter.start()
    assert registration_entered.wait(1)
    stopper = threading.Thread(target=lambda: (watcher.stop(), stop_finished.set()))
    stopper.start()
    assert not stop_finished.wait(0.05)

    release_registration.set()
    starter.join(1)
    stopper.join(1)

    assert not start_errors
    assert stop_finished.is_set()
    assert observer.started
    assert observer.stopped
    assert observer.join_timeouts == [10]
    assert watcher._observer is None
    assert not watcher._started


def test_watcher_logs_when_observer_remains_alive(tmp_path, caplog):
    observer = FakeObserver(alive=True)
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)
    watcher.start()
    with caplog.at_level("ERROR"):
        watcher.stop()
    assert "did not stop" in caplog.text
    assert watcher._observer is observer
    assert watcher._started


class BlockingStartObserver(FakeObserver):
    def __init__(self):
        super().__init__()
        self.start_entered = threading.Event()
        self.release_start = threading.Event()

    def start(self):
        self.start_entered.set()
        assert self.release_start.wait(2)
        self.started = True


def test_watcher_concurrent_starts_create_one_observer(tmp_path):
    observer = BlockingStartObserver()
    factory = Mock(return_value=observer)
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), observer_factory=factory)
    errors = []

    first = threading.Thread(target=lambda: _call_and_record(watcher.start, errors))
    second = threading.Thread(target=lambda: _call_and_record(watcher.start, errors))
    first.start()
    assert observer.start_entered.wait(1)
    second.start()
    assert second.is_alive()
    observer.release_start.set()
    first.join(1)
    second.join(1)

    assert not errors
    assert not first.is_alive()
    assert not second.is_alive()
    assert factory.call_count == 1
    watcher.stop()


def test_watcher_start_racing_stop_waits_and_cleans_up(tmp_path):
    observer = BlockingStartObserver()
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)
    start_errors = []
    stop_finished = threading.Event()

    starter = threading.Thread(target=lambda: _call_and_record(watcher.start, start_errors))
    starter.start()
    assert observer.start_entered.wait(1)
    stopper = threading.Thread(target=lambda: (watcher.stop(), stop_finished.set()))
    stopper.start()
    assert not stop_finished.wait(0.05)
    observer.release_start.set()
    starter.join(1)
    stopper.join(1)

    assert not start_errors
    assert stop_finished.is_set()
    assert observer.stopped
    assert observer.join_timeouts == [10]
    watcher.stop()


def _call_and_record(function, errors):
    try:
        function()
    except Exception as error:
        errors.append(error)


def test_watcher_cleans_up_observer_when_schedule_fails(tmp_path):
    startup_error = RuntimeError("observer scheduling failed")
    observer = Mock()
    observer.schedule.side_effect = [startup_error, None]
    observer.join.side_effect = AssertionError("join called before observer start")
    observer.is_alive.return_value = False
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)

    with pytest.raises(RuntimeError, match="observer scheduling failed") as raised:
        watcher.start()

    assert raised.value is startup_error
    observer.stop.assert_called_once_with()
    observer.join.assert_not_called()
    assert watcher._observer is None
    assert not watcher._observer_start_attempted
    assert not watcher._started
    watcher.start()
    assert observer.schedule.call_count == 2


def test_watcher_retries_stop_after_stop_failure(tmp_path):
    observer = FakeObserver()
    observer.stop = Mock(side_effect=[RuntimeError("stop failed"), None])
    watcher = DatabaseWatcher(tmp_path / "main.sqlite", Mock(), lambda: observer)
    watcher.start()

    with pytest.raises(RuntimeError, match="stop failed"):
        watcher.stop()
    assert watcher._observer is observer
    assert watcher._started

    watcher.stop()
    assert observer.stop.call_count == 2
    assert observer.join_timeouts == [10, 10]
    assert watcher._observer is None
    assert not watcher._started


def test_watcher_normalizes_database_path_for_watch_and_filter(tmp_path, monkeypatch):
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    real_database = real_parent / "main.sqlite"
    link_parent = tmp_path / "link"
    link_parent.symlink_to(real_parent, target_is_directory=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    observer = FakeObserver()
    watcher = DatabaseWatcher(Path("~/link/main.sqlite"), Mock(), lambda: observer)

    watcher.start()

    assert observer.scheduled[0][1] == str(real_parent)
    handler = observer.scheduled[0][0]
    handler.on_modified(event(real_database))
    watcher._debounce.notify.assert_called_once_with()
    watcher.stop()
