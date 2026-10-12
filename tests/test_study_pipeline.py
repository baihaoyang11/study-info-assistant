from datetime import datetime
import json

import pytest

from academic_mail_agent.models import SourceDocument
from academic_mail_agent.extraction import extract_items
from academic_mail_agent.storage import StudyStore
from academic_mail_agent.manual_import import import_canvas_document
from academic_mail_agent.cli import main
from academic_mail_agent.errors import MailError


def doc(key='mock:a:777:7', body=None, **kwargs):
    return SourceDocument(source_key=key, source='mock', title='COMP101 课程安排', source_ref='mock://7', body=body or 'COMP101 作业提交，截止 2026-10-20 18:00 +08:00\nCOMP101 期中考试：2026-10-22 09:00 +08:00', **kwargs)


def test_multiple_tasks_with_explicit_timezone_and_source_evidence():
    items = extract_items(doc())
    assert len(items) == 2
    assert [i.kind for i in items] == ['assignment', 'exam']
    assert items[0].course == 'COMP101'
    assert items[0].due_at.isoformat() == '2026-10-20T18:00:00+08:00'
    assert items[1].due_at.isoformat() == '2026-10-22T09:00:00+08:00'
    assert all(i.source_key == 'mock:a:777:7' and i.evidence in doc().body for i in items)
    assert not items[0].needs_review


@pytest.mark.parametrize('text', ['作业截止下周五', '作业截止 10月20日', '作业截止 2026-02-30', '作业截止 2026-10-20 18:00'])
def test_ambiguous_or_invalid_dates_are_not_invented(text):
    item = extract_items(doc(body=text))[0]
    assert item.due_at is None and item.needs_review
    assert item.review_reason


def test_date_only_is_preserved_without_inventing_midnight():
    item = extract_items(doc(body='作业截止 2026-10-20'))[0]
    assert item.due_at is None
    assert item.due_date.isoformat() == '2026-10-20'
    assert item.needs_review


def test_deadline_on_following_line_belongs_to_the_task():
    source = doc(body='COMP101 作业：Project 1\n截止：2026-10-20 18:00 +08:00')
    tasks = extract_items(source)
    assert len(tasks) == 1
    assert tasks[0].kind == 'assignment'
    assert tasks[0].due_at.isoformat() == '2026-10-20T18:00:00+08:00'
    assert tasks[0].evidence in source.body


def test_publication_date_is_not_mistaken_for_deadline():
    item = extract_items(doc(body='COMP101 作业发布 2026-10-12，截止 2026-10-20 18:00 +08:00'))[0]
    assert item.due_at.isoformat() == '2026-10-20T18:00:00+08:00'


def test_publication_only_timestamp_is_not_a_confirmed_deadline():
    item = extract_items(doc(body='COMP101 作业发布于 2026-10-12 09:00 +08:00'))[0]
    assert item.due_at is None and item.due_date is None
    assert item.needs_review


def test_unrelated_offset_later_in_sentence_is_not_a_timezone():
    item = extract_items(doc(body='COMP101 作业截止 2026-10-20 18:00，讨论群编号 +08:00'))[0]
    assert item.due_at is None and item.needs_review


def test_separate_same_course_exams_are_not_collapsed():
    source = doc(body='COMP101 考试：2026-10-20 09:00 +08:00\nCOMP101 考试：2026-10-27 09:00 +08:00')
    items = extract_items(source)
    assert len(items) == 2
    assert len({i.id for i in items}) == 2
    assert [i.due_date.isoformat() for i in items] == ['2026-10-20', '2026-10-27']


def test_repeated_identical_lines_do_not_create_duplicate_tasks():
    line = 'COMP101 作业截止 2026-10-20 18:00 +08:00'
    assert len(extract_items(doc(body=line + '\n' + line))) == 1


def test_markdown_heading_is_not_a_task():
    source = doc(body='# COMP101 作业页面\nCOMP101 作业：Project 1\n截止：2026-10-20 18:00 +08:00')
    assert len(extract_items(source)) == 1


def test_cancelled_exam_is_not_a_confirmed_open_task():
    item = extract_items(doc(body='COMP101 考试已取消，原定 2026-10-20 18:00 +08:00'))[0]
    assert item.needs_review and '取消' in item.review_reason


def test_plain_notifications_and_autoreplies_are_not_tasks():
    assert extract_items(doc(body='这是一封问候邮件，没有行动要求。')) == []
    automatic = doc().model_copy(update={'title': 'Automatic reply: COMP101 作业', 'body': '作业截止 2026-10-20'})
    assert extract_items(automatic) == []


def test_incomplete_body_always_requires_review():
    item = extract_items(doc(body='作业截止 2026-10-20 18:00 +08:00', body_status='partial'))[0]
    assert item.needs_review and '正文' in item.review_reason


def test_storage_upsert_preserves_completion_and_updates_deadline(tmp_path):
    path = tmp_path / 'study.sqlite3'
    original = doc(body='COMP101 作业提交，截止 2026-10-20 18:00 +08:00')
    with StudyStore(path) as store:
        store.save_documents([original])
        task = store.list_items()[0]
        store.set_status(task['id'], 'done')
        updated = original.model_copy(update={'body': 'COMP101 作业提交，截止 2026-10-21 18:00 +08:00'})
        store.save_documents([updated, updated])
        tasks = store.list_items(include_done=True)
        assert len(tasks) == 1 and tasks[0]['id'] == task['id']
        assert tasks[0]['status'] == 'done'
        assert tasks[0]['due_at'] == '2026-10-21T18:00:00+08:00'
        assert store.document_count() == 1
    with StudyStore(path) as reopened:
        assert reopened.list_items(include_done=True)[0]['status'] == 'done'


def test_uid_generation_and_account_are_distinct_sources(tmp_path):
    with StudyStore(tmp_path / 'study.db') as store:
        store.save_documents([doc('qq:a:INBOX:777:7'), doc('qq:a:INBOX:888:7'), doc('qq:b:INBOX:777:7')])
        assert store.document_count() == 3
        assert len(store.list_items()) == 6


def test_removed_items_do_not_remain_as_open_todos(tmp_path):
    with StudyStore(tmp_path / 'study.db') as store:
        store.save_documents([doc()])
        store.save_documents([doc(body='本次没有学业事项。')])
        assert store.list_items() == []


def test_failed_batch_rolls_back_all_documents(tmp_path, monkeypatch):
    from academic_mail_agent import storage
    original = storage.extract_items
    def fail_second(source):
        if source.source_key == 'fail':
            raise ValueError('synthetic failure')
        return original(source)
    monkeypatch.setattr(storage, 'extract_items', fail_second)
    with StudyStore(tmp_path / 'study.db') as store:
        with pytest.raises(ValueError):
            store.save_documents([doc(), doc('fail')])
        assert store.document_count() == 0


def test_canvas_import_is_local_only_stable_and_updatable(tmp_path):
    path = tmp_path / 'COMP101.md'
    path.write_text('COMP101 作业截止 2026-10-20', encoding='utf-8')
    first = import_canvas_document(path, source_name='COMP101 作业页')
    path.write_text('COMP101 作业截止 2026-10-21', encoding='utf-8')
    second = import_canvas_document(path, source_name='COMP101 作业页')
    assert first.source == 'canvas_manual' and first.source_key == second.source_key
    assert second.body.endswith('2026-10-21')
    assert second.source_ref == 'COMP101 作业页'


def test_import_rejects_nontext_and_oversize_files(tmp_path):
    for name, content in [('unsafe.html', b'<script>bad</script>'), ('big.txt', b'x' * 1048577), ('bad.txt', b'\xff\xfe')]:
        path = tmp_path / name
        path.write_bytes(content)
        with pytest.raises(MailError, match='IMPORT_ERROR'):
            import_canvas_document(path)


def test_cli_mock_sync_todos_complete_and_digest(tmp_path, capsys):
    db = str(tmp_path / 'study.db')
    assert main(['sync', '--db', db]) == 0
    sync = json.loads(capsys.readouterr().out)
    assert sync['provider'] == 'mock' and sync['documents_saved'] > 0
    assert main(['todos', '--db', db, '--format', 'json']) == 0
    tasks = json.loads(capsys.readouterr().out)['items']
    assert tasks and tasks[0]['source'] == 'mock'
    assert main(['complete', tasks[0]['id'], '--db', db]) == 0
    capsys.readouterr()
    assert main(['digest', '--db', db]) == 0
    output = capsys.readouterr().out
    assert '学业清单' in output and 'Canvas' in output
    assert '手动' in output and 'Mock' in output


def test_cli_qq_sync_refuses_before_credentials_and_database(tmp_path, monkeypatch, capsys):
    def forbidden(*a, **kw):
        pytest.fail('Unauthorised sync loaded credentials')
    monkeypatch.setattr('academic_mail_agent.cli.load_qq_config', forbidden)
    db = tmp_path / 'study.db'
    assert main(['sync', '--provider', 'qq', '--db', str(db)]) == 2
    assert not db.exists()
    assert 'REAL_CONNECTION_DISABLED' in capsys.readouterr().err


def test_cli_manual_import_and_missing_completion(tmp_path, capsys):
    path = tmp_path / 'canvas.txt'
    path.write_text('COMP101 作业截止 2026-10-20', encoding='utf-8')
    db = str(tmp_path / 'study.db')
    assert main(['import-canvas', str(path), '--db', db]) == 0
    capsys.readouterr()
    assert main(['todos', '--db', db, '--format', 'json']) == 0
    assert json.loads(capsys.readouterr().out)['items'][0]['source'] == 'canvas_manual'
    assert main(['complete', 'missing', '--db', db]) == 2
    assert 'ITEM_NOT_FOUND' in capsys.readouterr().err


def test_completed_items_have_their_own_display_group(tmp_path):
    from academic_mail_agent.display import render_checklist
    with StudyStore(tmp_path / 'study.db') as store:
        store.save_documents([doc()])
        for item in store.list_items():
            store.set_status(item['id'], 'done')
        text = render_checklist(store.list_items(include_done=True), [])
    assert '已完成' in text and '- [x]' in text
    assert '逾期未完成' not in text and '其他未完成' not in text
