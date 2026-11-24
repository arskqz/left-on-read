"""Command-line entry point: no arguments starts the UI, ``check FILE`` runs the round-trip check."""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import Counter
from pathlib import Path

from .core import DatasetLoadError, Project, SchemaDetectionError, load, validate

MAX_LISTED_ISSUES = 10


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leftonread")
    commands = parser.add_subparsers(dest="command")
    check = commands.add_parser(
        "check",
        help="Detect a dataset's schema and format, list validation warnings, "
        "and verify that import -> export reproduces the file byte for byte.",
    )
    check.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args.file)

    from .app import run  # imported here so `check` works without loading Qt

    return run()


def _check(path: Path) -> int:
    try:
        dataset = load(path)
    except (SchemaDetectionError, DatasetLoadError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    fmt = dataset.format
    print(f"Schema:        {dataset.schema.label}")
    print(
        f"Format:        {fmt.container}, indent={fmt.indent!r}, ensure_ascii={fmt.ensure_ascii}, "
        f"newline={'CRLF' if fmt.newline == chr(13) + chr(10) else 'LF'}, bom={fmt.bom}"
    )
    print(f"Conversations: {len(dataset.conversations)}")

    issues = {c.id: found for c in dataset.conversations if (found := validate(c))}
    by_code = Counter(issue.code for found in issues.values() for issue in found)
    print(f"Warnings:      {len(issues)} conversation(s) with issues")
    for code, n in by_code.most_common():
        print(f"  {code}: {n}")
    for cid, found in list(issues.items())[:MAX_LISTED_ISSUES]:
        for issue in found:
            where = f", message {issue.index + 1}" if issue.index is not None else ""
            print(f"  #{cid}{where}: {issue.message}")
    if len(issues) > MAX_LISTED_ISSUES:
        print(f"  ... and {len(issues) - MAX_LISTED_ISSUES} more conversation(s)")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"export{path.suffix}"
        with Project.create(Path(tmp) / "check.dsproj", path) as project:
            project.export(out)
        identical = out.read_bytes() == path.read_bytes()

    print(f"Round-trip:    {'byte-identical' if identical else 'DIFFERS from the source'}")
    return 0 if identical else 2
