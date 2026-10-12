import imaplib
import json

import pytest

from academic_mail_agent import cli
from academic_mail_agent.canvas import MockCanvasConnector
from academic_mail_agent.config import QQConfig, load_qq_config
from academic_mail_agent.errors import MailError
from academic_mail_agent.qq_imap import QQIMAPConnector
from test_phase1 import FakeIMAP


def test_dotenv_is_explicit_does_not_mutate_environment_and_environment_wins(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('QQ_EMAIL=file@qq.com\nQQ_IMAP_AUTH_CODE=file-secret\nQQ_IMAP_TIMEOUT=20\n', encoding='utf-8')
    monkeypatch.setenv('QQ_EMAIL', 'env@qq.com')
    monkeypatch.delenv('QQ_IMAP_AUTH_CODE', raising=False)
    monkeypatch.delenv('QQ_IMAP_TIMEOUT', raising=False)
    config = load_qq_config(path)
    assert config.account == 'env@qq.com'
    assert config.authorization_code.get_secret_value() == 'file-secret'
    assert config.timeout == 20
    import os
    assert 'QQ_IMAP_AUTH_CODE' not in os.environ


def test_dotenv_does_not_search_ancestors(tmp_path, monkeypatch):
    (tmp_path / '.env').write_text('QQ_EMAIL=parent@qq.com\nQQ_IMAP_AUTH_CODE=secret\n', encoding='utf-8')
    child = tmp_path / 'child'
    child.mkdir()
    monkeypatch.chdir(child)
    for key in ('QQ_EMAIL', 'QQ_IMAP_AUTH_CODE', 'QQ_IMAP_TIMEOUT'):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(MailError, match='CONFIG_ERROR'):
        load_qq_config()


@pytest.mark.parametrize('timeout', [0, -1, 121, float('nan'), float('inf')])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(ValueError):
        QQConfig(account='user@qq.com', authorization_code='secret', timeout=timeout)


@pytest.mark.parametrize('secret', ['秘密', '', 'abc\r\nNOOP'])
def test_invalid_authorization_code_is_rejected(secret):
    with pytest.raises(ValueError):
        QQConfig(account='user@qq.com', authorization_code=secret)


def test_cli_real_path_uses_fake_transport_and_cleans_after_fetch_failure(monkeypatch, capsys):
    fake = FakeIMAP(fail='FETCH')
    monkeypatch.setattr(cli, 'load_qq_config', lambda *a: QQConfig(account='user@qq.com', authorization_code='super-secret'))
    monkeypatch.setattr(imaplib, 'IMAP4_SSL', lambda *a, **kw: fake)
    assert cli.main(['list', '--provider', 'qq', '--allow-real-mailbox']) == 2
    out = capsys.readouterr()
    assert out.out == ''
    assert 'super-secret' not in out.err
    assert 'user@qq.com' not in out.err
    assert fake.calls[-1] == ('LOGOUT',)


def test_cli_missing_configuration_is_sanitized(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('QQ_EMAIL', 'SECRET-INVALID-ACCOUNT')
    monkeypatch.setenv('QQ_IMAP_AUTH_CODE', 'SECRET-AUTH-CODE')
    monkeypatch.setenv('QQ_IMAP_TIMEOUT', 'bad')
    assert cli.main(['list', '--provider', 'qq', '--allow-real-mailbox', '--env-file', str(tmp_path / 'missing')]) == 2
    out = capsys.readouterr()
    assert 'CONFIG_ERROR' in out.err
    assert 'SECRET' not in out.err


def test_help_is_offline_and_does_not_load_configuration(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'load_qq_config', lambda *a: pytest.fail('help loaded config'))
    with pytest.raises(SystemExit) as caught:
        cli.main(['--help'])
    assert caught.value.code == 0


def test_interrupt_during_read_cleans_connection(monkeypatch, capsys):
    fake = FakeIMAP()
    original = fake.uid
    def interrupted(command, *args):
        if command == 'FETCH':
            raise KeyboardInterrupt()
        return original(command, *args)
    fake.uid = interrupted
    monkeypatch.setattr(cli, 'load_qq_config', lambda *a: QQConfig(account='user@qq.com', authorization_code='secret'))
    monkeypatch.setattr(imaplib, 'IMAP4_SSL', lambda *a, **kw: fake)
    assert cli.main(['list', '--provider', 'qq', '--allow-real-mailbox']) == 130
    assert fake.calls[-1] == ('LOGOUT',)


def test_disconnected_read_and_invalid_limits_are_rejected():
    connector = QQIMAPConnector(QQConfig(account='user@qq.com', authorization_code='secret'))
    with pytest.raises(MailError, match='NOT_CONNECTED'):
        connector.latest_headers()
    for limit in (0, 11, True, '1'):
        with pytest.raises(MailError, match='LIMIT_ERROR'):
            connector.latest_headers(limit)


def test_canvas_mock_is_fixed_offline_data():
    courses = MockCanvasConnector().list_courses()
    assert [course.model_dump() for course in courses] == [dict(id='mock-1', course_code='DEMO101', name='模拟课程', time_zone='Asia/Shanghai')]
