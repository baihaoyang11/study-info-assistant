from email.header import decode_header
from email.parser import BytesHeaderParser
from email.utils import parsedate_to_datetime
import unicodedata

from .models import MailMetadata


def safe_header(value: str | None) -> str:
    parts = []
    try:
        chunks = decode_header(value or '')
    except (ValueError, UnicodeError):
        chunks = [(value or '', None)]
    for chunk, charset in chunks:
        if isinstance(chunk, bytes):
            try:
                chunk = chunk.decode(charset or 'ascii', errors='replace')
            except (LookupError, UnicodeError):
                chunk = chunk.decode('utf-8', errors='replace')
        parts.append(chunk)
    text = ''.join(parts).replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
    return ''.join(c for c in text if not unicodedata.category(c).startswith('C'))


def parse_headers(uid: str, raw: bytes) -> MailMetadata:
    headers = BytesHeaderParser().parsebytes(raw)
    date = None
    try:
        parsed = parsedate_to_datetime(headers.get('Date', ''))
        if parsed is not None and parsed.tzinfo is not None and parsed.utcoffset() is not None:
            date = parsed
    except (TypeError, ValueError, OverflowError):
        pass
    return MailMetadata(uid=uid, sender=safe_header(headers.get('From')), subject=safe_header(headers.get('Subject')), message_id=safe_header(headers.get('Message-ID')) or None, date=date, date_status='known' if date else 'unknown')
