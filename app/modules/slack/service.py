from collections import Counter, defaultdict

from app.config import MAX_ROWS
from app.errors import InspectionError
from app.reasons import cell
from app.modules.trace.units import distance, scaled
from .reader import KINDS, read_slack_rows


def normalize(fields):
    row = {key: cell(value) for key, value in fields.items()}
    if row['kind'] not in KINDS:
        raise ValueError('BAD_KIND')
    length_mm = scaled(row['length_m'], 1000, 0, 500_000_000)
    if row['kind'] == 'CLEAR' and length_mm:
        raise ValueError('CLEAR_NOT_ZERO')
    return {'id': row['coil_id'], 'route_mm': distance(row['route_m'], 'm'),
            'length_mm': length_mm, 'kind': row['kind']}


def receive_slack(text):
    """Parse the slack registry; duplicate entries are deduped, conflicts withdrawn like trace events."""
    grouped, issues, counts = defaultdict(list), [], Counter()

    def mark(line, raw, code):
        issues.append({'source': 'slack', 'line': line, 'code': code, 'raw': raw})

    for line, raw, values, reason in read_slack_rows(text):
        counts['input'] += 1
        if counts['input'] > MAX_ROWS:
            raise InspectionError('ROW_LIMIT', 'slack')
        if reason in {'BLANK', 'REPEATED_HEADER'}:
            counts[reason] += 1
            continue
        if reason:
            mark(line, raw, reason)
            continue
        try:
            row = normalize(values)
        except ValueError as exc:
            mark(line, raw, str(exc))
            continue
        grouped[row['id']].append((row, line, raw))
    entries = []
    for group in grouped.values():
        first, *others = group
        if any(other[0] != first[0] for other in others):
            for _, line, raw in group:
                mark(line, raw, 'CONFLICTING_EVENT')
            continue
        row, line, raw = first
        entries.append({**row, 'line': line, 'raw': raw})
        for _, line, raw in others:
            mark(line, raw, 'DUPLICATE_EVENT')
    entries.sort(key=lambda row: (row['route_mm'], row['id']))
    meta = {'input': counts['input'], 'blank': counts['BLANK'], 'sections': counts['REPEATED_HEADER'] + 1,
            'accepted': len(entries), 'isolated': len(issues),
            'state': 'PROCESSED' if entries or issues else 'HEADER_ONLY'}
    meta['balanced'] = meta['input'] == meta['blank'] + meta['sections'] - 1 + meta['accepted'] + meta['isolated']
    return {'entries': entries, 'meta': meta, 'isolated': sorted(issues, key=lambda row: row['line']),
            'kind_counts': dict(Counter(row['kind'] for row in entries))}
