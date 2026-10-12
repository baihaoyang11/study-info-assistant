from datetime import datetime, timezone, timedelta

from .parsing import safe_header

LABELS = {'assignment': '作业', 'exam': '考试', 'deadline': '截止事项', 'notice': '通知待办'}
SOURCES = {'qq': 'QQ', 'mock': 'Mock', 'canvas_manual': 'Canvas 手动导入'}


def render_checklist(items, source_status, *, digest=False):
    now = datetime.now(timezone.utc)
    lines = ['学业清单（本地规则提取，保留来源证据）', 'Canvas：仅手动导入，未自动检查学校平台。']
    if not source_status:
        lines.append('尚无采集/导入运行记录；空清单不代表没有学业任务。')
    for source in source_status:
        label = SOURCES.get(source['source'], source['source'])
        if source['status'] == 'failed':
            lines.append(f"{label}：最近采集失败（{source['details'].get('error_code', 'UNKNOWN')}），下列可能为历史数据。")
        else:
            info = source['details']
            count = info.get('documents', 0)
            lines.append(f"{label}：最近成功时间 {source['checked_at']}；本次处理 {count} 份来源。")
            if info.get('scope') == 'latest_messages':
                lines.append(f"  范围：最近最多 {info['limit']} 封，非全部历史/完整增量同步；正文不完整 {info.get('incomplete_bodies', 0)} 封。")
    if not items:
        lines.append('当前本地没有未完成事项，请结合上方来源状态与覆盖范围核对。')
        return '\n'.join(lines)
    groups = {'逾期未完成': [], '未来七天': [], '待核对': [], '其他未完成': [], '已完成': []}
    for item in items:
        group = '其他未完成'
        if item['status'] == 'done':
            group = '已完成'
        elif item['needs_review']:
            group = '待核对'
        elif item['due_at']:
            due = datetime.fromisoformat(item['due_at'].replace('Z', '+00:00'))
            if due < now:
                group = '逾期未完成'
            elif due <= now + timedelta(days=7):
                group = '未来七天'
        groups[group].append(item)
    for label, rows in groups.items():
        if not rows:
            continue
        lines.append('\n' + label)
        for item in rows:
            mark = 'x' if item['status'] == 'done' else ' '
            due = item['due_at'] or item['due_date'] or '未知'
            lines.append(f"- [{mark}] {safe_header(item['title'])} | {LABELS[item['kind']]} | 截止/发生时间：{due}")
            lines.append(f"  来源：{SOURCES[item['source']]} · {safe_header(item['source_ref'])} | ID：{item['id']}")
            if item['needs_review']:
                lines.append('  待核对：' + safe_header(item['review_reason']))
            lines.append('  证据：' + safe_header(item['evidence']))
    return '\n'.join(lines)
