import logging
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.models import ChangeSet, RenderedSnapshot, SyncResult, ThingsSnapshot
import src.sync_engine as sync_engine_module
from src.sync_engine import SyncEngine


def config(repo_path):
    return Mock(
        repo_path=repo_path,
        auto_commit=True,
        auto_push=False,
        git_remote="origin",
        git_branch="main",
    )


def test_sync_runs_single_pipeline_in_order(tmp_path):
    snapshot = ThingsSnapshot()
    rendered = RenderedSnapshot({}, ())
    changes = ChangeSet(added=(Path("Inbox.md"),))
    calls = []
    reader = Mock(read_snapshot=Mock(side_effect=lambda: calls.append("read") or snapshot))
    renderer = Mock(side_effect=lambda value: calls.append("render") or rendered)
    reconciler = Mock(side_effect=lambda repo, value: calls.append("reconcile") or changes)
    git = Mock(sync=Mock(side_effect=lambda *args, **kwargs: calls.append("git") or (True, False)))
    engine = SyncEngine(config(tmp_path), reader, git, renderer, reconciler)

    result = engine.sync()

    assert calls == ["read", "render", "reconcile", "git"]
    assert result == SyncResult(changes, committed=True, pushed=False)


def test_read_failure_prevents_render_write_and_git(tmp_path):
    reader = Mock(read_snapshot=Mock(side_effect=OSError("locked")))
    renderer = Mock()
    reconciler = Mock()
    git = Mock()
    engine = SyncEngine(config(tmp_path), reader, git, renderer, reconciler)

    with pytest.raises(OSError, match="locked"):
        engine.sync()

    assert not list(tmp_path.iterdir())
    renderer.assert_not_called()
    reconciler.assert_not_called()
    git.sync.assert_not_called()


def test_empty_changes_are_still_passed_to_git(tmp_path):
    changes = ChangeSet()
    git = Mock(sync=Mock(return_value=(False, False)))
    engine = SyncEngine(
        config(tmp_path),
        Mock(read_snapshot=Mock(return_value=ThingsSnapshot())),
        git,
        Mock(return_value=RenderedSnapshot({}, ())),
        Mock(return_value=changes),
    )

    result = engine.sync()

    assert result == SyncResult(changes)
    git.sync.assert_called_once_with(
        changes,
        auto_commit=True,
        auto_push=False,
        remote="origin",
        branch="main",
    )


def test_sync_if_idle_is_nonblocking_and_can_run_again(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def read_snapshot():
        calls.append("read")
        entered.set()
        release.wait(timeout=2)
        return ThingsSnapshot()

    engine = SyncEngine(
        config(tmp_path),
        Mock(read_snapshot=read_snapshot),
        Mock(sync=Mock(return_value=(False, False))),
        Mock(return_value=RenderedSnapshot({}, ())),
        Mock(return_value=ChangeSet()),
    )
    first = threading.Thread(target=engine.sync)
    first.start()
    assert entered.wait(timeout=2)

    assert engine.sync_if_idle() is False
    assert calls == ["read"]

    release.set()
    first.join(timeout=2)
    assert not first.is_alive()
    assert engine.sync_if_idle() is True
    assert calls == ["read", "read"]


@pytest.mark.parametrize("failed_stage", ["renderer", "reconciler", "git"])
def test_pipeline_failure_stops_later_stages_and_releases_lock(tmp_path, failed_stage):
    snapshot = ThingsSnapshot()
    rendered = RenderedSnapshot({}, ())
    changes = ChangeSet()
    calls = []
    failure = {"stage": failed_stage}
    reader = Mock(read_snapshot=Mock(side_effect=lambda: calls.append("read") or snapshot))

    def render(value):
        calls.append("render")
        if failure["stage"] == "renderer":
            raise RuntimeError("renderer failed")
        return rendered

    def reconcile(repo, value):
        calls.append("reconcile")
        if failure["stage"] == "reconciler":
            raise RuntimeError("reconciler failed")
        return changes

    def git_sync(*args, **kwargs):
        calls.append("git")
        if failure["stage"] == "git":
            raise RuntimeError("git failed")
        return (False, False)

    renderer = Mock(side_effect=render)
    reconciler = Mock(side_effect=reconcile)
    git = Mock(sync=Mock(side_effect=git_sync))
    engine = SyncEngine(config(tmp_path), reader, git, renderer, reconciler)

    with pytest.raises(RuntimeError, match=failed_stage):
        engine.sync()

    assert calls == {
        "renderer": ["read", "render"],
        "reconciler": ["read", "render", "reconcile"],
        "git": ["read", "render", "reconcile", "git"],
    }[failed_stage]

    failure["stage"] = None
    calls.clear()
    assert engine.sync_if_idle() is True
    assert calls == ["read", "render", "reconcile", "git"]


def test_sync_logs_counts_results_and_failure_markers(tmp_path, caplog):
    changes = ChangeSet(
        added=(Path("a.md"), Path("b.md")),
        modified=(Path("c.md"),),
        deleted=(Path("d.md"),),
    )
    renderer = Mock(return_value=RenderedSnapshot({}, ()))
    reconciler = Mock(return_value=changes)
    git = Mock(sync=Mock(return_value=(True, False)))
    engine = SyncEngine(
        config(tmp_path),
        Mock(read_snapshot=Mock(return_value=ThingsSnapshot())),
        git,
        renderer,
        reconciler,
    )

    with caplog.at_level(logging.INFO, logger=sync_engine_module._LOG.name):
        engine.sync()

    message = caplog.records[-1].getMessage()
    assert "duration=" in message
    assert "added=2 modified=1 deleted=1" in message
    assert "committed=True pushed=False" in message

    failing_renderer = Mock(side_effect=ValueError("render failed"))
    failing_engine = SyncEngine(
        config(tmp_path),
        Mock(read_snapshot=Mock(return_value=ThingsSnapshot())),
        Mock(sync=Mock(return_value=(False, False))),
        failing_renderer,
        Mock(),
    )
    with caplog.at_level(logging.ERROR, logger=sync_engine_module._LOG.name):
        with pytest.raises(ValueError, match="render failed"):
            failing_engine.sync()
    message = caplog.records[-1].getMessage()
    assert "stage=renderer" in message
    assert "added=unavailable" in message
    assert "committed=not executed pushed=not executed" in message


def test_logging_handler_failure_does_not_mask_error_or_lock_release(tmp_path, monkeypatch):
    renderer = Mock(side_effect=ValueError("render failed"))
    engine = SyncEngine(
        config(tmp_path),
        Mock(read_snapshot=Mock(return_value=ThingsSnapshot())),
        Mock(sync=Mock(return_value=(False, False))),
        renderer,
        Mock(),
    )
    monkeypatch.setattr(sync_engine_module._LOG, "error", Mock(side_effect=RuntimeError("log failed")))

    with pytest.raises(ValueError, match="render failed"):
        engine.sync()

    renderer.side_effect = None
    assert engine.sync_if_idle() is True
