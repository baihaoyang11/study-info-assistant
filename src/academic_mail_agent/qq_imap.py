import imaplib
import re
import ssl

from .config import QQConfig
from .errors import MailError
from .parsing import parse_headers


class QQIMAPConnector:
    """A narrow read-only API. Construction never connects to a server."""

    def __init__(self, config: QQConfig, *, imap_factory=None):
        self.config = config
        self._factory = imap_factory
        self._client = None

    def connect(self, *, allow_real: bool = False):
        if allow_real is not True:
            raise MailError('REAL_CONNECTION_DISABLED')
        if self._client is not None:
            return
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        factory = self._factory or imaplib.IMAP4_SSL
        stage = 'network'
        try:
            self._client = factory('imap.qq.com', 993, ssl_context=context, timeout=self.config.timeout)
            # imaplib debug output can expose server responses; never enable it.
            self._client.debug = 0
            stage = 'login'
            self._ok(self._client.login(self.config.account, self.config.authorization_code.get_secret_value()), 'AUTH_ERROR')
            stage = 'select'
            self._ok(self._client.select('INBOX', readonly=True))
        except (MailError, ssl.SSLError, OSError, imaplib.IMAP4.error) as exc:
            self.disconnect()
            if isinstance(exc, MailError):
                raise MailError(exc.code) from None
            if isinstance(exc, ssl.SSLError):
                raise MailError('TLS_ERROR') from None
            if isinstance(exc, OSError):
                raise MailError('NETWORK_ERROR') from None
            raise MailError('AUTH_ERROR' if stage == 'login' else 'PROTOCOL_ERROR') from None

    @staticmethod
    def _ok(response, code='PROTOCOL_ERROR'):
        if not isinstance(response, tuple) or len(response) != 2 or response[0] != 'OK':
            raise MailError(code)
        return response[1]

    def latest_headers(self, limit: int = 10):
        if type(limit) is not int or not 1 <= limit <= 10:
            raise MailError('LIMIT_ERROR')
        if self._client is None:
            raise MailError('NOT_CONNECTED')
        try:
            data = self._ok(self._client.uid('SEARCH', None, 'ALL'))
            if not isinstance(data, list):
                raise MailError('PROTOCOL_ERROR')
            tokens = []
            for item in data:
                if item is None:
                    continue
                if not isinstance(item, bytes):
                    raise MailError('PROTOCOL_ERROR')
                tokens.extend(item.split())
            ids = set()
            for token in tokens:
                if not re.fullmatch(rb'[0-9]{1,10}', token) or not 1 <= int(token) <= 4294967295:
                    raise MailError('PROTOCOL_ERROR')
                ids.add(int(token))
            messages = []
            for uid in sorted(ids, reverse=True)[:limit]:
                fetched = self._ok(self._client.uid('FETCH', str(uid), '(UID BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)])'))
                if not isinstance(fetched, list):
                    raise MailError('PROTOCOL_ERROR')
                literals = [item for item in fetched if isinstance(item, tuple) and len(item) == 2]
                if len(literals) != 1:
                    raise MailError('PROTOCOL_ERROR')
                envelope, raw = literals[0]
                if not isinstance(envelope, bytes) or not isinstance(raw, bytes):
                    raise MailError('PROTOCOL_ERROR')
                # imaplib splits the record at the header literal. UID may
                # occur before or after it; never search the email text itself.
                literal_index = fetched.index(literals[0])
                suffix = fetched[literal_index + 1:]
                if any(not isinstance(item, bytes) for item in suffix):
                    raise MailError('PROTOCOL_ERROR')
                record = envelope + b' '.join(suffix)
                matches = re.findall(rb'\bUID ([0-9]+)\b', record)
                if len(matches) != 1 or int(matches[0]) != uid:
                    raise MailError('PROTOCOL_ERROR')
                messages.append(parse_headers(str(uid), raw))
            return messages
        except ssl.SSLError:
            raise MailError('TLS_ERROR') from None
        except OSError:
            raise MailError('NETWORK_ERROR') from None
        except (imaplib.IMAP4.error, ValueError, TypeError):
            raise MailError('PROTOCOL_ERROR') from None

    def disconnect(self):
        client, self._client = self._client, None
        if client is None:
            return
        try:
            response = client.logout()
            if not isinstance(response, tuple) or response[0] != 'BYE':
                client.shutdown()
        except (OSError, imaplib.IMAP4.error):
            try:
                client.shutdown()
            except (OSError, imaplib.IMAP4.error):
                pass

    def latest_messages(self, limit: int = 50):
        """Read only non-attachment text parts; keep the existing header API."""
        from .body_collection import collect_messages
        return collect_messages(self, limit)
