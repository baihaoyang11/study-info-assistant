"""Conservative, local rules. Source text never becomes executable instructions."""
from datetime import datetime, timezone, timedelta
import hashlib
import re

from .models import SourceDocument, StudyItem
from .parsing import safe_header

DATE = re.compile(r'(?<!\d)(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?(?:[T\s]+(\d{1,2})[:：](\d{2})(?::(\d{2}))?)?')
OFFSET = re.compile(r'\s*(?:UTC|GMT)?\s*([+-])(\d{2}):?(\d{2})(?!\d)', re.I)
COURSE = re.compile(r'\b[A-Z]{2,8}[ -]?\d{3,5}[A-Z]?\b', re.I)
RULES = (
    ('exam', re.compile(r'考试|测验|期中|期末|\b(?:exam|quiz)\b', re.I)),
    ('assignment', re.compile(r'作业|报告提交|\b(?:assignment|homework|coursework)\b', re.I)),
    ('deadline', re.compile(r'截止|\b(?:deadline|due)\b', re.I)),
    ('notice', re.compile(r'报名|选课|注册|需提交|\b(?:register|enrol|submit)\b', re.I)),
)
DUE_CUE = re.compile(r'截止(?:时间)?|提交期限|\b(?:deadline|due(?:\s+date)?)\b', re.I)


def _date_info(line, kind):
    cue = DUE_CUE.search(line)
    if cue is None and kind != 'exam':
        return None, None, '没有明确的截止时间标识，需要核对'
    target = line[cue.end():] if cue else line
    matches = list(DATE.finditer(target))
    if len(matches) != 1:
        return None, None, '日期不明确或存在多个时间，需要核对来源'
    match = matches[0]
    if cue is None and re.search(r'发布|公布|\b(?:posted|published)\b', target[:match.start()], re.I):
        return None, None, '可能是通知发布时间，需核对实际考试时间'
    year, month, day, hour, minute, second = match.groups()
    try:
        value = datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0))
        if hour is None:
            return None, value.date(), '仅有日期，截止时刻与时区需要核对'
        tail = target[match.end():]
        offset = OFFSET.match(tail)
        zone = None
        if offset:
            sign, hours, minutes = offset.groups()
            if int(hours) > 23 or int(minutes) > 59:
                raise ValueError('bad offset')
            delta = timedelta(hours=int(hours), minutes=int(minutes))
            zone = timezone(delta if sign == '+' else -delta)
        elif re.match(r'\s*[(（]?\s*(?:北京时间|香港时间|HKT\b|Asia/(?:Shanghai|Hong_Kong))', tail, re.I):
            zone = timezone(timedelta(hours=8))
        elif re.match(r'\s*(?:Z\b|UTC\b|GMT\b)(?!\s*[+-])', tail, re.I):
            zone = timezone.utc
        if zone is None:
            return None, value.date(), '时间未标明时区，需要核对'
        return value.replace(tzinfo=zone), value.date(), ''
    except ValueError:
        return None, None, '日期或时间格式无效，需要核对'


def extract_items(document: SourceDocument) -> list[StudyItem]:
    if re.match(r'\s*(?:automatic reply|auto[ -]?reply|自动回复|自动回覆)', document.title, re.I):
        return []
    lines = [line.strip() for line in re.split(r'[\n;；]+', document.body) if line.strip()]
    candidates = []
    for line in lines:
        if re.match(r'^#{1,6}\s', line):
            continue
        if candidates and candidates[-1][0] in ('assignment', 'exam', 'notice') and re.match(r'^(?:截止|时间|日期|考试时间|due\b|deadline\b)', line, re.I):
            kind, previous = candidates[-1]
            candidates[-1] = (kind, previous + '\n' + line)
            continue
        for kind, pattern in RULES:
            if pattern.search(line):
                candidates.append((kind, line))
                break
    if not candidates:
        # A subject-only task stays tentative; generic course notices are ignored.
        for kind, pattern in RULES[:2]:
            if pattern.search(document.title):
                candidates.append((kind, document.title))
                break
    result, seen, occurrences = [], set(), {}
    for kind, raw_line in candidates:
        line = safe_header(raw_line)
        if (kind, line) in seen:
            continue
        seen.add((kind, line))
        match = COURSE.search(line) or COURSE.search(document.title)
        course = match.group().replace(' ', '').replace('-', '').upper() if match else None
        due_at, due_date, reason = _date_info(line, kind)
        identity = DUE_CUE.split(line, maxsplit=1)[0]
        identity = DATE.sub('', identity)
        identity = re.sub(r'[^\w\u4e00-\u9fff]+', '', identity).lower()
        occurrence_key = (kind, identity)
        ordinal = occurrences.get(occurrence_key, 0)
        occurrences[occurrence_key] = ordinal + 1
        stable = f'{document.source_key}|{kind}|{identity}'
        if ordinal:
            stable += f'|occurrence:{ordinal + 1}'
        item_id = hashlib.sha256(stable.encode()).hexdigest()[:32]
        reasons = [reason] if reason else []
        if not course:
            reasons.append('课程归属未确定')
        if document.body_status != 'complete':
            reasons.append('正文不完整，需要核对原始来源')
        if re.search(r'取消|无需提交|延期|\b(?:cancelled|canceled|postponed)\b', line, re.I):
            reasons.append('涉及取消或延期，需人工核对最终安排')
        if raw_line == document.title and not document.body.strip():
            reasons.append('仅根据主题识别，缺少正文证据')
        result.append(StudyItem(id=item_id, source_key=document.source_key, title=line[:180], kind=kind, course=course, due_at=due_at, due_date=due_date, evidence=raw_line[:2000], needs_review=bool(reasons), review_reason='；'.join(reasons)))
    return result
