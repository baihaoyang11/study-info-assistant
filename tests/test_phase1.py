import imaplib
import json
import ssl

import pytest

from academic_mail_agent.config import QQConfig
from academic_mail_agent.errors import MailError
from academic_mail_agent.parsing import parse_headers
from academic_mail_agent.qq_imap import QQIMAPConnector
from academic_mail_agent.cli import main


HEADER = (b'Date: Mon, 12 Oct 2026 09:00:00 +0800\r\n'
          b'From: =?utf-8?b?6ICB5biI?= <teacher@example.edu>\r\n'
          b'Subject: =?utf-8?b?5L2c5Lia?=\r\nMessage-ID: <demo@example.edu>\r\n\r\n')


class FakeIMAP:
    def __init__(self, search=None, fail=None):
        self.search = [b'11 2 10 1 3 4 5 6 7 8 9 11'] if search is None else search
        self.fail = fail
        self.calls = []

    def login(self, user, password):
        self.calls.append(('LOGIN',))
        if self.fail == 'login':
            raise imaplib.IMAP4.error('super-secret user@qq.com')
        return 'OK', [b'authenticated']

    def select(self, mailbox, readonly=False):
        self.calls.append(('SELECT', mailbox, readonly))
        return ('NO' if self.fail == 'select' else 'OK'), [b'11']

    def uid(self, command, *args):
        self.calls.append((command, *args))
        if self.fail == command:
            return 'NO', [b'super-secret']
        if command == 'SEARCH':
            return 'OK', self.search
        if self.fail == 'malformed':
            return 'OK', [None]
        if self.fail == 'mismatch':
            return 'OK', [(b'1 (UID 999 BODY[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)] {1}', HEADER), b')']
        if self.fail in ('suffix_uid', 'suffix_mismatch'):
            suffix_uid = args[0] if self.fail == 'suffix_uid' else '999'
            prefix = f'1 (BODY[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)] {{{len(HEADER)}}}'.encode()
            return 'OK', [(prefix, HEADER), f' UID {suffix_uid})'.encode()]
        return 'OK', [(f'1 (UID {args[0]} BODY[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)] {{{len(HEADER)}}}'.encode(), HEADER), b')']

    def logout(self):
        self.calls.append(('LOGOUT',))
        if self.fail == 'logout':
            raise OSError('super-secret')
        return 'BYE', [b'bye']

    def shutdown(self):
        self.calls.append(('SHUTDOWN',))


def connector(fake):
    return QQIMAPConnector(QQConfig(account='user@qq.com', authorization_code='super-secret'), imap_factory=lambda *a, **kw: fake)


def test_constructor_and_connect_require_explicit_authorization():
    fake = FakeIMAP()
    c = connector(fake)
    with pytest.raises(MailError, match='REAL_CONNECTION_DISABLED'):
        c.connect()
    assert fake.calls == []


def test_tls_and_only_latest_ten_readonly_header_requests():
    fake = FakeIMAP()
    captured = {}
    def factory(host, port, **kwargs):
        captured.update(host=host, port=port, **kwargs)
        return fake
    c = QQIMAPConnector(QQConfig(account='user@qq.com', authorization_code='super-secret'), imap_factory=factory)
    c.connect(allow_real=True)
    try:
        messages = c.latest_headers()
    finally:
        c.disconnect()
    assert captured['host'] == 'imap.qq.com' and captured['port'] == 993
    assert captured['ssl_context'].verify_mode == ssl.CERT_REQUIRED
    assert captured['ssl_context'].check_hostname is True
    assert captured['timeout'] == 15
    assert [m.uid for m in messages] == ['11', '10', '9', '8', '7', '6', '5', '4', '3', '2']
    assert ('SELECT', 'INBOX', True) in fake.calls
    assert ('SEARCH', None, 'ALL') in fake.calls
    requests = [call for call in fake.calls if call[0] == 'FETCH']
    assert len(requests) == 10
    assert all(call[2] == '(UID BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)])' for call in requests)
    assert set(call[0] for call in fake.calls) == {'LOGIN', 'SELECT', 'SEARCH', 'FETCH', 'LOGOUT'}


@pytest.mark.parametrize('search', [[b''], [None]])
def test_empty_mailbox(search):
    fake = FakeIMAP(search=search)
    c = connector(fake)
    c.connect(allow_real=True)
    assert c.latest_headers() == []
    c.disconnect()
    assert not any(x[0] == 'FETCH' for x in fake.calls)


@pytest.mark.parametrize('search', [[b'1 invalid'], [b'0'], [b'-1'], [b'4294967296'], ['1']])
def test_malformed_uid_search_is_rejected(search):
    c = connector(FakeIMAP(search=search))
    c.connect(allow_real=True)
    with pytest.raises(MailError, match='PROTOCOL_ERROR'):
        c.latest_headers()
    c.disconnect()


@pytest.mark.parametrize('fail', ['login', 'select', 'SEARCH', 'FETCH', 'malformed', 'mismatch'])
def test_server_failures_are_sanitized_and_cleaned_up(fail):
    fake = FakeIMAP(fail=fail)
    c = connector(fake)
    with pytest.raises(MailError) as caught:
        try:
            c.connect(allow_real=True)
            c.latest_headers()
        finally:
            c.disconnect()
    assert 'super-secret' not in str(caught.value)
    assert 'user@qq.com' not in str(caught.value)
    assert fake.calls[-1] == ('LOGOUT',)


@pytest.mark.parametrize('exc,code', [(ssl.SSLCertVerificationError('secret'), 'TLS_ERROR'), (TimeoutError('secret'), 'NETWORK_ERROR'), (OSError('secret'), 'NETWORK_ERROR')])
def test_connection_failures_are_sanitized(exc, code):
    def factory(*a, **kw):
        raise exc
    c = QQIMAPConnector(QQConfig(account='user@qq.com', authorization_code='super-secret'), imap_factory=factory)
    with pytest.raises(MailError, match=code) as caught:
        c.connect(allow_real=True)
    assert 'secret' not in str(caught.value)


def test_logout_failure_uses_shutdown_and_disconnect_is_idempotent():
    fake = FakeIMAP(fail='logout')
    c = connector(fake)
    c.connect(allow_real=True)
    c.disconnect()
    c.disconnect()
    assert fake.calls[-2:] == [('LOGOUT',), ('SHUTDOWN',)]


def test_mime_and_aware_date_parsing():
    m = parse_headers('7', HEADER)
    assert m.subject == '作业'
    assert m.sender == '老师 <teacher@example.edu>'
    assert m.date.isoformat() == '2026-10-12T09:00:00+08:00'
    assert m.message_id == '<demo@example.edu>'


def test_fetch_accepts_matching_uid_after_header_literal():
    c = connector(FakeIMAP(search=[b'7'], fail='suffix_uid'))
    c.connect(allow_real=True)
    try:
        assert [m.uid for m in c.latest_headers()] == ['7']
    finally:
        c.disconnect()


def test_fetch_rejects_mismatched_uid_after_header_literal():
    c = connector(FakeIMAP(search=[b'7'], fail='suffix_mismatch'))
    c.connect(allow_real=True)
    try:
        with pytest.raises(MailError, match='PROTOCOL_ERROR'):
            c.latest_headers()
    finally:
        c.disconnect()


@pytest.mark.parametrize('date', ['', 'nonsense', 'Mon, 12 Oct 2026 09:00:00', 'Mon, 12 Oct 2026 09:00:00 -0000'])
def test_missing_naive_or_bad_date_is_unknown(date):
    m = parse_headers('1', f'Date: {date}\r\nSubject: hi\r\n\r\n'.encode())
    assert m.date is None
    assert m.date_status == 'unknown'


def test_unknown_charset_and_terminal_controls_degrade_safely():
    m = parse_headers('1', b'Subject: =?nonesuch?q?hello=FF?=\r\nFrom: hi\x1b[31m\r\n\r\n')
    assert 'hello' in m.subject
    assert '\x1b' not in m.sender


def test_credentials_not_in_config_repr():
    assert 'super-secret' not in repr(QQConfig(account='user@qq.com', authorization_code='super-secret'))


@pytest.mark.parametrize('account', ['bad', 'user@gmail.com', 'user@qq.com\r\nNOOP'])
def test_config_rejects_non_qq_or_injected_accounts(account):
    with pytest.raises(ValueError):
        QQConfig(account=account, authorization_code='secret')


@pytest.mark.parametrize('args', [[], ['diagnose'], ['list'], ['list', '--provider', 'qq']])
def test_cli_safe_paths_do_not_load_credentials_or_connect(args, monkeypatch, capsys):
    def forbidden(*a, **kw):
        raise AssertionError('safe paths must not load credentials/connect')
    monkeypatch.setattr('academic_mail_agent.cli.load_qq_config', forbidden)
    monkeypatch.setattr(imaplib, 'IMAP4_SSL', forbidden)
    code = main(args)
    out = capsys.readouterr()
    assert code == (2 if 'qq' in args else 0)
    assert '作业提交提醒' not in out.out


def test_cli_mock_detail_is_explicit_and_warns(capsys):
    assert main(['list', '--detail']) == 0
    output = capsys.readouterr()
    assert '隐私' in output.err
    assert json.loads(output.out)['messages'][0]['subject'] == '作业提交提醒'


def test_cli_default_output_hides_subject(capsys):
    assert main(['list']) == 0
    messages = json.loads(capsys.readouterr().out)['messages']
    assert messages and all(m['subject'] == '[hidden]' for m in messages)


@pytest.mark.parametrize('limit', ['0', '11', '-1'])
def test_cli_limit_rejected_without_network(limit, capsys):
    with pytest.raises(SystemExit) as caught:
        main(['list', '--limit', limit])
    assert caught.value.code == 2
