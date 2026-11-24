import json
import os
from pathlib import Path

import pytest

from conftest import SAMPLE_FILES
from dataformatter.core import io
from dataformatter.core.io import DatasetLoadError, FileFormat
from dataformatter.core.schema import OPENAI, SchemaDetectionError


def roundtrip(path: Path, out: Path) -> io.Dataset:
    dataset = io.load(path)
    io.save(out, dataset.conversations, dataset.schema, dataset.format)
    return dataset


@pytest.mark.parametrize("sample", SAMPLE_FILES, ids=lambda p: p.name)
def test_samples_round_trip_byte_identically(sample, tmp_path):
    out = tmp_path / sample.name
    dataset = roundtrip(sample, out)
    assert dataset.exact
    assert out.read_bytes() == sample.read_bytes()


FORMAT_VARIANTS = [
    FileFormat(indent=2),
    FileFormat(indent=4),
    FileFormat(indent="\t"),
    FileFormat(indent=0),
    FileFormat(indent=None, item_separator=", "),
    FileFormat(indent=None, item_separator=",", key_separator=":"),
    FileFormat(indent=2, ensure_ascii=True),
    FileFormat(indent=2, newline="\r\n"),
    FileFormat(indent=2, bom=True),
    FileFormat(indent=2, trailing_newline=False),
    FileFormat(container="jsonl", indent=None, item_separator=", "),
    FileFormat(container="jsonl", indent=None, item_separator=",", key_separator=":", newline="\r\n"),
    FileFormat(container="jsonl", indent=None, item_separator=", ", trailing_newline=False, ensure_ascii=True),
]


@pytest.mark.parametrize("fmt", FORMAT_VARIANTS, ids=str)
def test_format_variants_are_detected_and_reproduced(fmt, unsloth_sample, tmp_path):
    items = json.loads(unsloth_sample.read_text("utf-8"))
    src = tmp_path / "src.json"
    src.write_bytes(io.encode_items(items, fmt))
    out = tmp_path / "out.json"

    dataset = roundtrip(src, out)

    assert dataset.format == fmt
    assert dataset.exact
    assert out.read_bytes() == src.read_bytes()


def test_unusual_formatting_is_flagged_but_data_is_kept(tmp_path):
    src = tmp_path / "hand.json"
    src.write_text('[ {"messages" : [ {"role":"user", "content":"hi", "n": 1e5} ]} ]', "utf-8")
    out = tmp_path / "out.json"

    dataset = roundtrip(src, out)

    assert not dataset.exact
    assert json.loads(out.read_text("utf-8")) == json.loads(src.read_text("utf-8"))


def test_empty_file_needs_explicit_schema(tmp_path):
    src = tmp_path / "empty.json"
    src.write_text("[]", "utf-8")
    with pytest.raises(SchemaDetectionError):
        io.load(src)
    dataset = io.load(src, schema=OPENAI)
    assert dataset.conversations == [] and dataset.exact


def test_explicit_schema_must_fit(unsloth_sample):
    with pytest.raises(DatasetLoadError):
        io.load(unsloth_sample, schema=OPENAI)


@pytest.mark.parametrize("content", [b'[{"messages": [}', b'{"messages": []}\nnot json\n', b"\xff\xfe"])
def test_broken_files_raise_load_error(content, tmp_path):
    src = tmp_path / "bad.json"
    src.write_bytes(content)
    with pytest.raises(DatasetLoadError):
        io.load(src)


def test_conversation_ids_are_one_based(unsloth_sample):
    assert [c.id for c in io.load(unsloth_sample).conversations] == [1, 2, 3, 4]


def test_atomic_write_leaves_no_temp_files(tmp_path):
    target = tmp_path / "x.json"
    io.atomic_write(target, b"one")
    io.atomic_write(target, b"two")
    assert target.read_bytes() == b"two"
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


# Your own datasets (e.g. a real training file) can be checked without
# committing them: set DATAFORMATTER_ROUNDTRIP_FILES to paths separated by
# os.pathsep (";" on Windows, ":" elsewhere) and run pytest.
_EXTRA = [Path(p) for p in os.environ.get("DATAFORMATTER_ROUNDTRIP_FILES", "").split(os.pathsep) if p]


@pytest.mark.skipif(not _EXTRA, reason="DATAFORMATTER_ROUNDTRIP_FILES not set")
@pytest.mark.parametrize("path", _EXTRA, ids=lambda p: p.name)
def test_local_files_round_trip(path, tmp_path):
    out = tmp_path / path.name
    assert roundtrip(path, out).exact
    assert out.read_bytes() == path.read_bytes()
