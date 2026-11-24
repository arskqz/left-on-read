"""Internal data model: conversations, messages and validation.

Everything here uses the internal representation: ``role``/``content`` with
system / user / assistant roles. Mapping to and from the spelling used in a
file happens only at the file boundary, in :mod:`leftonread.core.schema`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SYSTEM, USER, ASSISTANT = "system", "user", "assistant"
ROLES = (SYSTEM, USER, ASSISTANT)

UNREVIEWED, KEEP, ARCHIVE = "unreviewed", "keep", "archive"
STATUSES = (UNREVIEWED, KEEP, ARCHIVE)

# Quick picks offered after archiving. Any other text is allowed too.
ARCHIVE_REASONS = ("repetitive", "out of character", "broken", "other")


@dataclass
class Message:
    role: str
    # Usually a string. Other JSON values (null, a list of content parts, ...)
    # are carried through untouched; validation warns about them.
    content: Any
    extra: dict[str, Any] = field(default_factory=dict)  # other keys, in original order

    # Round-trip hints. They are only needed to write the source file back
    # byte for byte and can be left as None for messages created in the app.
    key_order: list[str] | None = None  # key order of the original object
    file_role: str | None = None  # original role value, if the schema's role map can't reproduce it

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.extra:
            record["extra"] = self.extra
        if self.key_order is not None:
            record["key_order"] = self.key_order
        if self.file_role is not None:
            record["file_role"] = self.file_role
        return record

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Message:
        return cls(
            role=record["role"],
            content=record.get("content"),
            extra=record.get("extra", {}),
            key_order=record.get("key_order"),
            file_role=record.get("file_role"),
        )


@dataclass
class Conversation:
    messages: list[Message] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)  # other keys of the item, in original order
    id: int | None = None  # stable, assigned on import

    # Project-only state. Never written to an exported dataset.
    status: str = UNREVIEWED
    archive_reason: str | None = None
    tags: set[str] = field(default_factory=set)

    key_order: list[str] | None = None  # round-trip hint, see Message.key_order


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    index: int | None = None  # index of the offending message, if any


def validate(conversation: Conversation) -> list[Issue]:
    """Check a conversation against the usual chat-dataset rules.

    The result is a list of warnings. Nothing is ever rejected, because other
    people's data may break these rules on purpose.
    """
    messages = conversation.messages
    if not messages:
        return [Issue("no_messages", "Conversation has no messages")]

    issues: list[Issue] = []
    for i, msg in enumerate(messages):
        if msg.role not in ROLES:
            issues.append(Issue("unknown_role", f"Unknown role {msg.role!r}", i))
        if msg.role == SYSTEM and i != 0:
            issues.append(Issue("system_not_first", "System message is not the first message", i))
        if not isinstance(msg.content, str):
            issues.append(Issue("non_text_content", "Content is not plain text", i))
        elif not msg.content.strip():
            issues.append(Issue("empty_content", "Content is empty", i))

    expected = None  # None: first turn, which should be from the user
    for i, msg in enumerate(messages):
        if msg.role not in (USER, ASSISTANT):
            continue
        if expected is None and msg.role != USER:
            issues.append(Issue("not_alternating", "First turn is not from the user", i))
        elif expected is not None and msg.role != expected:
            issues.append(Issue("not_alternating", f"Two {msg.role} messages in a row", i))
        expected = ASSISTANT if msg.role == USER else USER

    if messages[-1].role != ASSISTANT:
        issues.append(Issue("last_not_assistant", "Last message is not from the assistant", len(messages) - 1))

    return issues
