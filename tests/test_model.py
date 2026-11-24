from dataformatter.core.model import Conversation, Message, validate


def conv(*pairs):
    return Conversation(messages=[Message(role, content) for role, content in pairs])


def codes(c):
    return [i.code for i in validate(c)]


def test_valid_conversation_has_no_issues():
    assert validate(conv(("system", "s"), ("user", "hi"), ("assistant", "hello"))) == []
    assert validate(conv(("user", "hi"), ("assistant", "hello"))) == []


def test_empty_conversation():
    assert codes(Conversation()) == ["no_messages"]


def test_alternation_and_ending():
    issues = validate(conv(("user", "a"), ("user", "b"), ("assistant", "c"), ("user", "d")))
    assert [(i.code, i.index) for i in issues] == [("not_alternating", 1), ("last_not_assistant", 3)]


def test_must_start_with_user():
    assert "not_alternating" in codes(conv(("system", "s"), ("assistant", "hi")))


def test_role_and_content_problems():
    c = conv(("user", "  "), ("assistant", None), ("narrator", "x"), ("system", "late"), ("assistant", "ok"))
    found = codes(c)
    for code in ("empty_content", "non_text_content", "unknown_role", "system_not_first"):
        assert code in found
