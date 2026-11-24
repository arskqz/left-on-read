"""Dataset schemas: how conversations and messages are spelled in a file.

A :class:`SchemaSpec` describes one spelling (list key, message field names,
role values). The schema is detected on import, stored in the project and
used again on export, so a file always comes back in the shape it came in.
Adding a schema means adding one ``SchemaSpec`` to :data:`SCHEMAS`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from .model import Conversation, Message


class SchemaDetectionError(ValueError):
    """The schema could not be decided. ``candidates`` lists the schemas that fit."""

    def __init__(self, message: str, candidates: Sequence[SchemaSpec]):
        super().__init__(message)
        self.candidates = list(candidates)


@dataclass(frozen=True)
class SchemaSpec:
    name: str
    label: str
    list_key: str
    role_field: str = "role"
    content_field: str = "content"
    # (file role, internal role) pairs. Roles not listed pass through unchanged.
    role_map: tuple[tuple[str, str], ...] = ()

    # -- roles ---------------------------------------------------------------

    def role_to_internal(self, role: Any) -> Any:
        for file_role, internal in self.role_map:
            if file_role == role:
                return internal
        return role

    def role_to_file(self, role: Any) -> Any:
        for file_role, internal in self.role_map:
            if internal == role:
                return file_role
        return role

    # -- detection -----------------------------------------------------------

    def matches(self, item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        messages = item.get(self.list_key)
        return isinstance(messages, list) and all(
            isinstance(m, dict) and self.role_field in m for m in messages
        )

    def first_mismatch(self, items: Sequence[Any]) -> int | None:
        return next((i for i, item in enumerate(items) if not self.matches(item)), None)

    # -- conversion ----------------------------------------------------------

    def item_to_conversation(self, item: dict[str, Any], id: int | None = None) -> Conversation:
        return Conversation(
            messages=[self._message_in(m) for m in item[self.list_key]],
            extra={k: v for k, v in item.items() if k != self.list_key},
            id=id,
            key_order=list(item),
        )

    def conversation_to_item(self, conversation: Conversation) -> dict[str, Any]:
        values = dict(conversation.extra)
        values[self.list_key] = [self._message_out(m) for m in conversation.messages]
        return _ordered(values, conversation.key_order, default_first=(self.list_key,))

    def _message_in(self, raw: dict[str, Any]) -> Message:
        file_role = raw[self.role_field]
        role = self.role_to_internal(file_role)
        return Message(
            role=role,
            content=raw.get(self.content_field),
            extra={k: v for k, v in raw.items() if k not in (self.role_field, self.content_field)},
            key_order=list(raw),
            file_role=file_role if self.role_to_file(role) != file_role else None,
        )

    def _message_out(self, msg: Message) -> dict[str, Any]:
        values = dict(msg.extra)
        if msg.file_role is not None and self.role_to_internal(msg.file_role) == msg.role:
            values[self.role_field] = msg.file_role
        else:
            values[self.role_field] = self.role_to_file(msg.role)
        # A missing content key stays missing (e.g. OpenAI tool-call messages).
        if msg.content is not None or msg.key_order is None or self.content_field in msg.key_order:
            values[self.content_field] = msg.content
        return _ordered(values, msg.key_order, default_first=(self.role_field, self.content_field))

    # -- persistence ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchemaSpec:
        data = dict(data)
        data["role_map"] = tuple(tuple(pair) for pair in data.get("role_map", ()))
        return cls(**data)


def _ordered(values: dict[str, Any], key_order: list[str] | None, default_first: tuple[str, ...]) -> dict[str, Any]:
    """Return ``values`` with keys in ``key_order`` first, then any new keys."""
    out: dict[str, Any] = {}
    for key in key_order if key_order is not None else default_first:
        if key in values:
            out[key] = values[key]
    for key, value in values.items():
        out.setdefault(key, value)
    return out


UNSLOTH = SchemaSpec(
    name="unsloth",
    label="Role/content under 'conversations' (Unsloth)",
    list_key="conversations",
)
OPENAI = SchemaSpec(
    name="openai",
    label="OpenAI messages",
    list_key="messages",
)
SHAREGPT = SchemaSpec(
    name="sharegpt",
    label="ShareGPT (from/value)",
    list_key="conversations",
    role_field="from",
    content_field="value",
    role_map=(("human", "user"), ("gpt", "assistant")),
)

SCHEMAS: tuple[SchemaSpec, ...] = (UNSLOTH, OPENAI, SHAREGPT)


def get_schema(name: str) -> SchemaSpec:
    for spec in SCHEMAS:
        if spec.name == name:
            return spec
    raise KeyError(name)


def candidate_schemas(items: Sequence[Any]) -> list[SchemaSpec]:
    return [spec for spec in SCHEMAS if spec.first_mismatch(items) is None]


def detect_schema(items: Sequence[Any]) -> SchemaSpec:
    """Return the one schema that fits every item, or raise SchemaDetectionError."""
    if not items:
        raise SchemaDetectionError("The file has no conversations, so its schema can't be detected.", SCHEMAS)
    candidates = candidate_schemas(items)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        names = ", ".join(c.label for c in candidates)
        raise SchemaDetectionError(f"More than one schema fits this file: {names}.", candidates)
    closest = max(SCHEMAS, key=lambda s: s.first_mismatch(items) or 0)
    raise SchemaDetectionError(
        f"No supported schema fits every conversation. Closest is {closest.label}, "
        f"which fails at item {closest.first_mismatch(items)}.",
        [],
    )
