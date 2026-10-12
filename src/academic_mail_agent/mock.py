from datetime import datetime

from .errors import MailError
from .models import MailMetadata, MailDocument


class MockMailConnector:
    """Fixed synthetic data; no credentials, filesystem access or network."""

    def latest_headers(self, limit: int = 10):
        if type(limit) is not int or not 1 <= limit <= 10:
            raise MailError('LIMIT_ERROR')
        return [
            MailMetadata(provider='mock', uid='2', sender='老师 <teacher@example.edu>', subject='作业提交提醒', message_id='<mock-2@example.edu>', date=datetime.fromisoformat('2026-10-12T09:00:00+08:00'), date_status='known'),
            MailMetadata(provider='mock', uid='1', sender='教务 <office@example.edu>', subject='课程通知'),
        ][:limit]

    def latest_messages(self, limit: int = 50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise MailError('SYNC_LIMIT_ERROR')
        bodies = ['COMP101 作业提交，截止 2026-10-20 18:00 +08:00\nCOMP101 期中考试：2026-10-22 09:00 +08:00', 'COMP102 作业截止下周五，需要核对 Canvas 原文。']
        return [MailDocument(**meta.model_dump(), account_id='demo', uidvalidity='1', body=body) for meta, body in zip(self.latest_headers(2), bodies)][:limit]
