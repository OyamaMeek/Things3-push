import json
import os
from pathlib import Path

import pytest

from src.filesystem import MANIFEST_PATH, load_manifest, reconcile
from src.markdown import GENERATED_MARKER
from src.models import ContainerPath, RenderedSnapshot


def managed(title: str) -> str:
    return f"{GENERATED_MARKER}\n# {title}\n"


def test_reconcile_adds_files_and_manifest(tmp_path):
    rendered = RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ())

    changes = reconcile(tmp_path, rendered)

    assert changes.added == (Path(".things3-sync-manifest.json"), Path("Inbox.md"))
    assert (tmp_path / "Inbox.md").read_text() == managed("Inbox")
    assert (tmp_path / MANIFEST_PATH).exists()


def test_identical_reconcile_does_not_rewrite_or_report_changes(tmp_path):
    rendered = RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ())
    reconcile(tmp_path, rendered)
    before = (tmp_path / "Inbox.md").stat().st_mtime_ns

    changes = reconcile(tmp_path, rendered)

    assert not changes.changed
    assert (tmp_path / "Inbox.md").stat().st_mtime_ns == before


def test_removes_only_previous_managed_files(tmp_path):
    reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))
    stranger = tmp_path / "notes.md"
    stranger.write_text("keep me")

    changes = reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert Path("Inbox.md") in changes.deleted
    assert stranger.read_text() == "keep me"


def test_refuses_to_overwrite_unmarked_destination_before_any_write(tmp_path):
    (tmp_path / "Inbox.md").write_text("personal inbox")
    rendered = RenderedSnapshot(
        {Path("Anytime.md"): managed("Anytime"), Path("Inbox.md"): managed("Inbox")}, ()
    )

    with pytest.raises(FileExistsError, match="unmanaged destination"):
        reconcile(tmp_path, rendered)

    assert (tmp_path / "Inbox.md").read_text() == "personal inbox"
    assert not (tmp_path / "Anytime.md").exists()


def test_refuses_to_delete_previous_path_after_marker_is_removed(tmp_path, caplog):
    reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))
    (tmp_path / "Inbox.md").write_text("user-owned now")

    changes = reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert (tmp_path / "Inbox.md").read_text() == "user-owned now"
    assert Path("Inbox.md") not in changes.deleted
    assert "not deleting unmarked file" in caplog.text.lower()


def test_refuses_regular_file_ancestor_before_any_write(tmp_path):
    (tmp_path / "ZParent").write_text("user-owned parent")
    rendered = RenderedSnapshot(
        {Path("A.md"): managed("A"), Path("ZParent/task.md"): managed("Task")}, ()
    )

    with pytest.raises(FileExistsError, match="unmanaged destination: ZParent/task.md"):
        reconcile(tmp_path, rendered)

    assert not (tmp_path / "A.md").exists()
    assert not (tmp_path / MANIFEST_PATH).exists()
    assert (tmp_path / "ZParent").read_text() == "user-owned parent"


def test_non_utf8_unowned_destination_is_an_ownership_conflict(tmp_path):
    (tmp_path / "Inbox.md").write_bytes(b"\xff\xfe")

    with pytest.raises(FileExistsError, match="unmanaged destination: Inbox.md") as error:
        reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))

    assert isinstance(error.value.__cause__, UnicodeDecodeError)
    assert not (tmp_path / MANIFEST_PATH).exists()


def test_refuses_dangling_destination_symlink_before_any_write(tmp_path):
    destination = tmp_path / "Inbox.md"
    destination.symlink_to(tmp_path / "missing-target")

    with pytest.raises(FileExistsError, match="unmanaged destination: Inbox.md"):
        reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))

    assert destination.is_symlink()
    assert not (tmp_path / MANIFEST_PATH).exists()


def test_refuses_dangling_ancestor_symlink_before_any_write(tmp_path):
    ancestor = tmp_path / "ZParent"
    ancestor.symlink_to(tmp_path / "missing-directory", target_is_directory=True)
    rendered = RenderedSnapshot(
        {Path("A.md"): managed("A"), Path("ZParent/task.md"): managed("Task")}, ()
    )

    with pytest.raises(FileExistsError, match="unmanaged destination: ZParent/task.md"):
        reconcile(tmp_path, rendered)

    assert ancestor.is_symlink()
    assert not (tmp_path / "A.md").exists()
    assert not (tmp_path / MANIFEST_PATH).exists()


def test_refuses_dangling_manifest_symlink_before_any_write(tmp_path):
    manifest = tmp_path / MANIFEST_PATH
    manifest.symlink_to(tmp_path / "missing-manifest")

    with pytest.raises(FileExistsError, match="unmanaged destination: .things3-sync-manifest.json"):
        reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))

    assert manifest.is_symlink()
    assert not (tmp_path / "Inbox.md").exists()
    assert not list(tmp_path.glob("..things3-sync-manifest.json.*.tmp"))


@pytest.mark.parametrize("unsafe", [Path("/absolute.md"), Path("../escape.md")])
def test_rejects_unsafe_paths_before_any_disk_mutation(tmp_path, unsafe):
    rendered = RenderedSnapshot({Path("Inbox.md"): managed("Inbox"), unsafe: managed("bad")}, ())

    with pytest.raises(ValueError, match="unsafe"):
        reconcile(tmp_path, rendered)

    assert not (tmp_path / "Inbox.md").exists()
    assert not (tmp_path / MANIFEST_PATH).exists()


def test_title_backslash_path_is_ordinary_on_macos_posix(tmp_path):
    path = Path(r"Projects/Release\\Notes.md")

    reconcile(tmp_path, RenderedSnapshot({path: managed("Release")}, ()))

    assert (tmp_path / path).read_text() == managed("Release")


def test_interrupted_second_write_leaves_no_changeset_and_next_run_converges(tmp_path, monkeypatch):
    import src.filesystem as filesystem

    old_second = managed("old")
    (tmp_path / "Second.md").write_text(old_second)
    original_write = filesystem._atomic_write
    calls = 0

    def interrupted(path, content):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("interrupted")
        original_write(path, content)

    monkeypatch.setattr(filesystem, "_atomic_write", interrupted)
    rendered = RenderedSnapshot(
        {Path("First.md"): managed("first"), Path("Second.md"): managed("second")}, ()
    )

    with pytest.raises(OSError, match="interrupted"):
        reconcile(tmp_path, rendered)

    assert (tmp_path / "First.md").read_text() == managed("first")
    assert (tmp_path / "Second.md").read_text() == old_second
    monkeypatch.setattr(filesystem, "_atomic_write", original_write)
    changes = reconcile(tmp_path, rendered)
    assert changes.modified == (Path("Second.md"),)


def test_replace_failure_preserves_original_and_cleans_tempfile(tmp_path, monkeypatch):
    import src.filesystem as filesystem

    path = tmp_path / "Inbox.md"
    path.write_text(managed("old"))
    original_replace = os.replace

    def fail_replace(source, destination):
        if Path(destination) == path:
            raise OSError("replace failed")
        return original_replace(source, destination)

    monkeypatch.setattr(filesystem.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        filesystem._atomic_write(path, managed("new"))

    assert path.read_text() == managed("old")
    assert not list(tmp_path.glob(".Inbox.md.*.tmp"))


def test_manifest_load_is_typed_and_uses_current_containers(tmp_path):
    rendered = RenderedSnapshot(
        {Path("Projects/Release/tasks.md"): managed("Release")},
        (ContainerPath("P1", "project", Path("Projects/Release")),),
    )
    reconcile(tmp_path, rendered)

    manifest = load_manifest(tmp_path)

    assert manifest.version == 1
    assert manifest.managed_files == (Path("Projects/Release/tasks.md"),)
    assert dict(manifest.active_containers) == {"project:P1": Path("Projects/Release")}
    data = json.loads((tmp_path / MANIFEST_PATH).read_text())
    assert data["_generated_by"] == "things3-github-sync"


@pytest.mark.parametrize(
    "data",
    [
        {"_generated_by": "wrong", "version": 1, "managed_files": [], "active_containers": {}, "archived_containers": {}},
        {"_generated_by": "things3-github-sync", "version": 2, "managed_files": [], "active_containers": {}, "archived_containers": {}},
        {"_generated_by": "things3-github-sync", "version": 1, "managed_files": ["../bad.md"], "active_containers": {}, "archived_containers": {}},
        {"_generated_by": "things3-github-sync", "version": 1, "managed_files": "Inbox.md", "active_containers": {}, "archived_containers": {}},
        {"_generated_by": "things3-github-sync", "version": 1, "managed_files": [], "active_containers": {}, "archived_containers": {}, "future_field": {"retain": True}},
    ],
)
def test_invalid_manifest_prevents_reconcile_writes(tmp_path, data):
    (tmp_path / MANIFEST_PATH).write_text(json.dumps(data))

    with pytest.raises(ValueError):
        reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))

    assert not (tmp_path / "Inbox.md").exists()


def test_invalid_utf8_manifest_prevents_reconcile_writes(tmp_path):
    (tmp_path / MANIFEST_PATH).write_bytes(b"\xff\xfe")

    with pytest.raises(ValueError, match="invalid sync manifest") as error:
        reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))

    assert isinstance(error.value.__cause__, UnicodeDecodeError)
    assert not (tmp_path / "Inbox.md").exists()
    assert (tmp_path / MANIFEST_PATH).read_bytes() == b"\xff\xfe"


def test_git_paths_retains_historical_managed_paths(tmp_path):
    reconcile(tmp_path, RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ()))

    changes = reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert changes.git_paths == (MANIFEST_PATH, Path("Inbox.md"))


def container(uuid, kind, directory):
    return ContainerPath(uuid, kind, Path(directory))


def container_rendered(uuid, kind, directory, title):
    path = Path(directory) / "tasks.md"
    return RenderedSnapshot({path: managed(title)}, (container(uuid, kind, directory),))


def test_renamed_active_container_moves_only_managed_files(tmp_path, caplog):
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/Old", "old"))
    stranger = tmp_path / "Projects/Old/personal.md"
    stranger.write_text("keep me")

    changes = reconcile(tmp_path, container_rendered("P1", "project", "Projects/New", "new"))

    assert (tmp_path / "Projects/New/tasks.md").read_text() == managed("new")
    assert not (tmp_path / "Projects/Old/tasks.md").exists()
    assert stranger.read_text() == "keep me"
    assert Path("Projects/Old/tasks.md") in changes.deleted
    assert "not removing nonempty container directory" in caplog.text.lower()


def test_absent_project_archives_managed_files_and_records_mapping(tmp_path):
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/Release", "release"))

    changes = reconcile(tmp_path, RenderedSnapshot({}, ()))

    archive = Path("Archived/Projects/Release-P1")
    assert (tmp_path / archive / "tasks.md").read_text() == managed("release")
    assert Path("Projects/Release/tasks.md") in changes.deleted
    assert Path("Archived/Projects/Release-P1/tasks.md") in changes.added
    manifest = load_manifest(tmp_path)
    assert dict(manifest.archived_containers) == {"project:P1": archive}
    assert archive / "tasks.md" in manifest.managed_files


def test_absent_area_archives_to_areas(tmp_path):
    reconcile(tmp_path, container_rendered("A1", "area", "Areas/Work", "work"))

    reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert (tmp_path / "Archived/Areas/Work-A1/tasks.md").read_text() == managed("work")
    assert dict(load_manifest(tmp_path).archived_containers) == {
        "area:A1": Path("Archived/Areas/Work-A1")
    }


def test_repeated_absence_retains_archive_without_changes(tmp_path):
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/Release", "release"))
    reconcile(tmp_path, RenderedSnapshot({}, ()))

    changes = reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert not changes.changed
    assert (tmp_path / "Archived/Projects/Release-P1/tasks.md").read_text() == managed("release")


def test_reappearing_container_retains_archive_history(tmp_path):
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/Release", "old release"))
    reconcile(tmp_path, RenderedSnapshot({}, ()))

    reconcile(tmp_path, container_rendered("P1", "project", "Projects/New Release", "new release"))

    assert (tmp_path / "Projects/New Release/tasks.md").read_text() == managed("new release")
    assert (tmp_path / "Archived/Projects/Release-P1/tasks.md").read_text() == managed("old release")
    manifest = load_manifest(tmp_path)
    assert dict(manifest.active_containers) == {"project:P1": Path("Projects/New Release")}
    assert dict(manifest.archived_containers) == {"project:P1": Path("Archived/Projects/Release-P1")}


def test_rearchiving_reuses_existing_archive_directory(tmp_path):
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/Release", "first"))
    reconcile(tmp_path, RenderedSnapshot({}, ()))
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/New Release", "second"))

    reconcile(tmp_path, RenderedSnapshot({}, ()))

    archive = tmp_path / "Archived/Projects/Release-P1"
    assert (archive / "tasks.md").read_text() == managed("second")
    assert not (tmp_path / "Archived/Projects/Release-P1-2").exists()


def test_rearchive_refuses_to_overwrite_unmarked_archive_file(tmp_path):
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/Release", "first"))
    reconcile(tmp_path, RenderedSnapshot({}, ()))
    reconcile(tmp_path, container_rendered("P1", "project", "Projects/New Release", "second"))
    archive_file = tmp_path / "Archived/Projects/Release-P1/tasks.md"
    archive_file.write_text("history edited by user")

    with pytest.raises(FileExistsError, match="unmanaged destination"):
        reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert archive_file.read_text() == "history edited by user"
    assert (tmp_path / "Projects/New Release/tasks.md").read_text() == managed("second")


@pytest.mark.parametrize(
    ("uuid", "suffix"),
    [("a/b:cdefghijk", "a-b-cdef"), ("////", "0ea28b45")],
)
def test_archive_uuid_suffix_is_sanitized_and_stable(tmp_path, uuid, suffix):
    reconcile(tmp_path, container_rendered(uuid, "project", "Projects/Release", "release"))

    reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert (tmp_path / "Archived/Projects" / f"Release-{suffix}" / "tasks.md").exists()
