"""The project file: a SQLite database holding one imported dataset.

    source.json ──import──▶ name.dsproj ──export──▶ keep.json / archive.json
    (never modified)        (edits, status, tags,   (clean: same schema and
                             undo history)            format as the source)

Every change is committed immediately and recorded in ``history`` as a
before/after snapshot of the conversation, so anything can be undone. Changes
made inside :meth:`Project.batch` form one undo step.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from . import io
from .io import FileFormat
from .model import ARCHIVE, STATUSES, Conversation, Issue, Message, validate
from .schema import SchemaSpec

SCHEMA_VERSION = 1
PROJECT_SUFFIX = ".dsproj"

_DDL = """
CREATE TABLE project (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE conversations (
    id             INTEGER PRIMARY KEY,
    source_index   INTEGER,              -- position in the source file; NULL if created in the app
    data_json      TEXT NOT NULL,        -- messages
    extra_json     TEXT NOT NULL,        -- other item keys + round-trip hints
    status         TEXT NOT NULL DEFAULT 'unreviewed'
                   CHECK (status IN ('unreviewed', 'keep', 'archive')),
    archive_reason TEXT,
    updated_at     TEXT NOT NULL
);
CREATE INDEX conversations_status ON conversations(status);

CREATE TABLE tags (
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tag             TEXT NOT NULL,
    PRIMARY KEY (conversation_id, tag)
);
CREATE INDEX tags_tag ON tags(tag);

CREATE TABLE history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        INTEGER NOT NULL,    -- one undo step
    conversation_id INTEGER NOT NULL,
    action          TEXT NOT NULL,
    before_json     TEXT,                -- NULL: conversation did not exist
    after_json      TEXT,
    ts              TEXT NOT NULL
);
CREATE INDEX history_group ON history(group_id);

CREATE VIRTUAL TABLE messages_fts USING fts5(
    conversation_id UNINDEXED,
    role UNINDEXED,
    content,
    tokenize = 'unicode61 remove_diacritics 0'
);
"""

_ORDER = "ORDER BY source_index IS NULL, source_index, id"


class ProjectError(Exception):
    pass


class SourceState(Enum):
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    MISSING = "missing"


class Project:
    """An open project file. Use :meth:`create` or :meth:`open`, then :meth:`close`."""

    def __init__(self, path: Path, conn: sqlite3.Connection):
        self.path = path
        self._conn = conn
        self._group: int | None = None
        self._meta: dict[str, str] = dict(conn.execute("SELECT key, value FROM project"))

    # -- lifecycle -----------------------------------------------------------

    @classmethod
    def create(cls, path: str | Path, source: str | Path, schema: SchemaSpec | None = None) -> Project:
        """Import ``source`` into a new project file at ``path``.

        Raises the errors of :func:`dataformatter.core.io.load`; on
        SchemaDetectionError, ask the user and call again with ``schema``.
        """
        path = Path(path)
        source = Path(source).resolve()
        if path.exists():
            raise ProjectError(f"{path} already exists.")

        dataset = io.load(source, schema)
        conn = _connect(path)
        try:
            conn.executescript(_DDL)
            now = _now()
            meta = {
                "schema_version": str(SCHEMA_VERSION),
                "source_path": str(source),
                "source_hash": dataset.sha256,
                "schema": json.dumps(dataset.schema.to_dict()),
                "format": json.dumps(dataset.format.to_dict()),
                "roundtrip_exact": "1" if dataset.exact else "0",
                "created_at": now,
            }
            with conn:
                conn.executemany("INSERT INTO project (key, value) VALUES (?, ?)", meta.items())
                for index, conv in enumerate(dataset.conversations):
                    data_json, extra_json = _encode(conv)
                    conn.execute(
                        "INSERT INTO conversations (id, source_index, data_json, extra_json, updated_at)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (conv.id, index, data_json, extra_json, now),
                    )
                    _index_messages(conn, conv.id, conv.messages)
        except BaseException:
            conn.close()
            path.unlink(missing_ok=True)
            raise
        return cls(path, conn)

    @classmethod
    def open(cls, path: str | Path) -> Project:
        path = Path(path)
        if not path.is_file():
            raise ProjectError(f"{path} does not exist.")
        conn = _connect(path)
        try:
            row = conn.execute("SELECT value FROM project WHERE key = 'schema_version'").fetchone()
        except sqlite3.DatabaseError as e:
            conn.close()
            raise ProjectError(f"{path} is not a project file.") from e
        if row is None or int(row[0]) != SCHEMA_VERSION:
            conn.close()
            raise ProjectError(f"{path} has an unsupported project version.")
        return cls(path, conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Project:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- metadata ------------------------------------------------------------

    @property
    def source_path(self) -> Path:
        return Path(self._meta["source_path"])

    @property
    def schema(self) -> SchemaSpec:
        return SchemaSpec.from_dict(json.loads(self._meta["schema"]))

    @property
    def format(self) -> FileFormat:
        return FileFormat.from_dict(json.loads(self._meta["format"]))

    @property
    def roundtrip_exact(self) -> bool:
        """Whether an unedited export reproduces the source byte for byte."""
        return self._meta["roundtrip_exact"] == "1"

    def check_source(self) -> SourceState:
        """Has the source file changed since import?"""
        if not self.source_path.is_file():
            return SourceState.MISSING
        if io.file_sha256(self.source_path) != self._meta["source_hash"]:
            return SourceState.CHANGED
        return SourceState.UNCHANGED

    # -- reading -------------------------------------------------------------

    def count(self, statuses: str | Iterable[str] | None = None) -> int:
        where, params = _status_filter(statuses)
        return self._conn.execute(f"SELECT COUNT(*) FROM conversations {where}", params).fetchone()[0]

    def counts(self) -> dict[str, int]:
        result = dict.fromkeys(STATUSES, 0)
        result.update(self._conn.execute("SELECT status, COUNT(*) FROM conversations GROUP BY status"))
        return result

    def ids(self, statuses: str | Iterable[str] | None = None) -> list[int]:
        where, params = _status_filter(statuses)
        return [r[0] for r in self._conn.execute(f"SELECT id FROM conversations {where} {_ORDER}", params)]

    def get(self, conversation_id: int) -> Conversation:
        row = self._conn.execute(
            "SELECT id, data_json, extra_json, status, archive_reason FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            raise KeyError(conversation_id)
        tags = {r[0] for r in self._conn.execute("SELECT tag FROM tags WHERE conversation_id = ?", (conversation_id,))}
        return _decode(row, tags)

    def conversations(self, statuses: str | Iterable[str] | None = None) -> Iterator[Conversation]:
        tags: dict[int, set[str]] = {}
        for cid, tag in self._conn.execute("SELECT conversation_id, tag FROM tags"):
            tags.setdefault(cid, set()).add(tag)
        where, params = _status_filter(statuses)
        rows = self._conn.execute(
            f"SELECT id, data_json, extra_json, status, archive_reason FROM conversations {where} {_ORDER}", params
        )
        for row in rows:
            yield _decode(row, tags.get(row[0], set()))

    def validate_all(self) -> dict[int, list[Issue]]:
        return {c.id: issues for c in self.conversations() if (issues := validate(c))}

    # -- changing ------------------------------------------------------------

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Group the changes made inside into one transaction and one undo step."""
        if self._group is not None:
            yield
            return
        self._group = self._conn.execute("SELECT COALESCE(MAX(group_id), 0) + 1 FROM history").fetchone()[0]
        try:
            with self._conn:
                yield
        finally:
            self._group = None

    def update_conversation(self, conversation: Conversation) -> list[Issue]:
        """Save edited messages / extra keys. Status and tags are not touched.

        Returns validation warnings for the saved conversation.
        """
        if conversation.id is None:
            raise ValueError("Conversation has no id.")
        data_json, extra_json = _encode(conversation)

        def mutate() -> None:
            self._conn.execute(
                "UPDATE conversations SET data_json = ?, extra_json = ?, updated_at = ? WHERE id = ?",
                (data_json, extra_json, _now(), conversation.id),
            )
            _index_messages(self._conn, conversation.id, conversation.messages)

        self._change(conversation.id, "edit", mutate)
        return validate(conversation)

    def set_status(self, conversation_id: int, status: str, reason: str | None = None) -> None:
        """Set keep / archive / unreviewed. ``reason`` is kept only for archive."""
        _check_status(status)
        reason = reason if status == ARCHIVE else None
        self._change(
            conversation_id,
            "status",
            lambda: self._conn.execute(
                "UPDATE conversations SET status = ?, archive_reason = ?, updated_at = ? WHERE id = ?",
                (status, reason, _now(), conversation_id),
            ),
        )

    def add_tag(self, conversation_id: int, tag: str) -> None:
        tag = _clean_tag(tag)
        self._change(
            conversation_id,
            "tag",
            lambda: self._conn.execute(
                "INSERT OR IGNORE INTO tags (conversation_id, tag) VALUES (?, ?)", (conversation_id, tag)
            ),
        )

    def remove_tag(self, conversation_id: int, tag: str) -> None:
        tag = _clean_tag(tag)
        self._change(
            conversation_id,
            "untag",
            lambda: self._conn.execute(
                "DELETE FROM tags WHERE conversation_id = ? AND tag = ?", (conversation_id, tag)
            ),
        )

    @property
    def can_undo(self) -> bool:
        return self._conn.execute("SELECT EXISTS (SELECT 1 FROM history)").fetchone()[0] == 1

    def undo(self) -> list[int]:
        """Undo the last change (or batch). Returns the affected conversation ids."""
        with self._conn:
            group = self._conn.execute("SELECT MAX(group_id) FROM history").fetchone()[0]
            if group is None:
                return []
            rows = self._conn.execute(
                "SELECT conversation_id, before_json FROM history WHERE group_id = ? ORDER BY id DESC", (group,)
            ).fetchall()
            for cid, before in rows:
                self._restore(cid, json.loads(before) if before is not None else None)
            self._conn.execute("DELETE FROM history WHERE group_id = ?", (group,))
        return sorted({cid for cid, _ in rows})

    def _change(self, conversation_id: int, action: str, mutate: Callable[[], Any]) -> None:
        with self.batch():
            before = self._snapshot(conversation_id)
            if before is None:
                raise KeyError(conversation_id)
            mutate()
            after = self._snapshot(conversation_id)
            if after != before:
                self._conn.execute(
                    "INSERT INTO history (group_id, conversation_id, action, before_json, after_json, ts)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (self._group, conversation_id, action, json.dumps(before), json.dumps(after), _now()),
                )

    def _snapshot(self, conversation_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT data_json, extra_json, status, archive_reason FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        tags = [r[0] for r in self._conn.execute(
            "SELECT tag FROM tags WHERE conversation_id = ? ORDER BY tag", (conversation_id,)
        )]
        return {"data": row[0], "extra": row[1], "status": row[2], "archive_reason": row[3], "tags": tags}

    def _restore(self, conversation_id: int, snapshot: dict[str, Any] | None) -> None:
        if snapshot is None:
            self._conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            _index_messages(self._conn, conversation_id, [])
            return
        self._conn.execute(
            "UPDATE conversations SET data_json = ?, extra_json = ?, status = ?, archive_reason = ?, updated_at = ?"
            " WHERE id = ?",
            (snapshot["data"], snapshot["extra"], snapshot["status"], snapshot["archive_reason"], _now(),
             conversation_id),
        )
        self._conn.execute("DELETE FROM tags WHERE conversation_id = ?", (conversation_id,))
        self._conn.executemany(
            "INSERT INTO tags (conversation_id, tag) VALUES (?, ?)", [(conversation_id, t) for t in snapshot["tags"]]
        )
        messages = [Message.from_record(r) for r in json.loads(snapshot["data"])]
        _index_messages(self._conn, conversation_id, messages)

    # -- export --------------------------------------------------------------

    def export(self, path: str | Path, statuses: str | Iterable[str] | None = None) -> int:
        """Write the conversations with the given statuses (all if None) to ``path``.

        The output uses the source's schema and formatting and contains no
        project-only data (status, tags, archive reasons). Returns the count.
        """
        path = Path(path)
        if path.resolve() == self.source_path.resolve():
            raise ProjectError("Refusing to overwrite the source file.")
        conversations = list(self.conversations(statuses))
        io.save(path, conversations, self.schema, self.format)
        return len(conversations)


# -- helpers ------------------------------------------------------------------


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_status(status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}; expected one of {STATUSES}.")


def _clean_tag(tag: str) -> str:
    tag = tag.strip()
    if not tag:
        raise ValueError("Tag is empty.")
    return tag


def _status_filter(statuses: str | Iterable[str] | None) -> tuple[str, list[str]]:
    if statuses is None:
        return "", []
    wanted = [statuses] if isinstance(statuses, str) else list(statuses)
    for status in wanted:
        _check_status(status)
    return f"WHERE status IN ({', '.join('?' * len(wanted))})", wanted


def _encode(conv: Conversation) -> tuple[str, str]:
    data = [m.to_record() for m in conv.messages]
    extra = {"extra": conv.extra, "key_order": conv.key_order}
    return _dumps(data), _dumps(extra)


def _decode(row: tuple, tags: set[str]) -> Conversation:
    cid, data_json, extra_json, status, archive_reason = row
    extra = json.loads(extra_json)
    return Conversation(
        messages=[Message.from_record(r) for r in json.loads(data_json)],
        extra=extra["extra"],
        id=cid,
        status=status,
        archive_reason=archive_reason,
        tags=set(tags),
        key_order=extra["key_order"],
    )


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# Search rows get rowid = conversation_id << 20 | message index, so all rows of
# one conversation form a rowid range: deleting them is an indexed range
# lookup instead of a scan of the whole FTS table.
_FTS_SHIFT = 20


def _index_messages(conn: sqlite3.Connection, conversation_id: int, messages: list[Message]) -> None:
    first = conversation_id << _FTS_SHIFT
    conn.execute("DELETE FROM messages_fts WHERE rowid BETWEEN ? AND ?", (first, first + (1 << _FTS_SHIFT) - 1))
    conn.executemany(
        "INSERT INTO messages_fts (rowid, conversation_id, role, content) VALUES (?, ?, ?, ?)",
        [
            (first + i, conversation_id, str(m.role), m.content)
            for i, m in enumerate(messages[: 1 << _FTS_SHIFT])
            if isinstance(m.content, str)
        ],
    )
