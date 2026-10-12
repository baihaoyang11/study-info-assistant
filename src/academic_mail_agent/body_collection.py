import hashlib
import imaplib
import re
import ssl

from .errors import MailError
from .mail_body import fetch_structure, text_parts, decode_text
from .models import MailDocument
from .parsing import parse_headers

PART_LIMIT = 262144
MESSAGE_LIMIT = 1048576


def _literal(data, uid: str, *, section: str | None = None) -> bytes:
    if not isinstance(data, list):
        raise MailError('PROTOCOL_ERROR')
    literals = [(i, x) for i, x in enumerate(data) if isinstance(x, tuple) and len(x) == 2]
    if len(literals) != 1:
        raise MailError('PROTOCOL_ERROR')
    index, (envelope, raw) = literals[0]
    if index != 0 or not isinstance(envelope, bytes) or not isinstance(raw, bytes):
        raise MailError('PROTOCOL_ERROR')
    if section is not None:
        pattern = rb'BODY\[' + re.escape(section.encode()) + rb'\](?:<0>)?\s*\{([0-9]+)\}\s*$'
        match = re.search(pattern, envelope, re.I)
        if not match or int(match.group(1)) != len(raw):
            raise MailError('PROTOCOL_ERROR')
    tail = data[index + 1:]
    if any(not isinstance(x, bytes) for x in tail):
        raise MailError('PROTOCOL_ERROR')
    ids = re.findall(rb'\bUID ([0-9]+)\b', envelope + b' '.join(tail))
    if ids != [uid.encode()]:
        raise MailError('PROTOCOL_ERROR')
    return raw


def collect_messages(connector, limit: int = 50) -> list[MailDocument]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise MailError('SYNC_LIMIT_ERROR')
    client = connector._client
    if client is None:
        raise MailError('NOT_CONNECTED')
    try:
        generation = client.response('UIDVALIDITY')
        if not isinstance(generation, tuple) or len(generation) != 2 or not isinstance(generation[1], list) or len(generation[1]) != 1:
            raise MailError('PROTOCOL_ERROR')
        value = generation[1][0]
        if not isinstance(value, bytes) or not re.fullmatch(rb'[0-9]{1,10}', value) or not 1 <= int(value) <= 4294967295:
            raise MailError('PROTOCOL_ERROR')
        uidvalidity = str(int(value))
        data = connector._ok(client.uid('SEARCH', None, 'ALL'))
        if not isinstance(data, list) or any(x is not None and not isinstance(x, bytes) for x in data):
            raise MailError('PROTOCOL_ERROR')
        tokens = b' '.join(x for x in data if x is not None).split()
        if any(not re.fullmatch(rb'[0-9]{1,10}', x) or not 1 <= int(x) <= 4294967295 for x in tokens):
            raise MailError('PROTOCOL_ERROR')
        account_id = hashlib.sha256(connector.config.account.lower().encode()).hexdigest()[:24]
        documents = []
        for number in sorted({int(x) for x in tokens}, reverse=True)[:limit]:
            uid = str(number)
            header_data = connector._ok(client.uid('FETCH', uid, '(UID BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)])'))
            header_raw = _literal(header_data, uid, section='HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)')
            if len(header_raw) > 65536:
                raise MailError('PROTOCOL_ERROR')
            metadata = parse_headers(uid, header_raw)
            structure_data = connector._ok(client.uid('FETCH', uid, '(UID BODYSTRUCTURE)'))
            parts = text_parts(fetch_structure(structure_data, uid))
            chunks, total = [], 0
            status = 'complete' if parts else 'unsupported'
            if len(parts) > 32:
                status = 'partial'
            for part in parts[:32]:
                if part.size > PART_LIMIT or total + part.size > MESSAGE_LIMIT:
                    status = 'partial'
                    continue
                query = f'(UID BODY.PEEK[{part.section}]<0.{PART_LIMIT}>)'
                raw = _literal(connector._ok(client.uid('FETCH', uid, query)), uid, section=part.section)
                if len(raw) > PART_LIMIT or total + len(raw) > MESSAGE_LIMIT:
                    raise MailError('PROTOCOL_ERROR')
                total += len(raw)
                if len(raw) != part.size:
                    status = 'partial'
                try:
                    chunks.append(decode_text(raw, part.charset, part.encoding, part.content_type))
                except MailError as exc:
                    if exc.code != 'BODY_DECODE_ERROR':
                        raise
                    status = 'partial'
            documents.append(MailDocument(**metadata.model_dump(), account_id=account_id, uidvalidity=uidvalidity, body='\n\n'.join(chunks), body_status=status))
        return documents
    except ssl.SSLError:
        raise MailError('TLS_ERROR') from None
    except OSError:
        raise MailError('NETWORK_ERROR') from None
    except (imaplib.IMAP4.error, ValueError, TypeError):
        raise MailError('PROTOCOL_ERROR') from None
