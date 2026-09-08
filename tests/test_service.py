import importlib
import logging
import signal
import subprocess
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.config import AppConfig
from src.service import SyncService, build_service


class ScriptedEvent:
    def __init__(self, results):
        self.results = list(results)
        self.timeouts = []
        self.set_calls = 0
        self._is_set = False

    def is_set(self):
        return self._is_set

    def wait(self, timeout):
        self.timeouts.append(timeout)
        return self.results.pop(0)

    def set(self):
        self.set_calls += 1
        self._is_set = True


def test_run_performs_startup_sync_then_starts_watcher():
    calls = []
    engine = Mock(sync=Mock(side_effect=lambda: calls.append("startup")))
    watcher = Mock(start=Mock(side_effect=lambda: calls.append("watch")))
    debouncer = Mock(stop=Mock(side_effect=lambda wait: calls.append("debounce")))
    watcher.stop.side_effect = lambda: calls.append("stop-watch")
    stop_event = ScriptedEvent([True])

    SyncService(engine, watcher, debouncer, 3600, stop_event).run()

    assert calls == ["startup", "watch", "stop-watch", "debounce"]
    assert stop_event.timeouts == [3600]
    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_watcher_start_failure_stops_watcher_before_debouncer():
    calls = []
    error = RuntimeError("watcher startup")
    engine = Mock(sync=Mock())
    watcher = Mock(start=Mock(side_effect=error))
    watcher.stop.side_effect = lambda: calls.append("stop-watch")
    debouncer = Mock(stop=Mock(side_effect=lambda wait: calls.append("debounce")))

    with pytest.raises(RuntimeError, match="watcher startup"):
        SyncService(engine, watcher, debouncer, 60, ScriptedEvent([])).run()

    assert calls == ["stop-watch", "debounce"]
    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_stop_requested_during_startup_prevents_watcher_start():
    engine = Mock()
    watcher = Mock()
    debouncer = Mock()
    stop_event = ScriptedEvent([])
    service = SyncService(engine, watcher, debouncer, 60, stop_event)
    engine.sync.side_effect = service.stop

    service.run()

    watcher.start.assert_not_called()
    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_stop_does_not_wait_for_blocking_watcher_start():
    start_entered = threading.Event()
    release_start = threading.Event()
    start_finished = threading.Event()

    def start_watcher():
        start_entered.set()
        release_start.wait(2)
        start_finished.set()

    engine = Mock()
    watcher = Mock(start=Mock(side_effect=start_watcher))
    debouncer = Mock()
    service = SyncService(engine, watcher, debouncer, 60, threading.Event())
    run_thread = threading.Thread(target=service.run)
    run_thread.start()
    assert start_entered.wait(1)

    service.stop()

    assert service.stop_event.is_set()
    assert not start_finished.is_set()
    release_start.set()
    run_thread.join(1)
    assert not run_thread.is_alive()
    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_stop_does_not_wait_for_blocking_periodic_sync():
    sync_entered = threading.Event()
    release_sync = threading.Event()
    wait_until_sync = threading.Event()

    def sync():
        if wait_until_sync.is_set():
            sync_entered.set()
            release_sync.wait(2)
        else:
            wait_until_sync.set()

    engine = Mock(sync=Mock(side_effect=sync))
    watcher = Mock()
    debouncer = Mock()
    stop_event = ScriptedEvent([False, True])
    service = SyncService(engine, watcher, debouncer, 60, stop_event)
    run_thread = threading.Thread(target=service.run)
    run_thread.start()
    assert sync_entered.wait(1)

    service.stop()

    assert stop_event.is_set()
    assert not release_sync.is_set()
    release_sync.set()
    run_thread.join(1)
    assert not run_thread.is_alive()
    assert engine.sync.call_count == 2
    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_normal_exit_propagates_cleanup_failure():
    watcher = Mock()
    cleanup_error = OSError("watcher cleanup")
    watcher.stop.side_effect = cleanup_error
    debouncer = Mock()

    with pytest.raises(OSError, match="watcher cleanup"):
        SyncService(Mock(), watcher, debouncer, 60, ScriptedEvent([True])).run()

    debouncer.stop.assert_called_once_with(wait=True)


def test_normal_exit_propagates_debouncer_cleanup_failure():
    watcher = Mock()
    debouncer = Mock()
    cleanup_error = OSError("debouncer cleanup")
    debouncer.stop.side_effect = cleanup_error

    with pytest.raises(OSError, match="debouncer cleanup"):
        SyncService(Mock(), watcher, debouncer, 60, ScriptedEvent([True])).run()

    watcher.stop.assert_called_once_with()


def test_watcher_start_failure_cleanup_does_not_mask_original_error():
    engine = Mock()
    watcher = Mock()
    debouncer = Mock()
    startup_error = RuntimeError("watcher startup")
    watcher.start.side_effect = startup_error
    watcher.stop.side_effect = OSError("watcher cleanup")
    debouncer.stop.side_effect = OSError("debouncer cleanup")

    with pytest.raises(RuntimeError, match="watcher startup"):
        SyncService(engine, watcher, debouncer, 60, ScriptedEvent([])).run()

    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_main_returns_one_when_normal_cleanup_fails(monkeypatch, caplog):
    main_module = _load_main()
    config = AppConfig(repo_path=Path.cwd())
    service = Mock()
    service.run.side_effect = OSError("cleanup")

    monkeypatch.setattr(main_module.dotenv, "load_dotenv", Mock())
    monkeypatch.setattr(main_module.AppConfig, "from_env", Mock(return_value=config))
    monkeypatch.setattr(main_module, "setup_logging", Mock())
    monkeypatch.setattr(main_module, "build_service", Mock(return_value=service))

    with caplog.at_level(logging.ERROR, logger="main"):
        assert main_module.main() == 1

    assert "Service failed" in caplog.text
    assert "cleanup" not in caplog.text
    assert "Traceback" not in caplog.text


def test_interval_uses_same_engine_entrypoint():
    engine = Mock()
    stop_event = ScriptedEvent([False, True])

    SyncService(engine, Mock(), Mock(), 60, stop_event).run()

    assert engine.sync.call_count == 2
    assert stop_event.timeouts == [60, 60]


def test_interval_failure_is_logged_without_exception_details_or_traceback(caplog):
    secret = "password=/private/secret/things.sqlite"
    engine = Mock(sync=Mock(side_effect=[None, RuntimeError(secret), None]))
    stop_event = ScriptedEvent([False, False, True])

    with caplog.at_level(logging.ERROR, logger="src.service"):
        SyncService(engine, Mock(), Mock(), 15, stop_event).run()

    assert engine.sync.call_count == 3
    assert "Scheduled full sync failed" in caplog.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text


def test_startup_failure_propagates_and_watcher_does_not_start():
    error = OSError("startup")
    engine = Mock(sync=Mock(side_effect=error))
    watcher = Mock()
    debouncer = Mock()

    with pytest.raises(OSError, match="startup"):
        SyncService(engine, watcher, debouncer, 60, ScriptedEvent([])).run()

    watcher.start.assert_not_called()
    watcher.stop.assert_not_called()
    debouncer.stop.assert_not_called()


def test_stop_is_idempotent():
    stop_event = ScriptedEvent([])
    service = SyncService(Mock(), Mock(), Mock(), 60, stop_event)

    service.stop()
    service.stop()

    assert stop_event.set_calls == 1


def test_build_service_wires_database_and_dependencies(monkeypatch, tmp_path):
    database = tmp_path / "main.sqlite"
    config = AppConfig(repo_path=tmp_path, things_db=database)
    api = object()
    reader = object()
    git_client = object()
    engine = Mock()
    debouncer = object()
    watcher = object()
    service = object()

    discover = Mock(return_value=database)
    load_api = Mock(return_value=api)
    reader_ctor = Mock(return_value=reader)
    git_ctor = Mock(return_value=git_client)
    engine_ctor = Mock(return_value=engine)
    debounce_ctor = Mock(return_value=debouncer)
    watcher_ctor = Mock(return_value=watcher)
    service_ctor = Mock(return_value=service)

    import src.service as service_module

    monkeypatch.setattr(service_module, "discover_database_path", discover)
    monkeypatch.setattr(service_module, "load_default_api", load_api)
    monkeypatch.setattr(service_module, "ThingsReader", reader_ctor)
    monkeypatch.setattr(service_module, "GitClient", git_ctor)
    monkeypatch.setattr(service_module, "SyncEngine", engine_ctor)
    monkeypatch.setattr(service_module, "DebouncedSync", debounce_ctor)
    monkeypatch.setattr(service_module, "DatabaseWatcher", watcher_ctor)
    monkeypatch.setattr(service_module, "SyncService", service_ctor)

    assert build_service(config) is service
    discover.assert_called_once_with(database)
    load_api.assert_called_once_with()
    reader_ctor.assert_called_once_with(api, database)
    git_ctor.assert_called_once_with(tmp_path, timeout=config.git_timeout_seconds)
    engine_ctor.assert_called_once_with(config, reader, git_client)
    debounce_ctor.assert_called_once_with(engine.sync_if_idle, config.watch_debounce_seconds)
    watcher_ctor.assert_called_once_with(database, debouncer)
    service_ctor.assert_called_once_with(engine, watcher, debouncer, config.full_sync_interval)


def _load_main():
    import main

    return importlib.reload(main)


def test_main_loads_dotenv_configures_project_logs_and_registers_signals(monkeypatch, tmp_path):
    main_module = _load_main()
    config = AppConfig(repo_path=tmp_path)
    service = Mock()
    load_dotenv = Mock()
    from_env = Mock(return_value=config)
    setup = Mock()
    build = Mock(return_value=service)
    registered = {}

    monkeypatch.setattr(main_module.dotenv, "load_dotenv", load_dotenv)
    monkeypatch.setattr(main_module.AppConfig, "from_env", from_env)
    monkeypatch.setattr(main_module, "setup_logging", setup)
    monkeypatch.setattr(main_module, "service_holder", {"service": service})
    monkeypatch.setattr(main_module, "build_service", build)
    monkeypatch.setattr(main_module.signal, "signal", lambda signum, handler: registered.setdefault(signum, handler))

    assert main_module.main() == 0

    load_dotenv.assert_called_once_with()
    from_env.assert_called_once_with()
    setup.assert_called_once_with(
        Path(main_module.__file__).resolve().parent / "logs",
        config.log_level,
        config.log_max_bytes,
        config.log_backup_count,
    )
    build.assert_called_once_with(config)
    assert set(registered) == {signal.SIGINT, signal.SIGTERM}
    registered[signal.SIGINT](signal.SIGINT, None)
    registered[signal.SIGTERM](signal.SIGTERM, None)
    assert service.stop.call_count == 2
    service.run.assert_called_once_with()


@pytest.mark.parametrize("error", [
    ValueError("bad config password=/private/secret"),
    subprocess.TimeoutExpired(["git", "rev-parse"], 30),
    OSError("config path=/private/secret"),
])
def test_main_configuration_failure_returns_two_without_exception_details(monkeypatch, caplog, error):
    main_module = _load_main()
    monkeypatch.setattr(main_module.dotenv, "load_dotenv", Mock(side_effect=error))
    monkeypatch.setattr(main_module.AppConfig, "from_env", Mock())

    with caplog.at_level(logging.ERROR, logger="main"):
        result = main_module.main()

    assert result == 2
    assert caplog.text.count("Configuration failed") == 1
    assert str(error) not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize("error", [
    ValueError("bad config password=/private/secret"),
    subprocess.TimeoutExpired(["git", "rev-parse"], 30),
    OSError("config path=/private/secret"),
])
def test_main_app_config_failure_returns_two_without_exception_details(monkeypatch, caplog, error):
    main_module = _load_main()
    monkeypatch.setattr(main_module.dotenv, "load_dotenv", Mock())
    monkeypatch.setattr(main_module.AppConfig, "from_env", Mock(side_effect=error))

    with caplog.at_level(logging.ERROR, logger="main"):
        result = main_module.main()

    assert result == 2
    assert caplog.text.count("Configuration failed") == 1
    assert str(error) not in caplog.text
    assert "Traceback" not in caplog.text


def test_main_runtime_failure_returns_one_without_exception_details(monkeypatch, caplog):
    main_module = _load_main()
    config = AppConfig(repo_path=Path.cwd())
    secret = "runtime password=/private/secret"
    monkeypatch.setattr(main_module.dotenv, "load_dotenv", Mock())
    monkeypatch.setattr(main_module.AppConfig, "from_env", Mock(return_value=config))
    monkeypatch.setattr(main_module, "setup_logging", Mock())
    monkeypatch.setattr(main_module, "build_service", Mock(side_effect=RuntimeError(secret)))

    with caplog.at_level(logging.ERROR, logger="main"):
        result = main_module.main()

    assert result == 1
    assert "Service failed" in caplog.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text


def test_stop_requested_during_watcher_start_prevents_watcher_start():
    engine = Mock()
    watcher = Mock()
    debouncer = Mock()
    stop_event = ScriptedEvent([])
    service = SyncService(engine, watcher, debouncer, 60, stop_event)
    engine.sync.side_effect = service.stop

    service.run()

    watcher.start.assert_not_called()
    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_stop_requested_after_watcher_start_prevents_extra_interval_sync():
    engine = Mock()
    watcher = Mock()
    debouncer = Mock()
    stop_event = ScriptedEvent([False, True])
    service = SyncService(engine, watcher, debouncer, 60, stop_event)
    engine.sync.side_effect = [None, service.stop]

    service.run()

    assert engine.sync.call_count == 2
    watcher.start.assert_called_once_with()
    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_watcher_start_failure_does_not_mask_original_error():
    engine = Mock()
    watcher = Mock()
    debouncer = Mock()
    error = RuntimeError("watcher startup")
    watcher.start.side_effect = error
    watcher.stop.side_effect = OSError("cleanup")

    with pytest.raises(RuntimeError, match="watcher startup"):
        SyncService(engine, watcher, debouncer, 60, ScriptedEvent([])).run()

    watcher.stop.assert_called_once_with()
    debouncer.stop.assert_called_once_with(wait=True)


def test_signal_handlers_registered_after_service_construction(monkeypatch):
    main_module = _load_main()
    config = AppConfig(repo_path=Path.cwd())
    service = Mock()
    registered = {}

    monkeypatch.setattr(main_module.dotenv, "load_dotenv", Mock())
    monkeypatch.setattr(main_module.AppConfig, "from_env", Mock(return_value=config))
    monkeypatch.setattr(main_module, "setup_logging", Mock())
    monkeypatch.setattr(main_module, "service_holder", {})

    def build(config):
        main_module.service_holder["service"] = service
        return service

    monkeypatch.setattr(main_module, "build_service", build)
    monkeypatch.setattr(
        main_module.signal, "signal", lambda signum, handler: registered.setdefault(signum, handler)
    )

    assert main_module.main() == 0
    assert set(registered) == {signal.SIGINT, signal.SIGTERM}
    assert main_module.service_holder["service"] is service
    registered[signal.SIGINT](signal.SIGINT, None)
    registered[signal.SIGTERM](signal.SIGTERM, None)
    assert service.stop.call_count == 2
