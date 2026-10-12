class MailError(Exception):
    """Fixed, credential-free errors suitable for local display."""

    MESSAGES = {
        'REAL_CONNECTION_DISABLED': '真实邮箱连接未获显式授权。',
        'CONFIG_ERROR': 'QQ 配置无效或缺少账号/授权码。',
        'TLS_ERROR': 'TLS 证书或安全连接校验失败。',
        'NETWORK_ERROR': '网络连接失败或超时。',
        'AUTH_ERROR': '邮箱认证失败，请检查 IMAP 授权码。',
        'PROTOCOL_ERROR': '邮箱返回了无法处理的响应。',
        'NOT_CONNECTED': '尚未建立只读邮箱连接。',
        'LIMIT_ERROR': '读取数量必须为 1 到 10。',
    }

    def __init__(self, code):
        self.code = code if code in self.MESSAGES else 'PROTOCOL_ERROR'
        super().__init__(f'{self.code}: {self.MESSAGES[self.code]}')
