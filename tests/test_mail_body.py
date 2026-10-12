import base64
import pytest

from academic_mail_agent.config import QQConfig
from academic_mail_agent.errors import MailError
from academic_mail_agent.qq_imap import QQIMAPConnector
from academic_mail_agent.mail_body import text_parts, parse_bodystructure, decode_text
from test_phase1 import FakeIMAP, HEADER


PLAIN = b'("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "BASE64" 64 2 NIL NIL NIL)'
HTML = b'("TEXT" "HTML" ("CHARSET" "UTF-8") NIL NIL "8BIT" 50 2 NIL NIL NIL)'
ATTACH = b'("TEXT" "PLAIN" ("NAME" "secret.txt") NIL NIL "BASE64" 999 2 NIL ("ATTACHMENT" ("FILENAME" "secret.txt")) NIL)'


def test_multipart_prefers_plain_alternative_and_skips_attachment():
    structure = b'(' + b'(' + PLAIN + HTML + b' "ALTERNATIVE" NIL NIL)' + ATTACH + b' "MIXED" NIL NIL)'
    parts = text_parts(parse_bodystructure(structure))
    assert [(p.section, p.content_type) for p in parts] == [('1.1', 'text/plain')]


def test_attached_multipart_is_not_read():
    structure = b'(' + PLAIN + b' "MIXED" NIL ("ATTACHMENT" NIL))'
    assert text_parts(parse_bodystructure(structure)) == []


def test_extended_filename_parameter_is_not_body_text():
    attached = b'("TEXT" "PLAIN" ("NAME*" "UTF-8\'\'secret.txt") NIL NIL "8BIT" 12 1 NIL NIL)'
    assert text_parts(parse_bodystructure(attached)) == []


def test_html_conversion_ignores_active_content_and_preserves_lines():
    html = '<p>课程作业</p><script>secret()</script><style>bad</style><p>截止 2026-10-20 18:00</p>'
    text = decode_text(html.encode(), 'utf-8', '8bit', 'text/html')
    assert '课程作业' in text and '截止' in text
    assert '\n' in text and 'secret' not in text and 'bad' not in text


def test_base64_chinese_and_unknown_charset():
    assert decode_text(base64.b64encode('作业'.encode()), 'utf-8', 'base64', 'text/plain') == '作业'
    assert decode_text(b'hello\xff', 'unknown', '8bit', 'text/plain').startswith('hello')


@pytest.mark.parametrize('raw', [b'(', b'("TEXT"', b'("x"))', b'{' + b'9' * 20 + b'}'])
def test_malformed_bodystructure_is_rejected(raw):
    with pytest.raises(MailError, match='PROTOCOL_ERROR'):
        parse_bodystructure(raw)


class BodyIMAP(FakeIMAP):
    def __init__(self, structure=PLAIN, mismatched=False):
        super().__init__(search=[b'7'])
        raw = base64.b64encode('COMP101 作业截止 2026-10-20 18:00 +08:00'.encode())
        self.structure = structure.replace(b' 64 ', f' {len(raw)} '.encode())
        self.mismatched = mismatched

    def response(self, code):
        self.calls.append(('RESPONSE', code))
        return code, [b'777']

    def uid(self, command, *args):
        if command == 'FETCH' and 'BODYSTRUCTURE' in args[1]:
            self.calls.append((command, *args))
            return 'OK', [b'1 (UID 7 BODYSTRUCTURE ' + self.structure + b')']
        if command == 'FETCH' and 'BODY.PEEK[TEXT]' in args[1]:
            self.calls.append((command, *args))
            raw = base64.b64encode('COMP101 作业截止 2026-10-20 18:00 +08:00'.encode())
            uid = '999' if self.mismatched else '7'
            return 'OK', [(f'1 (BODY[TEXT]<0> {{{len(raw)}}}'.encode(), raw), f' UID {uid})'.encode()]
        return super().uid(command, *args)


def make(fake):
    return QQIMAPConnector(QQConfig(account='test@qq.com', authorization_code='fake'), imap_factory=lambda *a, **kw: fake)


def test_body_collection_is_peek_only_with_generation_and_account_identity():
    fake = BodyIMAP()
    c = make(fake)
    c.connect(allow_real=True)
    try:
        docs = c.latest_messages(limit=3)
    finally:
        c.disconnect()
    assert len(docs) == 1 and 'COMP101 作业截止' in docs[0].body
    assert docs[0].uidvalidity == '777' and docs[0].uid == '7'
    assert docs[0].account_id != 'test@qq.com'
    assert docs[0].body_status == 'complete'
    queries = [x[2] for x in fake.calls if x[0] == 'FETCH']
    assert '(UID BODYSTRUCTURE)' in queries
    assert '(UID BODY.PEEK[TEXT]<0.262144>)' in queries
    assert not any('BODY[]' in q or 'RFC822)' in q for q in queries)
    assert all('PEEK' in q or 'BODYSTRUCTURE' in q for q in queries)
    assert ('SELECT', 'INBOX', True) in fake.calls
    assert fake.calls[-1] == ('LOGOUT',)


def test_body_uid_mismatch_is_rejected():
    c = make(BodyIMAP(mismatched=True))
    c.connect(allow_real=True)
    try:
        with pytest.raises(MailError, match='PROTOCOL_ERROR'):
            c.latest_messages()
    finally:
        c.disconnect()


def test_large_text_is_skipped_and_marked_incomplete():
    fake = BodyIMAP(structure=PLAIN.replace(b' 64 ', b' 900000 '))
    c = make(fake)
    c.connect(allow_real=True)
    try:
        docs = c.latest_messages()
    finally:
        c.disconnect()
    assert docs[0].body == '' and docs[0].body_status == 'partial'
    assert not any(x[0] == 'FETCH' and 'BODY.PEEK[TEXT]' in x[2] for x in fake.calls)


def test_literal_for_wrong_body_section_is_not_accepted():
    from academic_mail_agent.body_collection import _literal
    with pytest.raises(MailError, match='PROTOCOL_ERROR'):
        _literal([(b'1 (UID 7 BODY[2]<0> {3}', b'bad'), b')'], '7', section='TEXT')


def test_corrupt_base64_is_not_silently_accepted():
    with pytest.raises(MailError, match='BODY_DECODE_ERROR'):
        decode_text(b'aGVsbG8=!!!!', 'utf-8', 'base64', 'text/plain')
