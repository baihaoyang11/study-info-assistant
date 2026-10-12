import hashlib
from pathlib import Path
import unicodedata

from .errors import MailError
from .models import SourceDocument
from .parsing import safe_header


def import_canvas_document(path: Path | str, *, source_name: str | None = None) -> SourceDocument:
    """Only a user-supplied local UTF-8 text file. No URLs or Canvas requests."""
    try:
        path = Path(path).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in ('.txt', '.md') or path.stat().st_size > 1048576:
            raise MailError('IMPORT_ERROR')
        raw = path.read_bytes()
        if len(raw) > 1048576:
            raise MailError('IMPORT_ERROR')
        text = raw.decode('utf-8-sig')
        text = ''.join(c for c in text if c in '\n\r\t' or not unicodedata.category(c).startswith('C'))
        name = safe_header(source_name or path.stem)
        if not text.strip() or not name.strip():
            raise MailError('IMPORT_ERROR')
        key = hashlib.sha256(str(path).encode()).hexdigest()[:32]
        return SourceDocument(source_key='canvas_manual:' + key, source='canvas_manual', title=name, source_ref=name, body=text)
    except (OSError, UnicodeError, ValueError, RuntimeError):
        raise MailError('IMPORT_ERROR') from None
