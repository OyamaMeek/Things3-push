from src.markdown import GENERATED_MARKER, render_document, render_task
from src.models import ChecklistItem, TaskSnapshot


def test_render_task_includes_supported_metadata_and_omits_missing_fields():
    task = TaskSnapshot(
        uuid="TASK-1",
        title="Release [v1]",
        status="incomplete",
        project_title="Product",
        area_title="Work",
        heading_title="Next",
        notes="first line\n- nested-looking line",
        tags=("important tag", "work"),
        checklist=(
            ChecklistItem(uuid="ITEM-1", title="Review *copy*", status="completed"),
        ),
        created="2026-09-04 09:00",
        modified="2026-09-04 10:00",
        deadline="2026-09-10",
    )

    rendered = render_task(task)

    assert rendered.startswith("## [ ] Release \\[v1\\]\n<!-- uuid: TASK-1 -->")
    assert "- **项目**: Product" in rendered
    assert "- **截止日期**: 2026-09-10" in rendered
    assert "- **开始日期**" not in rendered
    assert "优先级" not in rendered
    assert "Evening" not in rendered
    assert "  first line\n  - nested-looking line" in rendered
    assert "  - [x] Review \\*copy\\* <!-- uuid: ITEM-1 -->" in rendered


def test_status_markers_are_stable():
    assert render_task(TaskSnapshot("1", "open", "incomplete")).startswith("## [ ]")
    assert render_task(TaskSnapshot("2", "done", "completed")).startswith("## [x]")
    assert render_task(TaskSnapshot("3", "no", "canceled")).startswith("## [-]")


def test_document_has_marker_title_and_stable_separator():
    task = TaskSnapshot("TASK-1", "one", "incomplete")

    rendered = render_document("Inbox", [task])

    assert rendered.startswith(f"{GENERATED_MARKER}\n# Inbox\n\n")
    assert rendered.endswith("\n---\n")


def test_empty_document_remains_managed_and_deterministic():
    assert render_document("Today", []) == f"{GENERATED_MARKER}\n# Today\n"
