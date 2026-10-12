from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MailMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: Literal['qq', 'mock'] = 'qq'
    uid: str
    sender: str
    subject: str
    message_id: str | None = None
    date: datetime | None = None
    date_status: Literal['known', 'unknown'] = 'unknown'
