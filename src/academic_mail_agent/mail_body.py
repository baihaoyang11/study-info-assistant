"""Bounded IMAP BODYSTRUCTURE parsing and inert text decoding."""
import base64
import binascii
from dataclasses import dataclass
from html.parser import HTMLParser
import quopri
import re
import unicodedata

from .errors import MailError


def _values(raw: bytes):
    if not isinstance(raw, bytes) or len(raw) > 65536:
        raise MailError('PROTOCOL_ERROR')
    token = re.compile(rb'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^()\s"]+)')
    stack, result = [], []
    current = result
    pos = 0
    while pos < len(raw):
        if not raw[pos:].strip():
            break
        match = token.match(raw, pos)
        if not match:
            raise MailError('PROTOCOL_ERROR')
        value = match.group(1)
        pos = match.end()
        if value == b'(':
            if len(stack) >= 40:
                raise MailError('PROTOCOL_ERROR')
            nested = []
            current.append(nested)
            stack.append(current)
            current = nested
        elif value == b')':
            if not stack:
                raise MailError('PROTOCOL_ERROR')
            current = stack.pop()
        else:
            quoted = value.startswith(b'"')
            if quoted:
                value = re.sub(rb'\\(.)', rb'\1', value[1:-1])
            current.append(None if not quoted and value.upper() == b'NIL' else value.decode('utf-8', 'replace'))
    if stack:
        raise MailError('PROTOCOL_ERROR')
    return result


def parse_bodystructure(raw: bytes) -> list:
    values = _values(raw)
    if len(values) != 1 or not isinstance(values[0], list):
        raise MailError('PROTOCOL_ERROR')
    return values[0]


def fetch_structure(data, uid: str) -> list:
    if not isinstance(data, list) or not data or any(not isinstance(x, bytes) for x in data):
        raise MailError('PROTOCOL_ERROR')
    # Do not accept an unrelated second FETCH record in place of this message.
    values = _values(b' '.join(data))
    if len(values) != 2 or not isinstance(values[1], list):
        raise MailError('PROTOCOL_ERROR')
    attrs = values[1]
    if len(attrs) % 2:
        raise MailError('PROTOCOL_ERROR')
    pairs = list(zip(attrs[::2], attrs[1::2]))
    ids = [value for key, value in pairs if isinstance(key, str) and key.upper() == 'UID']
    structures = [value for key, value in pairs if isinstance(key, str) and key.upper() == 'BODYSTRUCTURE']
    if ids != [uid] or len(structures) != 1 or not isinstance(structures[0], list):
        raise MailError('PROTOCOL_ERROR')
    return structures[0]


@dataclass(frozen=True)
class TextPart:
    section: str
    content_type: str
    charset: str
    encoding: str
    size: int


def _named(params):
    if not isinstance(params, list):
        return False
    return any(isinstance(key, str) and key.upper().split('*', 1)[0] in ('NAME', 'FILENAME') for key in params[::2])


def _attached(disposition):
    return isinstance(disposition, list) and bool(disposition) and (
        str(disposition[0]).upper() == 'ATTACHMENT' or
        (len(disposition) > 1 and _named(disposition[1]))
    )


def text_parts(node: list, prefix: str = '') -> list[TextPart]:
    if not isinstance(node, list) or not node:
        raise MailError('PROTOCOL_ERROR')
    if isinstance(node[0], list):
        count = 0
        while count < len(node) and isinstance(node[count], list):
            count += 1
        if count >= len(node) or not isinstance(node[count], str):
            raise MailError('PROTOCOL_ERROR')
        if (len(node) > count + 1 and _named(node[count + 1])) or (len(node) > count + 2 and _attached(node[count + 2])):
            return []
        groups = [text_parts(child, f'{prefix}.{i}' if prefix else str(i)) for i, child in enumerate(node[:count], 1)]
        if node[count].upper() == 'ALTERNATIVE':
            for group in groups:
                plain = [part for part in group if part.content_type == 'text/plain']
                if plain:
                    return plain
            return next((group for group in groups if group), [])
        return [part for group in groups for part in group]
    if len(node) < 7:
        raise MailError('PROTOCOL_ERROR')
    if str(node[0]).upper() != 'TEXT' or str(node[1]).upper() not in ('PLAIN', 'HTML'):
        return []  # Includes MESSAGE/RFC822: never descend into attached mail.
    if _named(node[2]) or (len(node) > 9 and _attached(node[9])):
        return []
    charset = 'utf-8'
    if isinstance(node[2], list):
        params = node[2]
        for key, value in zip(params[::2], params[1::2]):
            if str(key).upper() == 'CHARSET' and isinstance(value, str):
                charset = value
    if not isinstance(node[6], str) or not re.fullmatch(r'\d{1,10}', node[6]):
        raise MailError('PROTOCOL_ERROR')
    return [TextPart(prefix or 'TEXT', 'text/' + str(node[1]).lower(), charset, str(node[5]).lower(), int(node[6]))]


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self.hidden += 1
        if tag in ('br', 'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3') and not self.hidden:
            self.chunks.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'li', 'tr') and not self.hidden:
            self.chunks.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.chunks.append(data)


def decode_text(raw: bytes, charset: str, encoding: str, content_type: str) -> str:
    try:
        if encoding == 'base64':
            raw = base64.b64decode(re.sub(rb'\s+', b'', raw), validate=True)
        elif encoding == 'quoted-printable':
            raw = quopri.decodestring(raw)
        elif encoding not in ('7bit', '8bit', 'binary'):
            raise MailError('BODY_DECODE_ERROR')
    except (binascii.Error, ValueError):
        raise MailError('BODY_DECODE_ERROR') from None
    try:
        text = raw.decode(charset, 'replace')
    except (LookupError, UnicodeError):
        text = raw.decode('utf-8', 'replace')
    if content_type == 'text/html':
        parser = _HTMLText()
        parser.feed(text)
        text = ''.join(parser.chunks)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = ''.join(c for c in text if c in '\n\t' or not unicodedata.category(c).startswith('C'))
    return '\n'.join(line.strip() for line in text.splitlines() if line.strip())
