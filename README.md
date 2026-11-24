# Left on Read

A local desktop tool for reviewing and editing chat-format fine-tuning datasets,
so you don't have to scroll through 20k+ lines of JSON.

> **Status:** early development. The core library, the project file and a
> first plain UI shell (import, open, export, conversation list) are in place.

## Principles

- **Fully local.** No cloud APIs, no telemetry.
- **Same shape in, same shape out.** The tool is an editor, not a converter.
  An unedited import → export reproduces the source file byte for byte.
- **The source file is never modified.** Edits, keep/archive decisions and
  tags live in a `.dsproj` project file (SQLite). Exports are always clean.

## Supported dataset schemas

| Schema | Container | List key | Message fields | Roles |
|---|---|---|---|---|
| Unsloth role/content | JSON array or JSONL | `conversations` | `role` / `content` | system / user / assistant |
| OpenAI messages | JSON array or JSONL | `messages` | `role` / `content` | system / user / assistant |
| ShareGPT | JSON array or JSONL | `conversations` | `from` / `value` | system / human / gpt |

Invented example files for each are in [`samples/`](samples/).

## Usage

Requires [uv](https://docs.astral.sh/uv/) (Python 3.11+ is installed automatically).

```sh
uv sync
uv run leftonread                              # start the app
uv run leftonread check path/to/dataset.json   # command-line check
```

The UI is Qt Quick (QML) via PySide6. `check` reports the detected schema and formatting, lists validation warnings,
and verifies that import → export reproduces the file exactly.

## Development

```sh
uv run pytest                                  # all tests
uv run pytest tests/test_io.py -k sharegpt     # a subset
```

To check your own datasets without committing them, list them in
`LEFTONREAD_ROUNDTRIP_FILES`, separated by `;` on Windows or `:` elsewhere:

```sh
LEFTONREAD_ROUNDTRIP_FILES=/path/to/a.json uv run pytest tests/test_io.py
```

## License

MIT. See [LICENSE](LICENSE).
