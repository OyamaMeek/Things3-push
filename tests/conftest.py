import pytest

from src.models import ContainerSnapshot, TaskSnapshot, ThingsSnapshot


@pytest.fixture
def sample_snapshot():
    project = ContainerSnapshot("P1", "project", "Release", area_uuid="A1")
    area = ContainerSnapshot("A1", "area", "Work")
    tasks = (
        TaskSnapshot("T1", "Project task", "incomplete", project_uuid="P1", area_uuid="A1", start="Anytime", index=2),
        TaskSnapshot("T2", "Area task", "incomplete", area_uuid="A1", start="Someday", index=1),
        TaskSnapshot("T3", "Inbox task", "incomplete", start="Inbox", index=0),
        TaskSnapshot("T4", "Done", "completed", project_uuid="P1", stop_date="2026-09-04 10:00"),
        TaskSnapshot("T5", "Canceled", "canceled", start="Anytime", stop_date="2026-09-03 10:00"),
    )
    return ThingsSnapshot(
        tasks=tasks,
        projects=(project,),
        areas=(area,),
        today_uuids=("T2", "T1"),
        upcoming_uuids=("T3",),
    )
