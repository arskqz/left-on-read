"""List models for QML views."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, QPersistentModelIndex, Qt

from ..core.model import SYSTEM, USER, Conversation, Issue
from ..core.project import Project

PREVIEW_LENGTH = 200


@dataclass(frozen=True)
class _Row:
    conversation_id: int
    preview: str
    turns: int
    status: str
    tags: tuple[str, ...]


def _row(conv: Conversation) -> _Row:
    first_user = next((m.content for m in conv.messages if m.role == USER and isinstance(m.content, str)), "")
    preview = " ".join(first_user.split())
    if len(preview) > PREVIEW_LENGTH:
        preview = preview[: PREVIEW_LENGTH - 1] + "…"
    turns = sum(1 for m in conv.messages if m.role != SYSTEM)
    return _Row(conv.id, preview, turns, conv.status, tuple(sorted(conv.tags)))


class ConversationListModel(QAbstractListModel):
    """One row per conversation, in source order."""

    IdRole = Qt.ItemDataRole.UserRole + 1
    PreviewRole = Qt.ItemDataRole.UserRole + 2
    TurnsRole = Qt.ItemDataRole.UserRole + 3
    StatusRole = Qt.ItemDataRole.UserRole + 4
    TagsRole = Qt.ItemDataRole.UserRole + 5

    _ROLE_NAMES = {
        IdRole: QByteArray(b"conversationId"),
        PreviewRole: QByteArray(b"preview"),
        TurnsRole: QByteArray(b"turns"),
        StatusRole: QByteArray(b"status"),
        TagsRole: QByteArray(b"tags"),
    }

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[_Row] = []
        self._row_of: dict[int, int] = {}

    def reset(self, project: Project | None) -> None:
        self.beginResetModel()
        self._rows = [_row(c) for c in project.conversations()] if project is not None else []
        self._row_of = {r.conversation_id: i for i, r in enumerate(self._rows)}
        self.endResetModel()

    def refresh(self, project: Project, ids: Iterable[int]) -> None:
        """Re-read the given conversations after they changed."""
        for cid in ids:
            row = self._row_of.get(cid)
            if row is None:
                continue
            self._rows[row] = _row(project.get(cid))
            index = self.index(row)
            self.dataChanged.emit(index, index)

    def row_of(self, conversation_id: int) -> int:
        return self._row_of.get(conversation_id, -1)

    def id_at(self, row: int) -> int | None:
        return self._rows[row].conversation_id if 0 <= row < len(self._rows) else None

    def status_at(self, row: int) -> str | None:
        return self._rows[row].status if 0 <= row < len(self._rows) else None

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role in (self.PreviewRole, Qt.ItemDataRole.DisplayRole):
            return row.preview
        if role == self.IdRole:
            return row.conversation_id
        if role == self.TurnsRole:
            return row.turns
        if role == self.StatusRole:
            return row.status
        if role == self.TagsRole:
            return list(row.tags)
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return self._ROLE_NAMES


@dataclass(frozen=True)
class _MessageRow:
    role: str
    content: str
    editable: bool
    issue: str


def _message_rows(conversation: Conversation | None, issues: Iterable[Issue]) -> list[_MessageRow]:
    if conversation is None:
        return []
    by_index: dict[int, list[str]] = {}
    for issue in issues:
        if issue.index is not None:
            by_index.setdefault(issue.index, []).append(issue.message)
    rows = []
    for i, msg in enumerate(conversation.messages):
        editable = isinstance(msg.content, str)
        text = msg.content if editable else json.dumps(msg.content, ensure_ascii=False, indent=2)
        rows.append(_MessageRow(msg.role, text, editable, "; ".join(by_index.get(i, []))))
    return rows


class MessageListModel(QAbstractListModel):
    """The messages of the selected conversation."""

    RoleRole = Qt.ItemDataRole.UserRole + 1
    ContentRole = Qt.ItemDataRole.UserRole + 2
    EditableRole = Qt.ItemDataRole.UserRole + 3
    IssueRole = Qt.ItemDataRole.UserRole + 4

    _ROLE_NAMES = {
        RoleRole: QByteArray(b"role"),
        ContentRole: QByteArray(b"content"),
        EditableRole: QByteArray(b"editable"),
        IssueRole: QByteArray(b"issue"),
    }

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[_MessageRow] = []

    def reset(self, conversation: Conversation | None, issues: Iterable[Issue] = ()) -> None:
        self.beginResetModel()
        self._rows = _message_rows(conversation, issues)
        self.endResetModel()

    def update(self, conversation: Conversation, issues: Iterable[Issue] = ()) -> None:
        """Refresh after an edit. Keeps delegates alive when the shape is unchanged,
        so a text field the user is moving into is not destroyed."""
        rows = _message_rows(conversation, issues)
        if len(rows) != len(self._rows):
            self.reset(conversation, issues)
            return
        changed = [i for i, (old, new) in enumerate(zip(self._rows, rows)) if old != new]
        self._rows = rows
        for i in changed:
            index = self.index(i)
            self.dataChanged.emit(index, index)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role in (self.ContentRole, Qt.ItemDataRole.DisplayRole):
            return row.content
        if role == self.RoleRole:
            return row.role
        if role == self.EditableRole:
            return row.editable
        if role == self.IssueRole:
            return row.issue
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return self._ROLE_NAMES
