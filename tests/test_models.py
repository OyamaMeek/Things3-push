from pathlib import Path
from dataclasses import FrozenInstanceError
import pytest
from src.models import ChecklistItem, RenderedSnapshot, TaskSnapshot, ThingsSnapshot

def test_task_snapshot_is_immutable_and_normalizes_collections():
    task = TaskSnapshot(uuid="TASK-1", title="Ship release", status="incomplete", tags=["work"], checklist=[ChecklistItem(uuid="ITEM-1", title="Tag", status="completed")])
    assert task.tags == ("work",); assert task.checklist[0].status == "completed"
    with pytest.raises(FrozenInstanceError): task.title = "changed"

def test_task_snapshot_rejects_unknown_status():
    with pytest.raises(ValueError, match="Unsupported task status"): TaskSnapshot(uuid="TASK-1", title="x", status="blocked")

def test_rendered_snapshot_copies_files_into_a_read_only_mapping():
    source = {Path("Inbox.md"): "content"}; rendered = RenderedSnapshot(source, ()); source[Path("Today.md")] = "later mutation"
    assert dict(rendered.files) == {Path("Inbox.md"): "content"}
    with pytest.raises(TypeError): rendered.files[Path("Inbox.md")] = "changed"

def test_snapshot_rejects_duplicate_task_uuids():
    one = TaskSnapshot(uuid="TASK-1", title="one", status="incomplete"); duplicate = TaskSnapshot(uuid="TASK-1", title="two", status="completed")
    with pytest.raises(ValueError, match="Duplicate task UUID"): ThingsSnapshot(tasks=(one, duplicate))
