import subprocess
from pathlib import Path
from types import SimpleNamespace

from src.filesystem import reconcile
from src.git_ops import GitClient
from src.models import ContainerSnapshot, TaskSnapshot, ThingsSnapshot
from src.renderer import render_snapshot
from src.sync_engine import SyncEngine


def run(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def initialized_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(repo, "init")
    run(repo, "config", "user.name", "Test")
    run(repo, "config", "user.email", "test@example.invalid")
    (repo / ".keep").write_text("\n")
    run(repo, "add", ".keep")
    run(repo, "commit", "-m", "seed")
    return repo


def sync_engine(repo, snapshots):
    reader = SimpleNamespace(read_snapshot=lambda: snapshots[0])
    config = SimpleNamespace(
        repo_path=repo,
        auto_commit=True,
        auto_push=False,
        git_remote="origin",
        git_branch="main",
    )
    return SyncEngine(config, reader, GitClient(repo), render_snapshot, reconcile)


def committed_paths(repo):
    return set(filter(None, run(repo, "show", "--no-renames", "--format=", "--name-only", "HEAD").splitlines()))


def test_snapshot_sync_commits_managed_files_and_is_idempotent(tmp_path, sample_snapshot):
    repo = initialized_repo(tmp_path)
    engine = sync_engine(repo, [sample_snapshot])

    first = engine.sync()
    first_head = run(repo, "rev-parse", "HEAD")
    assert first.committed
    assert (repo / "Inbox.md").exists()
    assert (repo / ".things3-sync-manifest.json").exists()
    assert "Inbox.md" in run(repo, "show", "--format=", "--name-only", "HEAD")

    second = engine.sync()
    assert not second.committed
    assert run(repo, "rev-parse", "HEAD") == first_head


def test_title_only_change_updates_and_commits_only_affected_documents(tmp_path):
    repo = initialized_repo(tmp_path)
    snapshots = [
        ThingsSnapshot(tasks=(TaskSnapshot("T1", "Before", "incomplete", start="Inbox"),)),
    ]
    engine = sync_engine(repo, snapshots)
    assert engine.sync().committed

    snapshots[0] = ThingsSnapshot(tasks=(TaskSnapshot("T1", "After", "incomplete", start="Inbox"),))
    result = engine.sync()

    assert result.committed
    assert "After" in (repo / "Inbox.md").read_text()
    assert "Before" not in (repo / "Inbox.md").read_text()
    assert committed_paths(repo) == {"Inbox.md"}


def test_moving_task_from_inbox_to_project_updates_both_primary_documents(tmp_path):
    repo = initialized_repo(tmp_path)
    project = ContainerSnapshot("P1", "project", "Release")
    snapshots = [
        ThingsSnapshot(
            tasks=(TaskSnapshot("T1", "Move me", "incomplete", start="Inbox"),),
            projects=(project,),
        ),
    ]
    engine = sync_engine(repo, snapshots)
    assert engine.sync().committed

    snapshots[0] = ThingsSnapshot(
        tasks=(TaskSnapshot("T1", "Move me", "incomplete", project_uuid="P1", start="Anytime"),),
        projects=(project,),
    )
    assert engine.sync().committed

    assert "Move me" not in (repo / "Inbox.md").read_text()
    assert "Move me" in (repo / "Projects" / "Release" / "tasks.md").read_text()
    assert committed_paths(repo) == {"Inbox.md", "Projects/Release/tasks.md"}


def test_archiving_container_preserves_unmanaged_file_and_excludes_it_from_commit(tmp_path):
    repo = initialized_repo(tmp_path)
    project = ContainerSnapshot("P1", "project", "Release")
    snapshots = [
        ThingsSnapshot(
            tasks=(TaskSnapshot("T1", "Release task", "incomplete", project_uuid="P1"),),
            projects=(project,),
        ),
    ]
    engine = sync_engine(repo, snapshots)
    assert engine.sync().committed
    stranger = repo / "Projects" / "Release" / "notes.txt"
    stranger.write_text("keep me\n")

    snapshots[0] = ThingsSnapshot()
    assert engine.sync().committed

    archive = repo / "Archived" / "Projects" / "Release-P1"
    assert stranger.read_text() == "keep me\n"
    assert (archive / "tasks.md").exists()
    paths = committed_paths(repo)
    assert "Projects/Release/notes.txt" not in paths
    assert "Archived/Projects/Release-P1/tasks.md" in paths
    assert "Projects/Release/tasks.md" in paths


def test_sync_commit_preserves_unrelated_real_index_staging(tmp_path):
    repo = initialized_repo(tmp_path)
    (repo / "user.txt").write_text("staged user work\n")
    run(repo, "add", "user.txt")
    snapshots = [ThingsSnapshot(tasks=(TaskSnapshot("T1", "Managed", "incomplete", start="Inbox"),))]

    assert sync_engine(repo, snapshots).sync().committed

    assert "user.txt" not in committed_paths(repo)
    assert run(repo, "diff", "--cached", "--name-only") == "user.txt"
