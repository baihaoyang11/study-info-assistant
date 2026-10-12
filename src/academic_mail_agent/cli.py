import argparse
import json
from pathlib import Path
import sys

from .config import load_qq_config
from .errors import MailError
from .mock import MockMailConnector
from .qq_imap import QQIMAPConnector
from .storage import StudyStore
from .study_service import sync_into
from .manual_import import import_canvas_document
from .display import render_checklist
from . import __version__


def bounded_limit(value):
    try:
        limit = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('limit must be 1..10') from None
    if not 1 <= limit <= 10:
        raise argparse.ArgumentTypeError('limit must be 1..10')
    return limit


def sync_limit(value):
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('sync limit must be 1..100') from None
    if not 1 <= count <= 100:
        raise argparse.ArgumentTypeError('sync limit must be 1..100')
    return count


def database_option(parser):
    parser.add_argument('--db', type=Path, default=Path('data/study.sqlite3'), help='仅本机保存的 SQLite 数据库')


def main(argv=None):
    parser = argparse.ArgumentParser(description='QQ 只读学业清单工具；默认 Mock，Canvas 仅手动导入。')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('diagnose', help='无网络诊断，不加载邮箱配置')
    listing = sub.add_parser('list', help='列出最近邮件头，默认 Mock')
    listing.add_argument('--provider', choices=['mock', 'qq'], default='mock')
    listing.add_argument('--allow-real-mailbox', action='store_true', help='显式允许本次连接真实邮箱')
    listing.add_argument('--detail', action='store_true', help='本地显示主题；可能包含隐私')
    listing.add_argument('--limit', type=bounded_limit, default=10)
    listing.add_argument('--env-file', type=Path, help='QQ 配置文件，仅授权真实读取时加载')
    sync = sub.add_parser('sync', help='采集文本正文，保存本机并提取事项；默认 Mock')
    sync.add_argument('--provider', choices=['mock', 'qq'], default='mock')
    sync.add_argument('--allow-real-mailbox', action='store_true')
    sync.add_argument('--limit', type=sync_limit, default=50)
    sync.add_argument('--env-file', type=Path)
    database_option(sync)
    for command in ('todos', 'digest'):
        view = sub.add_parser(command, help='展示本机事项与来源覆盖范围，不连接任何服务')
        view.add_argument('--format', choices=['text', 'json'], default='text')
        view.add_argument('--include-done', action='store_true')
        database_option(view)
    complete = sub.add_parser('complete', help='仅修改本机事项的完成状态，不修改邮件')
    complete.add_argument('item_id')
    complete.add_argument('--reopen', action='store_true')
    database_option(complete)
    manual = sub.add_parser('import-canvas', help='导入用户提供的本地 TXT/Markdown，不连接 Canvas')
    manual.add_argument('path', type=Path)
    manual.add_argument('--source-name', help='人工来源名称，例如 COMP101 作业页')
    database_option(manual)
    args = parser.parse_args(argv)
    if args.command == 'diagnose':
        print(json.dumps({'version': __version__, 'default_provider': 'mock', 'network_used': False, 'qq_endpoint': 'imap.qq.com:993', 'read_only': True}, ensure_ascii=False))
        return 0
    if args.command is None:
        args = parser.parse_args(['list'])
    connector = None
    try:
        if args.command == 'sync':
            if args.provider == 'qq':
                if not args.allow_real_mailbox:
                    raise MailError('REAL_CONNECTION_DISABLED')
                connector = QQIMAPConnector(load_qq_config(args.env_file))
            else:
                connector = MockMailConnector()
            with StudyStore(args.db) as store:
                if args.provider == 'qq':
                    try:
                        connector.connect(allow_real=True)
                    except MailError as exc:
                        store.record_failure('qq', exc.code)
                        raise
                result = sync_into(store, connector, args.provider, args.limit)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == 'import-canvas':
            document = import_canvas_document(args.path, source_name=args.source_name)
            with StudyStore(args.db) as store:
                store.save_documents([document], run_source='canvas_manual', coverage={'scope': 'manual_file', 'documents': 1})
                count = len(store.list_items())
            print(json.dumps({'source': 'canvas_manual', 'documents_saved': 1, 'open_items': count}, ensure_ascii=False))
            return 0
        if args.command == 'complete':
            status = 'open' if args.reopen else 'done'
            with StudyStore(args.db) as store:
                store.set_status(args.item_id, status)
            print(json.dumps({'id': args.item_id, 'status': status}))
            return 0
        if args.command in ('todos', 'digest'):
            with StudyStore(args.db) as store:
                items = store.list_items(include_done=args.include_done)
                status = store.source_status()
            if args.format == 'json':
                print(json.dumps({'items': items, 'sources': status, 'canvas_mode': 'manual_only'}, ensure_ascii=False, indent=2))
            else:
                print(render_checklist(items, status, digest=args.command == 'digest'))
            return 0
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
