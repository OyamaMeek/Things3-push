from pathlib import Path
from unittest.mock import Mock

import pytest

from src.things_adapter import ThingsReader, discover_database_path, load_default_api


class FakeAPI:
    def todos(self, **kwargs):
        status = kwargs["status"]
        if status == "incomplete":
            return [{
                "uuid": "TASK-1",
                "type": "to-do",
                "title": "Write notes",
                "status": "incomplete",
                "project": "PROJECT-1",
                "project_title": "Release",
                "area": "AREA-1",
                "area_title": "Work",
                "tags": ["important", "work"],
                "checklist": [{
                    "uuid": "ITEM-1",
                    "type": "checklist-item",
                    "title": "Review",
                    "status": "completed",
                }],
                "index": 4,
                "today_index": 2,
            }]
        return []

    def projects(self, **kwargs):
        return [{
            "uuid": "PROJECT-1",
            "type": "project",
            "title": "Release",
            "status": "incomplete",
            "area": "AREA-1",
            "area_title": "Work",
            "index": 1,
        }]

    def areas(self, **kwargs):
        return [{"uuid": "AREA-1", "type": "area", "title": "Work"}]

    def today(self, **kwargs):
        return [{"uuid": "TASK-1", "type": "to-do"}]

    def upcoming(self, **kwargs):
        return []


def test_reader_normalizes_sparse_dictionaries(tmp_path):
    reader = ThingsReader(FakeAPI(), tmp_path / "main.sqlite", sleep=Mock())

    snapshot = reader.read_snapshot()

    task = snapshot.tasks[0]
    assert task.project_uuid == "PROJECT-1"
    assert task.tags == ("important", "work")
    assert task.checklist[0].uuid == "ITEM-1"
    assert snapshot.today_uuids == ("TASK-1",)
    assert snapshot.projects[0].area_uuid == "AREA-1"


def test_reader_deduplicates_status_queries_by_uuid(tmp_path):
    api = FakeAPI()
    api.todos = Mock(side_effect=[
        [{"uuid": "TASK-1", "type": "to-do", "title": "x", "status": "incomplete"}],
        [{"uuid": "TASK-1", "type": "to-do", "title": "x", "status": "completed"}],
        [],
    ])
    reader = ThingsReader(api, tmp_path / "main.sqlite", sleep=Mock())

    snapshot = reader.read_snapshot()

    assert len(snapshot.tasks) == 1
    assert snapshot.tasks[0].status == "completed"


def test_reader_retries_whole_snapshot_three_times(tmp_path):
    api = FakeAPI()
    api.todos = Mock(side_effect=[OSError("locked"), OSError("locked"), [], [], []])
    sleep = Mock()
    reader = ThingsReader(api, tmp_path / "main.sqlite", sleep=sleep)

    snapshot = reader.read_snapshot()

    assert snapshot.tasks == ()
    assert sleep.call_args_list == [((10.0,),), ((10.0,),)]


def test_reader_raises_after_final_failure_without_extra_sleep(tmp_path):
    api = FakeAPI()
    api.todos = Mock(side_effect=OSError("locked"))
    sleep = Mock()
    reader = ThingsReader(api, tmp_path / "main.sqlite", sleep=sleep)

    with pytest.raises(OSError, match="locked"):
        reader.read_snapshot()

    assert sleep.call_count == 2


def test_discover_database_prefers_explicit_path(tmp_path):
    database = tmp_path / "main.sqlite"
    database.touch()
    assert discover_database_path(database, home=tmp_path) == database.resolve()


def test_discover_database_prefers_modern_thingsdata_directory(tmp_path):
    modern = tmp_path / (
        "Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/"
        "ThingsData-ABC/Things Database.thingsdatabase/main.sqlite"
    )
    modern.parent.mkdir(parents=True)
    modern.touch()
    assert discover_database_path(home=tmp_path) == modern.resolve()


def test_embedded_things_fixture_is_readable():
    fixture = Path(__file__).parents[1] / "things.py/tests/main.sqlite"
    if not fixture.exists():
        pytest.skip("local things.py fixture is not available")

    reader = ThingsReader(load_default_api(), fixture, sleep=Mock())
    snapshot = reader.read_snapshot()

    assert snapshot.tasks
    assert all(task.task_type == "to-do" for task in snapshot.tasks)
    assert {task.status for task in snapshot.tasks} <= {
        "incomplete", "completed", "canceled"
    }
