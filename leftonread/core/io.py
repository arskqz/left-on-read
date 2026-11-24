"""Load and save dataset files (JSON array or JSON Lines) without losing anything.

On load, the file's formatting (container, indent, separators, escaping, line
endings, BOM, trailing newline) is detected by re-serialising the parsed data
with candidate settings until one reproduces the file exactly. Saving with the
detected :class:`FileFormat` then writes the same bytes back.
"""

from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .model import Conversation
from .schema import SchemaSpec, detect_schema

JSON, JSONL = "json", "jsonl"

Indent = int | str | None


class DatasetLoadError(ValueError):
    pass


@dataclass(frozen=True)
class FileFormat:
    container: str = JSON
    indent: Indent = 2
    item_separator: str = ","
    key_separator: str = ": "
    ensure_ascii: bool = False
    newline: str = "\n"
    trailing_newline: bool = True
    bom: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileFormat:
        return cls(**data)


@dataclass
class Dataset:
    conversations: list[Conversation]
    schema: SchemaSpec
    format: FileFormat
    exact: bool  # saving with `format` reproduces the file byte for byte
    sha256: str


# -- serialising --------------------------------------------------------------


def dumps_items(items: Sequence[Any], fmt: FileFormat) -> str:
    separators = (fmt.item_separator, fmt.key_separator)
    if fmt.container == JSON:
        text = json.dumps(items, indent=fmt.indent, separators=separators, ensure_ascii=fmt.ensure_ascii)
    else:
        text = "\n".join(json.dumps(i, separators=separators, ensure_ascii=fmt.ensure_ascii) for i in items)
    if fmt.trailing_newline:
        text += "\n"
    if fmt.newline != "\n":
        # Safe: JSON output never contains a raw newline inside a string.
        text = text.replace("\n", fmt.newline)
    return text


def encode_items(items: Sequence[Any], fmt: FileFormat) -> bytes:
    return (codecs.BOM_UTF8 if fmt.bom else b"") + dumps_items(items, fmt).encode("utf-8")


def save(path: str | os.PathLike, conversations: Iterable[Conversation], schema: SchemaSpec, fmt: FileFormat) -> None:
    items = [schema.conversation_to_item(c) for c in conversations]
    atomic_write(path, encode_items(items, fmt))


def atomic_write(path: str | os.PathLike, data: bytes) -> None:
    """Write via a temp file in the same folder, so a crash never leaves half a file."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# -- loading ------------------------------------------------------------------


def load(path: str | os.PathLike, schema: SchemaSpec | None = None) -> Dataset:
    """Read a dataset file. Detects the schema unless one is given.

    Raises DatasetLoadError for unreadable files and
    :class:`~leftonread.core.schema.SchemaDetectionError` when the schema
    is unclear (the caller should then ask the user and pass ``schema``).
    """
    data = Path(path).read_bytes()
    text, bom = _decode(data)
    container, items = _parse(text)

    if schema is None:
        schema = detect_schema(items)
    else:
        bad = schema.first_mismatch(items)
        if bad is not None:
            raise DatasetLoadError(f"Item {bad} does not match the schema {schema.label}.")

    conversations = [schema.item_to_conversation(item, id=i + 1) for i, item in enumerate(items)]
    fmt, exact = detect_format(text, container, items, bom)
    if exact:
        # Also check the full path through the internal model.
        exact = dumps_items([schema.conversation_to_item(c) for c in conversations], fmt) == text
    return Dataset(conversations, schema, fmt, exact, hashlib.sha256(data).hexdigest())


def file_sha256(path: str | os.PathLike) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode(data: bytes) -> tuple[str, bool]:
    bom = data.startswith(codecs.BOM_UTF8)
    if bom:
        data = data[len(codecs.BOM_UTF8):]
    try:
        return data.decode("utf-8"), bom
    except UnicodeDecodeError as e:
        raise DatasetLoadError(f"The file is not valid UTF-8: {e}") from e


def _parse(text: str) -> tuple[str, list[Any]]:
    if text.lstrip().startswith("["):
        try:
            return JSON, json.loads(text)
        except json.JSONDecodeError as e:
            raise DatasetLoadError(f"Invalid JSON: {e}") from e

    items = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise DatasetLoadError(
                    f"Line {lineno} is not valid JSON ({e.msg}). Expected a JSON array or JSON Lines."
                ) from e
    return JSONL, items


def detect_format(text: str, container: str, items: Sequence[Any], bom: bool) -> tuple[FileFormat, bool]:
    """Find the FileFormat that reproduces ``text``. Returns (format, exact)."""
    candidates = list(_format_candidates(text, container, bom))
    for fmt in candidates:
        if dumps_items(items, fmt) == text:
            return fmt, True
    return candidates[0], False


def _format_candidates(text: str, container: str, bom: bool) -> Iterator[FileFormat]:
    newline = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")
    common = dict(container=container, newline=newline, trailing_newline=body.endswith("\n"), bom=bom)

    layouts: list[tuple[Indent, str, str]] = []
    if container == JSON:
        layouts += [(indent, ",", ": ") for indent in _indent_candidates(body)]
    layouts += [(None, ", ", ": "), (None, ",", ":")]

    for ensure_ascii in (False, True):
        for indent, item_sep, key_sep in layouts:
            yield FileFormat(
                indent=indent, item_separator=item_sep, key_separator=key_sep, ensure_ascii=ensure_ascii, **common
            )


def _indent_candidates(body: str) -> list[Indent]:
    candidates: list[Indent] = []
    match = re.search(r"\n([ \t]+)\S", body)
    if match:
        ws = match.group(1)
        candidates.append(ws if "\t" in ws else len(ws))
    for indent in (2, 4, "\t", 0):
        if indent not in candidates:
            candidates.append(indent)
    return candidates
