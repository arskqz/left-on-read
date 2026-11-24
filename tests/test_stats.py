from leftonread.core.model import Conversation, Message
from leftonread.core.stats import conversation_stats


def test_conversation_stats_counts_per_role():
    conv = Conversation(
        messages=[
            Message("system", "Be nice."),
            Message("user", "Hello there"),
            Message("assistant", "Hi! How are you?"),
            Message("tool", None),
        ]
    )
    stats = conversation_stats(conv)

    assert stats["messages"] == 4
    assert stats["turns"] == 3
    assert stats["roles"]["user"] == {"messages": 1, "chars": 11, "words": 2}
    assert stats["roles"]["assistant"]["words"] == 4
    assert stats["roles"]["tool"] == {"messages": 1, "chars": 0, "words": 0}
    assert stats["words"] == 2 + 2 + 4
    assert stats["chars"] == len("Be nice.") + 11 + len("Hi! How are you?")


def test_conversation_stats_empty():
    stats = conversation_stats(Conversation())
    assert stats["messages"] == 0 and stats["turns"] == 0 and stats["words"] == 0
