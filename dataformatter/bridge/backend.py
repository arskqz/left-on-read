"""App-level backend object exposed to QML as ``backend``."""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from ..core.io import DatasetLoadError
from ..core.model import ARCHIVE, KEEP, UNREVIEWED, Conversation, validate
from ..core.project import PROJECT_SUFFIX, Project, ProjectError, SourceState
from ..core.schema import SchemaDetectionError, SchemaSpec
from ..core.stats import conversation_stats
from .models import ConversationListModel, MessageListModel
from .settings import AppSettings

_EXPORT_STATUSES = {"all": None, "keep": KEEP, "archive": ARCHIVE}


class Backend(QObject):
    projectChanged = Signal()
    stateChanged = Signal()  # counts, current conversation, undo availability
    message = Signal(str)  # something the user should read (errors, notes)
    schemaChoiceNeeded = Signal(list)  # labels; answer with importWithSchema(index)

    def __init__(self, parent: QObject | None = None, settings: AppSettings | None = None):
        super().__init__(parent)
        self._settings = settings
        self._project: Project | None = None
        self._model = ConversationListModel(self)
        self._messages = MessageListModel(self)
        self._pending: tuple[Path, Path, list[SchemaSpec]] | None = None
        self._current_row = -1
        self._current: Conversation | None = None

    # -- properties ----------------------------------------------------------

    def _conversations(self) -> QObject:
        return self._model

    def _message_model(self) -> QObject:
        return self._messages

    def _has_project(self) -> bool:
        return self._project is not None

    def _title(self) -> str:
        return self._project.path.stem if self._project else ""

    def _summary(self) -> str:
        p = self._project
        if p is None:
            return ""
        counts = p.counts()
        total = sum(counts.values())
        return (
            f"{total} conversations · {counts[KEEP]} kept · {counts[ARCHIVE]} archived"
            f" · {p.schema.label} · source: {p.source_path.name}"
        )

    def _counts(self) -> dict:
        if self._project is None:
            return {"total": 0, KEEP: 0, ARCHIVE: 0, UNREVIEWED: 0}
        counts = self._project.counts()
        return {"total": sum(counts.values()), **counts}

    def _schema_label(self) -> str:
        return self._project.schema.label if self._project else ""

    def _source_name(self) -> str:
        return self._project.source_path.name if self._project else ""

    def _reviewed_count(self) -> int:
        c = self._counts()
        return c[KEEP] + c[ARCHIVE]

    def _total_count(self) -> int:
        return self._counts()["total"]

    def _get_current_row(self) -> int:
        return self._current_row

    def _current_stats(self) -> dict:
        conv = self._current
        if conv is None:
            return {}
        stats = conversation_stats(conv)
        return {
            "id": conv.id,
            "status": conv.status,
            "archiveReason": conv.archive_reason or "",
            "tags": sorted(conv.tags),
            "turns": stats["turns"],
            "messages": stats["messages"],
            "words": stats["words"],
            "chars": stats["chars"],
            "roles": [{"role": role, **counts} for role, counts in stats["roles"].items() if counts["messages"]],
            "issues": [i.message for i in validate(conv)],
        }

    def _can_undo(self) -> bool:
        return self._project is not None and self._project.can_undo

    conversations = Property(QObject, _conversations, constant=True)
    messages = Property(QObject, _message_model, constant=True)
    hasProject = Property(bool, _has_project, notify=projectChanged)
    title = Property(str, _title, notify=projectChanged)
    schemaLabel = Property(str, _schema_label, notify=projectChanged)
    sourceName = Property(str, _source_name, notify=projectChanged)
    summary = Property(str, _summary, notify=stateChanged)
    counts = Property("QVariantMap", _counts, notify=stateChanged)
    reviewedCount = Property(int, _reviewed_count, notify=stateChanged)
    totalCount = Property(int, _total_count, notify=stateChanged)
    currentRow = Property(int, _get_current_row, notify=stateChanged)
    currentStats = Property("QVariantMap", _current_stats, notify=stateChanged)
    canUndo = Property(bool, _can_undo, notify=stateChanged)

    # -- project slots -------------------------------------------------------

    @Slot(QUrl, result=QUrl)
    def suggestProjectUrl(self, source_url: QUrl) -> QUrl:
        return QUrl.fromLocalFile(str(Path(source_url.toLocalFile()).with_suffix(PROJECT_SUFFIX)))

    @Slot(QUrl, QUrl)
    def newProject(self, source_url: QUrl, project_url: QUrl) -> None:
        target = Path(project_url.toLocalFile())
        if target.suffix != PROJECT_SUFFIX:
            target = target.with_name(target.name + PROJECT_SUFFIX)
        self._create(Path(source_url.toLocalFile()), target, None)

    @Slot(int)
    def importWithSchema(self, index: int) -> None:
        if self._pending is None:
            return
        source, target, candidates = self._pending
        self._pending = None
        if 0 <= index < len(candidates):
            self._create(source, target, candidates[index])

    @Slot(QUrl)
    def openProject(self, url: QUrl) -> None:
        path = Path(url.toLocalFile())
        try:
            project = Project.open(path)
        except ProjectError as e:
            self.message.emit(str(e))
            return
        self._set_project(project)
        state = project.check_source()
        if state is SourceState.CHANGED:
            self.message.emit(f"The source file {project.source_path.name} has changed since it was imported.")
        elif state is SourceState.MISSING:
            self.message.emit(f"The source file was not found at {project.source_path}.")

    @Slot(QUrl, str)
    def exportTo(self, url: QUrl, which: str) -> None:
        if self._project is None:
            return
        path = Path(url.toLocalFile())
        try:
            count = self._project.export(path, _EXPORT_STATUSES[which])
        except (ProjectError, OSError) as e:
            self.message.emit(f"Export failed: {e}")
            return
        self.message.emit(f"Exported {count} conversations to {path.name}.")

    @Slot()
    def close(self) -> None:
        self._set_project(None)

    # -- review slots --------------------------------------------------------

    @Slot(int)
    def setCurrentRow(self, row: int) -> None:
        if self._project is None or not 0 <= row < self._model.rowCount():
            return
        if row != self._current_row:
            self._select(row)

    @Slot()
    def keep(self) -> None:
        self._decide(KEEP)

    @Slot()
    def archive(self) -> None:
        self._decide(ARCHIVE)

    @Slot()
    def skip(self) -> None:
        if self._current_row >= 0:
            self._select(self._next_unreviewed_row())

    @Slot()
    def undo(self) -> None:
        if self._project is None:
            return
        ids = self._project.undo()
        if not ids:
            return
        self._model.refresh(self._project, ids)
        row = self._model.row_of(ids[0])
        self._select(row if row >= 0 else self._current_row)

    @Slot(int, str)
    def setMessageContent(self, index: int, text: str) -> None:
        """Save new text for one message of the current conversation."""
        conv = self._current
        if self._project is None or conv is None or not 0 <= index < len(conv.messages):
            return
        old = conv.messages[index].content
        if not isinstance(old, str) or old == text:
            return
        edited = copy.deepcopy(conv)
        edited.messages[index].content = text
        self._save_edit(edited)

    @Slot(int)
    def deleteMessage(self, index: int) -> None:
        """Remove one turn from the current conversation (undoable)."""
        conv = self._current
        if self._project is None or conv is None or not 0 <= index < len(conv.messages):
            return
        edited = copy.deepcopy(conv)
        del edited.messages[index]
        self._save_edit(edited)

    def _save_edit(self, edited: Conversation) -> None:
        issues = self._project.update_conversation(edited)
        self._current = self._project.get(edited.id)
        self._model.refresh(self._project, [edited.id])
        self._messages.update(self._current, issues)
        self.stateChanged.emit()

    # -- helpers -------------------------------------------------------------

    def _decide(self, status: str) -> None:
        conv = self._current
        if self._project is None or conv is None:
            return
        self._project.set_status(conv.id, status)
        self._model.refresh(self._project, [conv.id])
        self._select(self._next_unreviewed_row())

    def _next_unreviewed_row(self) -> int:
        """First unreviewed row after the current one, wrapping; else the next row."""
        count = self._model.rowCount()
        start = self._current_row
        for step in range(1, count + 1):
            row = (start + step) % count
            if row != start and self._model.status_at(row) == UNREVIEWED:
                return row
        return min(start + 1, count - 1)

    def _select(self, row: int) -> None:
        cid = self._model.id_at(row)
        if self._project is None or cid is None:
            self._current_row = -1
            self._current = None
            self._messages.reset(None)
        else:
            self._current_row = row
            self._current = self._project.get(cid)
            self._messages.reset(self._current, validate(self._current))
        self.stateChanged.emit()

    def _create(self, source: Path, target: Path, schema: SchemaSpec | None) -> None:
        try:
            project = Project.create(target, source, schema)
        except SchemaDetectionError as e:
            if e.candidates:
                self._pending = (source, target, e.candidates)
                self.schemaChoiceNeeded.emit([c.label for c in e.candidates])
            else:
                self.message.emit(str(e))
            return
        except (DatasetLoadError, ProjectError, OSError) as e:
            self.message.emit(f"Could not import {source.name}: {e}")
            return
        self._set_project(project)
        if not project.roundtrip_exact:
            self.message.emit(
                "This file's formatting could not be reproduced exactly. "
                "Exports will contain the same data, but the formatting may differ."
            )

    def _set_project(self, project: Project | None) -> None:
        if self._project is not None:
            self._project.close()
        self._project = project
        self._model.reset(project)
        self._current_row = -1
        if project is not None:
            if self._settings is not None:
                self._settings.add_recent(project.path)
            first = next(
                (r for r in range(self._model.rowCount()) if self._model.status_at(r) == UNREVIEWED),
                0,
            )
            self._select(first)
        else:
            self._select(-1)
        self.projectChanged.emit()
