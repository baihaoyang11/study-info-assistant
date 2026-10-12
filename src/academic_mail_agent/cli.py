import argparse
import json
from pathlib import Path
import sys

from .config import load_qq_config
from .errors import MailError
from .mock import MockMailConnector
from .qq_imap import QQIMAPConnector


def bounded_limit(value):
    try:
        limit = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('limit must be 1..10') from None
    if not 1 <= limit <= 10:
        raise argparse.ArgumentTypeError('limit must be 1..10')
    return limit


def main(argv=None):
    parser = argparse.ArgumentParser(description='QQ 只读邮件头工具；默认 Mock，不连接邮箱。')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('diagnose', help='无网络诊断，不加载邮箱配置')
    listing = sub.add_parser('list', help='列出最近邮件头，默认 Mock')
    listing.add_argument('--provider', choices=['mock', 'qq'], default='mock')
    listing.add_argument('--allow-real-mailbox', action='store_true', help='显式允许本次连接真实邮箱')
    listing.add_argument('--detail', action='store_true', help='本地显示主题；可能包含隐私')
    listing.add_argument('--limit', type=bounded_limit, default=10)
    listing.add_argument('--env-file', type=Path, help='QQ 配置文件，仅授权真实读取时加载')
    args = parser.parse_args(argv)
    if args.command == 'diagnose':
        print(json.dumps({'version': '0.1.0', 'default_provider': 'mock', 'network_used': False, 'qq_endpoint': 'imap.qq.com:993', 'read_only': True}, ensure_ascii=False))
        return 0
    if args.command is None:
        args = parser.parse_args(['list'])
    connector = None
    try:
        if args.provider == 'qq':
            if not args.allow_real_mailbox:
                raise MailError('REAL_CONNECTION_DISABLED')
            connector = QQIMAPConnector(load_qq_config(args.env_file))
            connector.connect(allow_real=True)
        else:
            connector = MockMailConnector()
        messages = connector.latest_headers(args.limit)
        if args.detail:
            print('隐私提示：主题可能包含个人或学业信息，仅在本地显式显示。', file=sys.stderr)
        rows = []
        for message in messages:
            row = message.model_dump(mode='json')
            if not args.detail:
                row['subject'] = '[hidden]'
            rows.append(row)
        print(json.dumps({'provider': args.provider, 'messages': rows}, ensure_ascii=False, indent=2))
        return 0
    except MailError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('读取已取消。', file=sys.stderr)
        return 130
    finally:
        if isinstance(connector, QQIMAPConnector):
            connector.disconnect()
