"""Local SQLite documents, source evidence, task state and run coverage."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .errors import MailError
from .extraction import extract_items
from .models import SourceDocument


class StudyStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.connection = None

    def __enter__(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.path, timeout=15)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute('PRAGMA foreign_keys=ON')
            self.connection.executescript('''
                CREATE TABLE IF NOT EXISTS documents (
                    source_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    source_key TEXT NOT NULL REFERENCES documents(source_key),
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL
                );
            ''')
            return self
        except (OSError, sqlite3.Error):
            if self.connection:
                self.connection.close()
            raise MailError('STORAGE_ERROR') from None

    def __exit__(self, *exc):
        self.connection.close()

    def _run(self, source, status, details):
        self.connection.execute('INSERT INTO runs(source,checked_at,status,details) VALUES(?,?,?,?)', (source, datetime.now(timezone.utc).isoformat(), status, json.dumps(details, ensure_ascii=False)))

    def save_documents(self, documents: list[SourceDocument], *, run_source=None, coverage=None):
        try:
            with self.connection:
                for document in documents:
                    self.connection.execute('INSERT INTO documents VALUES(?,?,?) ON CONFLICT(source_key) DO UPDATE SET source=excluded.source,payload=excluded.payload', (document.source_key, document.source, document.model_dump_json()))
                    self.connection.execute('UPDATE items SET active=0 WHERE source_key=?', (document.source_key,))
                    for item in extract_items(document):
                        self.connection.execute('INSERT INTO items(id,source_key,payload,status,active) VALUES(?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,active=1', (item.id, document.source_key, item.model_dump_json(), item.status))
                if run_source:
                    self._run(run_source, 'success', coverage or {'documents': len(documents)})
        except sqlite3.Error:
            raise MailError('STORAGE_ERROR') from None

    def record_failure(self, source, code):
        try:
            with self.connection:
                self._run(source, 'failed', {'error_code': code})
        except sqlite3.Error:
            raise MailError('STORAGE_ERROR') from None

    def document_count(self):
        return self.connection.execute('SELECT COUNT(*) FROM documents').fetchone()[0]

    def list_items(self, *, include_done=False):
        try:
            sql = 'SELECT i.payload,i.status,d.payload AS document FROM items i JOIN documents d USING(source_key) WHERE i.active=1'
            if not include_done:
                sql += " AND i.status='open'"
            sql += ' ORDER BY i.id'
            result = []
            for row in self.connection.execute(sql):
                item, document = json.loads(row['payload']), json.loads(row['document'])
                item.update(status=row['status'], source=document['source'], source_ref=document['source_ref'], collected_at=document['collected_at'])
                result.append(item)
            return sorted(result, key=lambda item: (item['due_at'] or item['due_date'] or '9999', item['title']))
        except (sqlite3.Error, ValueError, KeyError):
            raise MailError('STORAGE_ERROR') from None

    def set_status(self, item_id, status):
        if status not in ('open', 'done'):
            raise MailError('STORAGE_ERROR')
        try:
            with self.connection:
                changed = self.connection.execute('UPDATE items SET status=? WHERE id=? AND active=1', (status, item_id))
                if changed.rowcount == 0:
                    raise MailError('ITEM_NOT_FOUND')
        except sqlite3.Error:
            raise MailError('STORAGE_ERROR') from None

    def source_status(self):
        try:
            rows = self.connection.execute('SELECT source,checked_at,status,details FROM runs WHERE id IN (SELECT MAX(id) FROM runs GROUP BY source) ORDER BY source')
            return [dict(row, details=json.loads(row['details'])) for row in rows]
        except (sqlite3.Error, ValueError):
            raise MailError('STORAGE_ERROR') from None
