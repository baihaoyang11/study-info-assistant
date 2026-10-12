from datetime import datetime, date, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MailMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: Literal['qq', 'mock'] = 'qq'
    uid: str
    sender: str
    subject: str
    message_id: str | None = None
    date: datetime | None = None
    date_status: Literal['known', 'unknown'] = 'unknown'


class MailDocument(MailMetadata):
    account_id: str
    uidvalidity: str
    body: str
    body_status: Literal['complete', 'partial', 'unsupported'] = 'complete'


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_key: str
    source: Literal['qq', 'mock', 'canvas_manual']
    title: str
    body: str
    source_ref: str
    received_at: datetime | None = None
    body_status: Literal['complete', 'partial', 'unsupported'] = 'complete'
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StudyItem(BaseModel):
    id: str
    source_key: str
    title: str
    kind: Literal['assignment', 'exam', 'deadline', 'notice']
    course: str | None = None
    due_at: datetime | None = None
    due_date: date | None = None
    evidence: str
    needs_review: bool = True
    review_reason: str
    status: Literal['open', 'done'] = 'open'
