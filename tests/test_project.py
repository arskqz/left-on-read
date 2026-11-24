import json
import shutil

import pytest

from conftest import SAMPLE_FILES
from leftonread.core import io
from leftonread.core.model import Message
from leftonread.core.project import Project, ProjectError, SourceState


@pytest.fixture
def project(unsloth_sample, tmp_path):
    source = tmp_path / unsloth_sample.name
    shutil.copy(unsloth_sample, source)
    with Project.create(tmp_path / "p.dsproj", source) as p:
        yield p


@pytest.mark.parametrize("sample", SAMPLE_FILES, ids=lambda p: p.name)
def test_import_export_is_byte_identical(sample, tmp_path):
    out = tmp_path / sample.name
    with Project.create(tmp_path / "p.dsproj", sample) as p:
        assert p.roundtrip_exact
        p.export(out)
    assert out.read_bytes() == sample.read_bytes()


def test_state_survives_reopen(project):
    project.set_status(1, "keep")
    project.set_status(2, "archive", reason="repetitive")
    project.add_tag(2, " night ")
    project.close()

    with Project.open(project.path) as p:
        assert p.counts() == {"unreviewed": 2, "keep": 1, "archive": 1}
        c = p.get(2)
        assert (c.status, c.archive_reason, c.tags) == ("archive", "repetitive", {"night"})
        assert p.ids("unreviewed") == [3, 4]


def test_export_filters_by_status_and_is_clean(project, tmp_path):
    project.set_status(1, "keep")
    project.set_status(3, "keep")
    project.add_tag(3, "night")
    out = tmp_path / "keep.json"

    assert project.export(out, "keep") == 2

    source_items = json.loads(project.source_path.read_text("utf-8"))
    assert json.loads(out.read_text("utf-8")) == [source_items[0], source_items[2]]


def test_archive_reason_only_kept_for_archive(project):
    project.set_status(1, "keep", reason="ignored")
    assert project.get(1).archive_reason is None


def test_set_archive_reason(project, tmp_path):
    with pytest.raises(ValueError):
        project.set_archive_reason(1, "broken")  # not archived
    project.set_status(1, "archive")
    project.set_archive_reason(1, "  broken ")
    assert project.get(1).archive_reason == "broken"
    project.set_archive_reason(1, "")
    assert project.get(1).archive_reason is None
    project.undo()
    assert project.get(1).archive_reason == "broken"
    project.undo()
    assert project.get(1).archive_reason is None and project.get(1).status == "archive"

    out = tmp_path / "out.json"
    project.set_archive_reason(1, "broken")
    project.export(out)
    assert "broken" not in out.read_text(encoding="utf-8")


def test_add_conversation(project, unsloth_sample, tmp_path):
    from leftonread.core.model import Conversation

    cid = project.add_conversation(Conversation(messages=[Message("user", "Hello there")], id=999))
    assert cid == 5
    assert project.get(cid).status == "unreviewed" and project.count() == 5
    assert project.ids()[-1] == cid  # after the imported ones
    project.add_tag(cid, "new")
    project.close()

    with Project.open(project.path) as p:
        out = tmp_path / "out.json"
        p.export(out)
        items = json.loads(out.read_text(encoding="utf-8"))
        assert items[-1] == {"conversations": [{"role": "user", "content": "Hello there"}]}

        p.undo()  # the tag
        p.undo()  # the creation
        assert p.count() == 4
        with pytest.raises(KeyError):
            p.get(cid)
        assert p._conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0] == 0
        p.export(out)
    assert out.read_bytes() == unsloth_sample.read_bytes()


def test_ui_state(project):
    assert project.ui_state("current") is None
    assert project.ui_state("queue", "all") == "all"
    project.set_ui_state("current", "3")
    project.set_ui_state("queue", "archive")
    project.set_ui_state("queue", None)
    assert not project.can_undo  # not part of history
    project.close()
    with Project.open(project.path) as p:
        assert p.ui_state("current") == "3" and p.ui_state("queue") is None


def test_edit_and_undo(project):
    original = project.get(1)
    edited = project.get(1)
    edited.messages[1].content = "Hello there"
    edited.messages.append(Message("user", "dangling"))

    issues = project.update_conversation(edited)

    assert [i.code for i in issues] == ["last_not_assistant"]
    assert project.get(1).messages[1].content == "Hello there"
    assert project.undo() == [1]
    assert project.get(1) == original
    assert not project.can_undo


def test_batch_is_one_undo_step(project):
    project.set_status(4, "keep")
    with project.batch():
        project.set_status(1, "archive")
        project.add_tag(2, "fix-later")
    assert project.undo() == [1, 2]
    assert project.get(1).status == "unreviewed" and project.get(2).tags == set()
    assert project.get(4).status == "keep"
    assert project.undo() == [4]
    assert project.undo() == []


def test_no_op_change_adds_no_history(project):
    project.remove_tag(1, "missing")
    assert not project.can_undo


def test_unknown_conversation_and_bad_input(project):
    with pytest.raises(KeyError):
        project.set_status(999, "keep")
    with pytest.raises(ValueError):
        project.set_status(1, "maybe")
    with pytest.raises(ValueError):
        project.add_tag(1, "  ")


def test_search_index_follows_edits(project):
    def hits(word):
        return [
            r[0]
            for r in project._conn.execute(
                "SELECT conversation_id FROM messages_fts WHERE messages_fts MATCH ?", (word,)
            )
        ]

    assert hits("mustikkatee") == [2]
    conv = project.get(2)
    conv.messages[2].content = "Kamomillatee!"
    project.update_conversation(conv)
    assert hits("mustikkatee") == [] and hits("kamomillatee") == [2]
    project.undo()
    assert hits("mustikkatee") == [2]


def test_source_change_detection(project):
    assert project.check_source() is SourceState.UNCHANGED
    project.source_path.write_text("[]", "utf-8")
    assert project.check_source() is SourceState.CHANGED
    project.source_path.unlink()
    assert project.check_source() is SourceState.MISSING


def test_refuses_to_overwrite(project, unsloth_sample):
    with pytest.raises(ProjectError):
        Project.create(project.path, unsloth_sample)
    with pytest.raises(ProjectError):
        project.export(project.source_path)


def test_failed_import_leaves_no_project_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[", "utf-8")
    with pytest.raises(io.DatasetLoadError):
        Project.create(tmp_path / "p.dsproj", bad)
    assert not (tmp_path / "p.dsproj").exists()


def test_open_rejects_non_projects(tmp_path):
    junk = tmp_path / "junk.dsproj"
    junk.write_text("hello" * 100, "utf-8")
    with pytest.raises(ProjectError):
        Project.open(junk)
    with pytest.raises(ProjectError):
        Project.open(tmp_path / "missing.dsproj")
