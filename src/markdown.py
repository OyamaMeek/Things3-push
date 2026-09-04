"""Deterministic Markdown rendering for Things task snapshots."""

import re
from typing import Sequence

from .models import ChecklistItem, TaskSnapshot

GENERATED_MARKER = "<!-- generated-by: things3-github-sync; do not edit -->"

_STATUS_MARKERS = {
    "incomplete": " ",
    "completed": "x",
    "canceled": "-",
}
_INLINE_SPECIALS = "\\`*_[]<>"


def escape_inline(value: str) -> str:
    """Normalize and escape a value that must remain on one Markdown line."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\n", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    escaped = []
    for character in normalized:
        if character in _INLINE_SPECIALS:
            escaped.append("\\")
        escaped.append(character)
    return "".join(escaped)


def _status_marker(status: str) -> str:
    return _STATUS_MARKERS[status]


def _field(label: str, value: str) -> str:
    return "- **{}**: {}".format(label, escape_inline(value))


def _render_tags(tags: Sequence[str]) -> str:
    rendered = []
    for tag in tags:
        normalized = tag.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"\s+", "-", normalized.replace("\n", " ").strip())
        rendered.append("#" + escape_inline(normalized))
    return " ".join(rendered)


def _render_notes(notes: str) -> Sequence[str]:
    normalized = notes.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or not any(line.strip() for line in lines):
        return ()
    return tuple("  " + line for line in lines)


def _render_checklist_item(item: ChecklistItem) -> str:
    line = "  - [{}] {}".format(_status_marker(item.status), escape_inline(item.title))
    if item.stop_date:
        line += " — 完成时间: " + escape_inline(item.stop_date)
    return line + " <!-- uuid: {} -->".format(item.uuid)


def render_task(task: TaskSnapshot) -> str:
    """Render one task as a deterministic Markdown block."""
    lines = [
        "## [{}] {}".format(_status_marker(task.status), escape_inline(task.title)),
        "<!-- uuid: {} -->".format(task.uuid),
    ]

    fields = (
        ("创建时间", task.created),
        ("修改时间", task.modified),
        ("开始日期", task.start_date),
        ("截止日期", task.deadline),
        ("提醒时间", task.reminder_time),
        ("项目", task.project_title),
        ("领域", task.area_title),
        ("标题分组", task.heading_title),
    )
    lines.extend(_field(label, value) for label, value in fields if value)

    if task.tags:
        lines.append("- **标签**: " + _render_tags(task.tags))

    note_lines = _render_notes(task.notes) if task.notes else ()
    if note_lines:
        lines.append("- **备注**:")
        lines.extend(note_lines)

    if task.checklist:
        lines.append("- **子任务**:")
        lines.extend(_render_checklist_item(item) for item in task.checklist)

    return "\n".join(lines) + "\n"


def render_document(title: str, tasks: Sequence[TaskSnapshot]) -> str:
    """Render a managed Markdown document containing task blocks."""
    header = "{}\n# {}\n".format(GENERATED_MARKER, escape_inline(title))
    if not tasks:
        return header

    blocks = [render_task(task).rstrip("\n") for task in tasks]
    return header + "\n" + "\n---\n".join(blocks) + "\n---\n"


def is_managed_markdown(content: str) -> bool:
    """Return whether the first line is the exact generated marker."""
    first_line = content.splitlines()[0] if content.splitlines() else ""
    return first_line == GENERATED_MARKER
