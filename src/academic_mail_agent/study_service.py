from .errors import MailError
from .models import SourceDocument


def mail_source(message) -> SourceDocument:
    key = f'{message.provider}:{message.account_id}:INBOX:{message.uidvalidity}:{message.uid}'
    return SourceDocument(source_key=key, source=message.provider, title=message.subject, body=message.body, source_ref=f'INBOX UID {message.uid} / UIDVALIDITY {message.uidvalidity}', received_at=message.date, body_status=message.body_status)


def sync_into(store, connector, provider, limit):
    try:
        messages = connector.latest_messages(limit)
        documents = [mail_source(message) for message in messages]
        coverage = {'scope': 'latest_messages', 'limit': limit, 'documents': len(documents), 'incomplete_bodies': sum(d.body_status != 'complete' for d in documents)}
        store.save_documents(documents, run_source=provider, coverage=coverage)
        return {'provider': provider, 'documents_saved': len(documents), 'open_items': len(store.list_items()), 'coverage': coverage, 'canvas_mode': 'manual_only'}
    except MailError as exc:
        store.record_failure(provider, exc.code)
        raise
