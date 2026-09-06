import logging
from pathlib import Path

from src.models import ContainerSnapshot, TaskSnapshot, ThingsSnapshot
from src.renderer import allocate_container_paths, render_snapshot


def test_routes_each_task_to_one_primary_location_and_dynamic_views(sample_snapshot):
    rendered = render_snapshot(sample_snapshot)

    assert "Project task" in rendered.files[Path("Projects/Release/tasks.md")]
    assert "Project task" not in rendered.files[Path("Areas/Work/tasks.md")]
    assert "Area task" in rendered.files[Path("Areas/Work/tasks.md")]
    assert "Inbox task" in rendered.files[Path("Inbox.md")]
    assert "Done" in rendered.files[Path("Projects/Release/已完成.md")]
    assert "Canceled" in rendered.files[Path("已取消.md")]
    assert rendered.files[Path("Today.md")].index("Area task") < rendered.files[Path("Today.md")].index("Project task")
    assert "Inbox task" in rendered.files[Path("Upcoming.md")]


def test_emits_fixed_top_level_and_empty_container_files():
    snapshot = ThingsSnapshot(
        projects=(ContainerSnapshot("P1", "project", "Empty"),),
        areas=(ContainerSnapshot("A1", "area", "Quiet"),),
    )

    rendered = render_snapshot(snapshot)

    expected = {
        Path("Inbox.md"), Path("Today.md"), Path("Anytime.md"),
        Path("Someday.md"), Path("Upcoming.md"), Path("已完成.md"),
        Path("已取消.md"), Path("Projects/Empty/tasks.md"),
        Path("Projects/Empty/已完成.md"), Path("Projects/Empty/已取消.md"),
        Path("Areas/Quiet/tasks.md"), Path("Areas/Quiet/已完成.md"),
        Path("Areas/Quiet/已取消.md"),
    }
    assert expected <= set(rendered.files)


def test_case_insensitive_collisions_get_stable_uuid_suffixes():
    projects = (
        ContainerSnapshot("AAA11111", "project", "Release"),
        ContainerSnapshot("BBB22222", "project", "release"),
    )

    paths = allocate_container_paths(projects, ())

    assert {item.relative_dir for item in paths} == {
        Path("Projects/Release-AAA11111"),
        Path("Projects/release-BBB22222"),
    }


def test_render_is_independent_of_input_tuple_order(sample_snapshot):
    reversed_snapshot = ThingsSnapshot(
        tasks=tuple(reversed(sample_snapshot.tasks)),
        projects=sample_snapshot.projects,
        areas=sample_snapshot.areas,
        today_uuids=sample_snapshot.today_uuids,
        upcoming_uuids=sample_snapshot.upcoming_uuids,
    )
    assert render_snapshot(sample_snapshot).files == render_snapshot(reversed_snapshot).files


def test_invalid_or_missing_start_routes_incomplete_task_to_anytime_with_warning(caplog):
    snapshot = ThingsSnapshot(tasks=(
        TaskSnapshot("T1", "Invalid start", "incomplete", start="Later"),
        TaskSnapshot("T2", "Missing start", "incomplete"),
    ))

    with caplog.at_level(logging.WARNING):
        rendered = render_snapshot(snapshot)

    assert "Invalid start" in rendered.files[Path("Anytime.md")]
    assert "Missing start" in rendered.files[Path("Anytime.md")]
    assert len(caplog.records) == 2


def test_excludes_trashed_tasks_and_containers():
    snapshot = ThingsSnapshot(
        tasks=(TaskSnapshot("T1", "Trashed task", "incomplete", trashed=True),),
        projects=(ContainerSnapshot("P1", "project", "Trashed", trashed=True),),
        areas=(ContainerSnapshot("A1", "area", "Trashed", trashed=True),),
    )

    rendered = render_snapshot(snapshot)

    assert "Trashed task" not in "".join(rendered.files.values())
    assert not rendered.containers


def test_path_allocation_handles_duplicate_short_uuid_prefixes_and_natural_suffixes():
    projects = (
        ContainerSnapshot("AAAAAAAA-one", "project", "Release"),
        ContainerSnapshot("AAAAAAAA-two", "project", "release"),
        ContainerSnapshot("BBBBBBBB-three", "project", "Release-AAAAAAAA"),
    )

    paths = allocate_container_paths(projects, ())

    assert len({path.relative_dir.as_posix().casefold() for path in paths}) == 3
    assert all(len(path.relative_dir.name) <= 120 for path in paths)


def test_case_only_uuid_collision_preserves_every_container_document():
    projects = (
        ContainerSnapshot("AAAAAAAA", "project", "Release"),
        ContainerSnapshot("aaaaaaaa", "project", "release"),
    )
    snapshot = ThingsSnapshot(projects=projects)

    paths = allocate_container_paths(projects, ())
    rendered = render_snapshot(snapshot)

    assert len({path.relative_dir.as_posix().casefold() for path in paths}) == 2
    for container_path in paths:
        assert container_path.relative_dir / "tasks.md" in rendered.files
        assert container_path.relative_dir / "已完成.md" in rendered.files
        assert container_path.relative_dir / "已取消.md" in rendered.files


def test_uuid_tokens_cannot_escape_container_roots():
    projects = (
        ContainerSnapshot("../TARGET", "project", "Release"),
        ContainerSnapshot(r"..\TARGET", "project", "release"),
    )
    areas = (
        ContainerSnapshot("A:/../TARGET", "area", "Focus"),
        ContainerSnapshot(r"A:\..\TARGET", "area", "focus"),
    )

    paths = allocate_container_paths(projects, areas)
    rendered = render_snapshot(ThingsSnapshot(projects=projects, areas=areas))

    assert len({path.relative_dir.as_posix().casefold() for path in paths}) == 4
    for container_path in paths:
        assert not container_path.relative_dir.is_absolute()
        assert ".." not in container_path.relative_dir.parts
        assert container_path.relative_dir.parts[0] == (
            "Projects" if container_path.kind == "project" else "Areas"
        )
    for path in rendered.files:
        assert not path.is_absolute()
        assert ".." not in path.parts
        if len(path.parts) > 1:
            assert path.parts[0] in {"Projects", "Areas"}


def test_terminal_tasks_sort_newest_stop_date_first():
    snapshot = ThingsSnapshot(tasks=(
        TaskSnapshot("old", "Old", "completed", stop_date="2026-01-01"),
        TaskSnapshot("new", "New", "completed", stop_date="2026-02-01"),
    ))

    rendered = render_snapshot(snapshot)

    assert rendered.files[Path("已完成.md")].index("New") < rendered.files[Path("已完成.md")].index("Old")


def test_missing_dynamic_ids_warn_once_and_duplicate_views_are_preserved(caplog):
    task = TaskSnapshot("T1", "Task", "incomplete")
    snapshot = ThingsSnapshot(
        tasks=(task,),
        today_uuids=("T1", "T1", "MISSING", "MISSING"),
        upcoming_uuids=("MISSING",),
    )

    with caplog.at_level(logging.WARNING):
        rendered = render_snapshot(snapshot)

    assert rendered.files[Path("Today.md")].count("## [ ] Task") == 2
    assert len([record for record in caplog.records if "MISSING" in record.message]) == 1


def test_missing_project_falls_through_to_active_area():
    snapshot = ThingsSnapshot(
        areas=(ContainerSnapshot("A1", "area", "Work"),),
        tasks=(TaskSnapshot("T1", "Area fallback", "incomplete", project_uuid="gone", area_uuid="A1"),),
    )

    assert "Area fallback" in render_snapshot(snapshot).files[Path("Areas/Work/tasks.md")]
