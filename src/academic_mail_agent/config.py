import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from .errors import MailError


class QQConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    account: str = Field(repr=False)
    authorization_code: SecretStr
    timeout: float = Field(default=15, gt=0, le=120, allow_inf_nan=False)

    @field_validator('account')
    @classmethod
    def qq_account(cls, value):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.+-]+@qq\.com', value, flags=re.IGNORECASE):
            raise ValueError('Invalid QQ account')
        return value

    @field_validator('authorization_code')
    @classmethod
    def nonempty_secret(cls, value):
        secret = value.get_secret_value()
        if not secret or not secret.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in secret):
            raise ValueError('Invalid authorization code')
        return value


def load_qq_config(env_file: Path | None = None) -> QQConfig:
    """Only called after the CLI's explicit real-mailbox authorization gate.

    Read one explicit file (default cwd/.env), never search parent directories;
    process environment wins, and dotenv interpolation is disabled.
    """
    try:
        path = env_file if env_file is not None else Path.cwd() / '.env'
        file_values = dotenv_values(path, interpolate=False) if path.is_file() else {}
        def value(key, default=None):
            return os.environ.get(key, file_values.get(key, default))
        return QQConfig(account=value('QQ_EMAIL'), authorization_code=value('QQ_IMAP_AUTH_CODE'), timeout=value('QQ_IMAP_TIMEOUT', 15))
    except (ValidationError, ValueError, OSError, UnicodeError):
        raise MailError('CONFIG_ERROR') from None
