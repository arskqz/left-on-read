"""Statistics over conversations. Plain Python, no Qt."""

from __future__ import annotations

from typing import Any

from .model import ROLES, SYSTEM, Conversation


def conversation_stats(conversation: Conversation) -> dict[str, Any]:
    """Message, character and word counts for one conversation, per role.

    Non-text content counts as a message but adds no characters or words.
    Roles outside system / user / assistant are counted under their own name.
    """
    per_role: dict[str, dict[str, int]] = {role: {"messages": 0, "chars": 0, "words": 0} for role in ROLES}
    for msg in conversation.messages:
        bucket = per_role.setdefault(msg.role, {"messages": 0, "chars": 0, "words": 0})
        bucket["messages"] += 1
        if isinstance(msg.content, str):
            bucket["chars"] += len(msg.content)
            bucket["words"] += len(msg.content.split())

    return {
        "turns": sum(1 for m in conversation.messages if m.role != SYSTEM),
        "messages": len(conversation.messages),
        "chars": sum(b["chars"] for b in per_role.values()),
        "words": sum(b["words"] for b in per_role.values()),
        "roles": per_role,
    }
