import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtQml")

from PySide6.QtCore import QObject, QSettings, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication  # noqa: E402

from leftonread.app import create_engine  # noqa: E402
from leftonread.bridge.backend import Backend  # noqa: E402
from leftonread.bridge.models import ConversationListModel, MessageListModel  # noqa: E402
from leftonread.bridge.settings import MAX_RECENT, AppSettings, migrate_legacy_settings  # noqa: E402
from leftonread.core.model import Conversation, Message, validate  # noqa: E402
from leftonread.core.project import Project  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def project_file(unsloth_sample, tmp_path):
    path = tmp_path / "p.dsproj"
    Project.create(path, unsloth_sample).close()
    return path


@pytest.fixture
def settings(app, tmp_path):
    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return AppSettings(store, backdrops_dir=tmp_path / "backdrops")


@pytest.fixture
def backend(settings):
    b = Backend(settings=settings)
    yield b
    b.close()


def url(path):
    return QUrl.fromLocalFile(str(path))


# -- models -------------------------------------------------------------------


def test_model_rows(app, project_file):
    model = ConversationListModel()
    with Project.open(project_file) as project:
        project.add_tag(2, "night")
        model.reset(project)
    assert model.rowCount() == 4
    first = model.index(0)
    assert model.data(first, model.IdRole) == 1
    assert model.data(first, model.PreviewRole) == "Good morning, Pip!"
    assert model.data(model.index(2), model.TurnsRole) == 4
    assert model.data(first, model.StatusRole) == "unreviewed"
    assert model.data(model.index(1), model.TagsRole) == ["night"]
    names = {bytes(n.data()) for n in model.roleNames().values()}
    assert names == {b"conversationId", b"preview", b"turns", b"status", b"tags"}


def test_model_refresh(app, project_file):
    model = ConversationListModel()
    changed = []
    model.dataChanged.connect(lambda a, b: changed.append(a.row()))
    with Project.open(project_file) as project:
        model.reset(project)
        project.set_status(3, "keep")
        model.refresh(project, [3])
    assert changed == [2]
    assert model.status_at(2) == "keep" and model.row_of(3) == 2 and model.id_at(2) == 3


def test_message_model(app):
    model = MessageListModel()
    conv = Conversation(messages=[Message("user", "hi"), Message("assistant", [{"type": "text"}])])
    model.reset(conv, validate(conv))
    assert model.rowCount() == 2
    assert model.data(model.index(0), model.RoleRole) == "user"
    assert model.data(model.index(0), model.EditableRole) is True
    assert model.data(model.index(1), model.EditableRole) is False
    assert '"type": "text"' in model.data(model.index(1), model.ContentRole)
    assert model.data(model.index(1), model.IssueRole) == "Content is not plain text"


# -- settings -----------------------------------------------------------------


def test_settings_defaults_and_persistence(settings, tmp_path):
    assert settings.backgroundColor.name() == "#020618"
    assert settings.highlightColor.name() == "#01ffff"
    assert settings.backdrop == ""

    settings.setHighlightColor(QColor("#ff8800"))
    again = AppSettings(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat), tmp_path / "none")
    assert again.highlightColor.name() == "#ff8800"

    settings.resetAppearance()
    assert settings.highlightColor.name() == "#01ffff"


def test_settings_recent(settings, tmp_path):
    files = []
    for i in range(MAX_RECENT + 2):
        f = tmp_path / f"p{i}.dsproj"
        f.write_bytes(b"")
        files.append(f)
        settings.add_recent(f)
    settings.add_recent(files[5])  # moves to the top, no duplicate

    recent = settings.recentProjects
    assert len(recent) == MAX_RECENT
    assert recent[0]["name"] == "p5.dsproj" and recent[1]["name"] == f"p{MAX_RECENT + 1}.dsproj"
    assert all(r["exists"] for r in recent)

    files[5].unlink()
    assert settings.recentProjects[0]["exists"] is False
    settings.removeRecent(recent[0]["path"])
    assert "p5.dsproj" not in [r["name"] for r in settings.recentProjects]


def test_migrate_legacy_settings(app, tmp_path):
    def ini(name):
        return QSettings(str(tmp_path / f"{name}.ini"), QSettings.Format.IniFormat)

    old_dir, new_dir = tmp_path / "old" / "backdrops", tmp_path / "new" / "backdrops"
    old_dir.mkdir(parents=True)
    (old_dir / "sky.png").write_bytes(b"png")
    legacy = ini("legacy")
    legacy.setValue("appearance/highlight", "#ff8800")
    legacy.setValue("appearance/backdrop", url(old_dir / "sky.png").toString())
    legacy.setValue("recent/projects", '["a.dsproj"]')
    legacy.sync()

    store = ini("new")
    assert migrate_legacy_settings(store, legacy, new_dir, old_dir)
    assert (new_dir / "sky.png").read_bytes() == b"png" and (old_dir / "sky.png").exists()
    migrated = AppSettings(ini("new"), new_dir)
    assert migrated.highlightColor.name() == "#ff8800"
    assert migrated.backdrop == url(new_dir / "sky.png").toString()
    assert [r["path"] for r in migrated.recentProjects] == ["a.dsproj"]

    # Once the new store has anything in it, it is never touched again.
    legacy.setValue("appearance/highlight", "#123456")
    assert not migrate_legacy_settings(ini("new"), legacy, new_dir, old_dir)
    assert AppSettings(ini("new"), new_dir).highlightColor.name() == "#ff8800"
    assert not migrate_legacy_settings(ini("empty"), ini("nothing"), tmp_path / "x", tmp_path / "y")


def test_settings_backdrops(settings, tmp_path):
    folder = tmp_path / "backdrops"
    folder.mkdir()
    (folder / "a.png").write_bytes(b"")
    (folder / "b.JPG").write_bytes(b"")
    (folder / "notes.txt").write_text("x")
    settings.reloadBackdrops()
    names = [u.rsplit("/", 1)[1] for u in settings.backdrops]
    assert names == ["a.png", "b.JPG"]

    settings.setBackdrop(settings.backdrops[0])
    assert settings.backdrop.endswith("a.png")
    (folder / "a.png").unlink()
    assert settings.backdrop == ""  # a vanished file is ignored


# -- backend ------------------------------------------------------------------


def test_backend_opens_project(backend, settings, project_file):
    messages = []
    backend.message.connect(messages.append)

    backend.openProject(url(project_file))

    assert backend.hasProject and backend.title == "p"
    assert backend.summary.startswith("4 conversations")
    assert backend.conversations.rowCount() == 4
    assert backend.currentRow == 0 and backend.messages.rowCount() == 3
    assert backend.currentStats["id"] == 1
    assert messages == []
    assert settings.recentProjects[0]["name"] == "p.dsproj"
    backend.close()
    assert not backend.hasProject and backend.conversations.rowCount() == 0
    assert backend.currentRow == -1 and backend.messages.rowCount() == 0


def test_backend_review_flow(backend, project_file):
    backend.openProject(url(project_file))
    assert (backend.reviewedCount, backend.totalCount) == (0, 4)

    backend.keep()
    assert backend.currentRow == 1 and backend.reviewedCount == 1
    assert backend.conversations.status_at(0) == "keep"

    backend.archive()
    assert backend.currentRow == 2
    assert backend.counts["archive"] == 1

    backend.skip()
    assert backend.currentRow == 3

    backend.keep()  # wraps around to the skipped one
    assert backend.currentRow == 2 and backend.reviewedCount == 3

    backend.undo()
    assert backend.reviewedCount == 2 and backend.currentRow == 3
    assert backend.conversations.status_at(3) == "unreviewed"


def test_backend_selects_first_unreviewed_on_open(backend, project_file):
    with Project.open(project_file) as project:
        project.set_status(1, "keep")
        project.set_status(2, "archive")
    backend.openProject(url(project_file))
    assert backend.currentRow == 2


def test_backend_edit_message(backend, project_file, tmp_path, unsloth_sample):
    backend.openProject(url(project_file))
    backend.setMessageContent(1, "Good morning, Pip!")  # unchanged: no edit recorded
    assert not backend.canUndo

    backend.setMessageContent(1, "Hello, Pip!")
    assert backend.canUndo
    assert backend.conversations.data(backend.conversations.index(0), ConversationListModel.PreviewRole) == "Hello, Pip!"

    with Project.open(project_file) as project:
        conv = project.get(1)
        assert conv.messages[1].content == "Hello, Pip!"
        assert conv.messages[1].key_order == ["role", "content"]
        assert conv.messages[0].content.startswith("You are Pip")

    backend.undo()
    out = tmp_path / "out.json"
    backend.exportTo(url(out), "all")
    assert out.read_bytes() == unsloth_sample.read_bytes()


def test_backend_edit_warns_but_saves(backend, project_file):
    backend.openProject(url(project_file))
    backend.setMessageContent(2, "   ")
    assert "Content is empty" in backend.currentStats["issues"]
    assert backend.messages.data(backend.messages.index(2), MessageListModel.IssueRole) == "Content is empty"


def test_backend_asks_for_schema_when_unsure(backend, tmp_path):
    source = tmp_path / "empty.json"
    source.write_text("[]", "utf-8")
    asked = []
    backend.schemaChoiceNeeded.connect(asked.append)

    backend.newProject(url(source), url(tmp_path / "empty"))

    assert len(asked) == 1 and len(asked[0]) == 3 and not backend.hasProject
    backend.importWithSchema(1)
    assert backend.hasProject and backend.currentRow == -1
    assert (tmp_path / "empty.dsproj").is_file()
    backend.skip()
    backend.keep()  # no conversation: nothing happens


def test_backend_reports_errors(backend, tmp_path):
    messages = []
    backend.message.connect(messages.append)
    backend.openProject(url(tmp_path / "missing.dsproj"))
    assert len(messages) == 1 and not backend.hasProject


def test_export_from_backend(backend, project_file, tmp_path):
    messages = []
    backend.message.connect(messages.append)
    backend.openProject(url(project_file))
    out = tmp_path / "out.json"

    backend.exportTo(url(out), "all")

    assert messages == ["Exported 4 conversations to out.json."]


# -- QML ----------------------------------------------------------------------


def test_main_qml_loads_without_warnings(app, settings, project_file, tmp_path):
    backend = Backend(settings=settings)
    warnings = []
    engine = create_engine(backend, settings, lambda ws: warnings.extend(w.toString() for w in ws))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    app.processEvents()

    # Bindings that only evaluate with a project open, in each mode, must not warn either.
    backend.openProject(url(project_file))
    app.processEvents()
    review = window.findChild(QObject, "reviewScreen")
    review.setProperty("editing", True)
    app.processEvents()
    backend.keep()
    backend.setMessageContent(1, "Edited")
    app.processEvents()
    window.setProperty("mode", "finder")
    app.processEvents()
    window.setProperty("sidebarOpen", False)
    app.processEvents()

    folder = tmp_path / "backdrops"
    folder.mkdir()
    (folder / "x.png").write_bytes(b"")
    settings.reloadBackdrops()
    app.processEvents()

    backend.close()
    app.processEvents()

    assert warnings == []
    del engine


def test_backend_delete_message(backend, project_file, tmp_path, unsloth_sample):
    backend.openProject(url(project_file))
    backend.setCurrentRow(2)  # system + 4 turns
    backend.deleteMessage(4)
    assert backend.messages.rowCount() == 4
    assert backend.currentStats["turns"] == 3
    assert "Last message is not from the assistant" in backend.currentStats["issues"]
    with Project.open(project_file) as project:
        assert [m.content for m in project.get(3).messages][-1] == "Thanks, Pip."

    backend.deleteMessage(99)  # out of range: ignored
    backend.undo()
    assert backend.messages.rowCount() == 5
    out = tmp_path / "out.json"
    backend.exportTo(url(out), "all")
    assert out.read_bytes() == unsloth_sample.read_bytes()


def test_backend_insert_message(backend, project_file, tmp_path, unsloth_sample):
    backend.openProject(url(project_file))
    backend.setCurrentRow(2)  # system + 4 turns
    backend.insertMessage(5, "user")
    assert backend.messages.rowCount() == 6
    assert "Last message is not from the assistant" in backend.currentStats["issues"]
    backend.setMessageContent(5, "One more thing")
    backend.insertMessage(6, "assistant")
    backend.setMessageContent(6, "Sure.")
    with Project.open(project_file) as project:
        msgs = project.get(3).messages
        assert [(m.role, m.content) for m in msgs[-2:]] == [("user", "One more thing"), ("assistant", "Sure.")]

    backend.insertMessage(99, "user")  # out of range: ignored
    backend.insertMessage(0, "narrator")  # unknown role: ignored
    assert backend.messages.rowCount() == 7

    out = tmp_path / "edited.json"
    backend.exportTo(url(out), "all")
    text = out.read_text(encoding="utf-8")
    assert '"One more thing"' in text and '"Sure."' in text

    for _ in range(4):
        backend.undo()
    assert backend.messages.rowCount() == 5
    out = tmp_path / "out.json"
    backend.exportTo(url(out), "all")
    assert out.read_bytes() == unsloth_sample.read_bytes()


def test_backend_move_message(backend, project_file, tmp_path, unsloth_sample):
    backend.openProject(url(project_file))
    backend.setCurrentRow(2)  # system, user, assistant, user, assistant
    msgs = backend.messages
    texts = lambda: [msgs.data(msgs.index(i)) for i in range(msgs.rowCount())]  # noqa: E731
    before = texts()
    backend.moveMessage(3, -1)
    assert texts() == before[:2] + [before[3], before[2]] + before[4:]
    assert backend.currentStats["issues"]  # user, user, assistant, assistant: no longer alternating
    backend.moveMessage(0, -1)  # already first: ignored
    backend.moveMessage(4, 1)  # already last: ignored
    backend.moveMessage(1, 2)  # only single steps
    assert backend.canUndo
    backend.undo()
    assert texts() == before
    backend.exportTo(url(tmp_path / "out.json"), "all")
    assert (tmp_path / "out.json").read_bytes() == unsloth_sample.read_bytes()


def test_backend_new_conversation(backend, project_file, tmp_path, unsloth_sample):
    backend.openProject(url(project_file))
    backend.setQueue("archive")  # empty queue: a new conversation still shows up
    assert backend.conversations.rowCount() == 0 and backend.currentRow == -1
    backend.newConversation()
    assert backend.conversations.rowCount() == 1 and backend.currentRow == 0
    assert backend.totalCount == 5 and backend.currentStats["id"] == 5
    msgs = backend.messages
    assert msgs.rowCount() == 1
    assert (msgs.data(msgs.index(0), msgs.RoleRole), msgs.data(msgs.index(0))) == ("user", "")

    backend.setQueue("all")
    assert backend.currentRow == 4  # still selected, last row
    backend.close()
    backend.openProject(url(project_file))
    assert backend.currentStats["id"] == 5  # reopens on it

    backend.undo()
    assert backend.conversations.rowCount() == 4 and backend.totalCount == 4
    assert backend.currentRow == 3
    backend.exportTo(url(tmp_path / "out.json"), "all")
    assert (tmp_path / "out.json").read_bytes() == unsloth_sample.read_bytes()


def test_backend_resumes_where_left(settings, project_file):
    first = Backend(settings=settings)
    first.openProject(url(project_file))
    first.keep()  # row 0 kept -> moves to row 1
    first.setCurrentRow(3)
    first.close()

    again = Backend(settings=settings)
    again.openProject(url(project_file))
    assert again.currentRow == 3 and again.currentStats["id"] == 4
    again.close()


def test_backend_queues_and_archive_reason(backend, project_file):
    archived = []
    backend.archived.connect(archived.append)
    backend.openProject(url(project_file))
    assert backend.queue == "all"
    backend.keep()  # conversation 1
    backend.archive()  # conversation 2
    assert archived == [2]
    assert backend.currentStats["id"] == 3

    backend.setArchiveReason(2, "repetitive")
    backend.setArchiveReason(3, "broken")  # not archived: ignored
    backend.setArchiveReason(99, "broken")  # unknown: ignored

    backend.setQueue("archive")
    assert backend.queue == "archive"
    assert backend.conversations.rowCount() == 1
    assert backend.currentStats["id"] == 2 and backend.currentStats["archiveReason"] == "repetitive"
    backend.archive()  # re-archiving while re-reviewing keeps the reason
    assert backend.currentStats["archiveReason"] == "repetitive"

    backend.setQueue("unreviewed")
    assert [backend.conversations.id_at(r) for r in range(backend.conversations.rowCount())] == [3, 4]
    backend.keep()  # 3 stays listed (marked kept) until the queue is reloaded
    assert backend.conversations.rowCount() == 2 and backend.currentStats["id"] == 4
    backend.setQueue("unreviewed")
    assert backend.conversations.rowCount() == 1

    backend.setQueue("nonsense")
    assert backend.queue == "unreviewed"
    path = backend._project.path
    backend.close()
    backend.openProject(url(path))
    assert backend.queue == "unreviewed" and backend.currentStats["id"] == 4


def test_edit_mode_keyboard(app, settings, project_file):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    backend = Backend(settings=settings)
    warnings = []
    engine = create_engine(backend, settings, lambda ws: warnings.extend(w.toString() for w in ws))
    window = engine.rootObjects()[0]
    window.show()
    window.requestActivate()
    assert QTest.qWaitForWindowActive(window)
    backend.openProject(url(project_file))
    backend.setCurrentRow(2)  # system + 4 turns
    review = window.findChild(QObject, "reviewScreen")
    view = window.findChild(QObject, "messageView")

    def key(k, mods=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(window, k, mods)
        for _ in range(5):
            app.processEvents()

    key(Qt.Key.Key_E)
    assert review.property("editing") is True
    assert view.property("currentTurn") == 1  # system prompt is collapsed, so the first user turn

    key(Qt.Key.Key_Tab)
    assert view.property("currentTurn") == 2
    for _ in range(10):  # Down moves through the lines, then into the next turn
        key(Qt.Key.Key_Down)
        if view.property("currentTurn") != 2:
            break
    assert view.property("currentTurn") == 3
    key(Qt.Key.Key_Up)  # cursor is at the start of turn 3: back into turn 2
    assert view.property("currentTurn") == 2
    key(Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    assert view.property("currentTurn") == 1

    key(Qt.Key.Key_Right)  # moves the text cursor, not keep
    key(Qt.Key.Key_K)  # types a letter, not keep
    assert backend.reviewedCount == 0

    key(Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert backend.messages.rowCount() == 4
    assert backend.currentStats["turns"] == 3

    # Ctrl+Enter adds a turn after the focused one (turn 1, now the assistant reply)
    # with the alternating role, and puts the cursor in it.
    key(Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert backend.messages.rowCount() == 5
    msgs = backend.messages
    assert [msgs.data(msgs.index(i), msgs.RoleRole) for i in (1, 2)] == ["assistant", "user"]
    assert view.property("currentTurn") == 2
    key(Qt.Key.Key_H)
    key(Qt.Key.Key_Tab)  # leaving the turn saves it
    assert backend.messages.data(backend.messages.index(2)) == "h"

    # Alt+Up moves the focused turn (3) up; the cursor follows it, and
    # unsaved text in it is saved first.
    assert view.property("currentTurn") == 3
    third = msgs.data(msgs.index(3))
    key(Qt.Key.Key_X)  # Tab put the cursor at the start
    key(Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    assert msgs.data(msgs.index(2)) == "x" + third and msgs.data(msgs.index(3)) == "h"
    assert view.property("currentTurn") == 2

    # After archiving, 1-4 pick a reason for the conversation just archived.
    key(Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
    toast = window.findChild(QObject, "reasonToast")
    key(Qt.Key.Key_A)
    assert toast.property("visible") is True and toast.property("conversationId") == 3
    key(Qt.Key.Key_2)
    assert toast.property("visible") is False
    with Project.open(project_file) as project:
        assert project.get(3).archive_reason == "out of character"

    # N starts a blank conversation in edit mode with the cursor in its user turn.
    key(Qt.Key.Key_N)
    assert review.property("editing") is True
    assert backend.totalCount == 5 and backend.currentStats["id"] == 5
    assert view.property("currentTurn") == 0
    key(Qt.Key.Key_H)
    key(Qt.Key.Key_N)  # while typing, N is a letter
    key(Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)  # done: saves
    assert backend.messages.data(backend.messages.index(0)) == "hn"
    assert backend.totalCount == 5
    review.setEditing(True)

    key(Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
    assert review.property("editing") is False
    assert warnings == []
    backend.close()
    del engine
