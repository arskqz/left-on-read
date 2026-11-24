import json

import pytest

from dataformatter.core.model import Message
from dataformatter.core.schema import (
    OPENAI,
    SHAREGPT,
    UNSLOTH,
    SchemaDetectionError,
    SchemaSpec,
    detect_schema,
)


def test_detects_each_schema():
    assert detect_schema([{"conversations": [{"role": "user", "content": "hi"}]}]) is UNSLOTH
    assert detect_schema([{"messages": [{"role": "user", "content": "hi"}]}]) is OPENAI
    assert detect_schema([{"conversations": [{"from": "human", "value": "hi"}]}]) is SHAREGPT


def test_empty_file_is_ambiguous():
    with pytest.raises(SchemaDetectionError) as e:
        detect_schema([])
    assert set(e.value.candidates) == {UNSLOTH, OPENAI, SHAREGPT}


def test_empty_conversations_are_ambiguous():
    with pytest.raises(SchemaDetectionError) as e:
        detect_schema([{"conversations": []}])
    assert set(e.value.candidates) == {UNSLOTH, SHAREGPT}


def test_mixed_items_match_nothing():
    items = [{"messages": [{"role": "user", "content": "a"}]}, {"conversations": [{"from": "human", "value": "b"}]}]
    with pytest.raises(SchemaDetectionError) as e:
        detect_schema(items)
    assert e.value.candidates == []


def test_sharegpt_roles_are_mapped_at_the_boundary():
    item = {
        "conversations": [
            {"from": "system", "value": "s"},
            {"from": "human", "value": "hi"},
            {"from": "gpt", "value": "yo", "weight": 0},
        ]
    }
    conv = SHAREGPT.item_to_conversation(item)
    assert [m.role for m in conv.messages] == ["system", "user", "assistant"]
    assert conv.messages[2].extra == {"weight": 0}
    assert SHAREGPT.conversation_to_item(conv) == item


@pytest.mark.parametrize(
    "item",
    [
        # Keys in unusual order, extra keys at both levels.
        {"id": 7, "messages": [{"content": "hi", "role": "user", "name": "x"}], "meta": {"a": [1, 2]}},
        # Missing content key and null content (tool-call style).
        {"messages": [{"role": "assistant", "tool_calls": []}, {"role": "assistant", "content": None}]},
    ],
)
def test_conversion_keeps_key_order_and_extras(item):
    back = OPENAI.conversation_to_item(OPENAI.item_to_conversation(item))
    assert json.dumps(back) == json.dumps(item)


def test_unmappable_role_value_is_written_back_unchanged():
    # "user" is not a ShareGPT role, but must not turn into "human" on export.
    item = {"conversations": [{"from": "user", "value": "hi"}, {"from": "gpt", "value": "yo"}]}
    conv = SHAREGPT.item_to_conversation(item)
    assert conv.messages[0].role == "user"
    assert SHAREGPT.conversation_to_item(conv) == item


def test_new_messages_use_schema_spelling():
    conv = SHAREGPT.item_to_conversation({"conversations": []})
    conv.messages.append(Message("assistant", "new"))
    assert SHAREGPT.conversation_to_item(conv) == {"conversations": [{"from": "gpt", "value": "new"}]}


def test_spec_dict_round_trip():
    assert SchemaSpec.from_dict(json.loads(json.dumps(SHAREGPT.to_dict()))) == SHAREGPT
