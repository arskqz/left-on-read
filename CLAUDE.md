# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

The design lives in two plan documents, which are the source of truth for scope and decisions:

- `Dataset formatter - Plan.md` — the main tool. Work follows its roadmap (§8) phase by phase. **Phase 0 (core) is done**: `dataformatter/core/` + tests + samples + CI. **Phase 1 (PySide6/QML shell) is themed after `dataformatter_design.pdf`** (the UI mockup: opening screen with recent projects, Review screen, Finder screen). Review basics are wired up: keep / archive / skip / undo, the reviewed counter, and editing message text. Tags (beyond showing them), search, replace and word stats are visible placeholders for Phases 3–4. Follow the PDF for layout; ask before deviating from it.
- `Subtitle importer - Plan.md` — a separate, later tool that *produces* a dataset JSON. Do not merge it into the formatter.

Decisions marked ✅ / `[x]` in the plans are settled; don't reopen them without being asked.

## Commands

Python 3.11, managed with `uv` (venv in `.venv`).

```sh
uv sync                                         # install deps
uv run dataformatter                            # start the UI
uv run pytest                                   # all tests (Qt tests run offscreen)
uv run pytest tests/test_project.py::test_edit_and_undo   # single test
uv run dataformatter check FILE                 # schema/format/warnings + byte-identical round-trip check
```

`DATAFORMATTER_ROUNDTRIP_FILES` (os.pathsep-separated) adds local, uncommitted datasets to the round-trip tests — use it for the user's real training file, which must never be committed.

## Architecture

Three layers with a strict dependency direction:

- `core/` — plain Python, **no Qt imports**. Tested with pytest.
- `bridge/` — thin PySide6 `QObject`s / `QAbstractListModel`s exposed to QML. `Backend` (context property `backend`) owns the open `Project` and reports problems to QML through its `message` signal instead of raising. Slow work will move to `QRunnable` + `QThreadPool`; import is synchronous for now. `AppSettings` (context property `settings`, `bridge/settings.py`) holds QSettings-backed appearance (background `#020618`, highlight `#01FFFF`, backdrop) and recent projects; backdrop images are read from `<AppDataLocation>/backdrops/` and the repo ships none.
- `qml/` — layout and look only; never touches files or SQL. `qmldir` declares the `Theme` singleton (fixed tokens) and the screens; user-changeable colours come from `settings`. Reusable pieces live in `qml/components/` and import `".."` for `Theme`. Every type in `qml/` must be listed in `qmldir`, because a directory with a qmldir only exposes the types it lists.
- `app.py` builds the engine (`create_engine` is reused by the QML smoke test in `tests/test_bridge.py`, which fails on any QML warning). `main.py` imports Qt lazily so `check` works without it.

UI is **PySide6 (Qt 6) with QML only**: never QtWidgets (no `QApplication`, no `QFileDialog`). Use `QGuiApplication` and `QtQuick.Dialogs`. The dependency is `PySide6-Essentials`.

### Core data flow

`io.load` → `Dataset` → `Project.create` writes `*.dsproj` (SQLite) → edits via `Project` → `Project.export` → `io.save`.

- `schema.py`: `SchemaSpec` maps a file's spelling (list key, role/content field names, role map) to the internal model. `detect_schema` raises `SchemaDetectionError` with `.candidates` when unsure — the UI should ask the user and pass `schema=` explicitly. Add a schema by adding a `SchemaSpec` to `SCHEMAS`.
- `io.py`: formatting (container, indent, separators, `ensure_ascii`, CRLF, BOM, trailing newline) is detected by **re-serialising with candidate `FileFormat`s until one reproduces the file**. `Dataset.exact` / `Project.roundtrip_exact` say whether that succeeded; if not, export is lossless in data but not bytes.
- `model.py`: `Message.key_order` / `Conversation.key_order` / `Message.file_role` are round-trip hints that let export reproduce key order and odd role values. Keep them intact when editing; new messages can leave them `None`.
- `project.py`: every mutation goes through `_change`, which stores before/after snapshots in `history`; `batch()` groups changes into one transaction + one undo step. `messages_fts` rowids are `conversation_id << 20 | message_index` so per-conversation reindexing is a range delete — keep that scheme (a `WHERE conversation_id = ?` delete made import quadratic).

## Invariants that are easy to break

- **Same shape in → same shape out.** Never convert between schemas; role mapping happens only at the file boundary.
- **Byte-identical round-trip** for unedited data — the sample tests in `tests/test_io.py` and `tests/test_project.py` guard it. `samples/**` is `-text` in `.gitattributes` so git never rewrites line endings.
- **Source file is read-only**: export refuses to overwrite it; changes are detected via `check_source()` (hash).
- **Export is always clean:** no tags, status, or archive reasons in output.
- **Validation warns, never blocks.**
- **Fully local:** no network calls or telemetry. Heavy ML deps go in an optional `[semantic]` extra.
- **Nothing Vesi-specific hard-coded** (names, system prompt, Qwen tokenizer). Sample data is invented.

## Qt 6 / PySide6 notes

- QML imports have no version numbers (`import QtQuick`, `QtQuick.Controls`, `QtQuick.Layouts`, `QtQuick.Dialogs`).
- HiDPI is on by default; use `app.exec()` and scoped enums (`Qt.ItemDataRole.UserRole`).
- `Slot` / `Signal` / `Property` come from `PySide6.QtCore`. Slots called from QML with file paths take `QUrl` and use `toLocalFile()`.
- `create_engine` sets the **Basic** Controls style (`QQuickStyle`), the only built-in style that fully follows our palette. Window colours go through the `palette` on `ApplicationWindow`.

Targets Windows and Fedora — use `pathlib`, avoid OS-specific paths.
