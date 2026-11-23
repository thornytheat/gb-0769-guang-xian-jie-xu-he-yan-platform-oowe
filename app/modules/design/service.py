from app.modules.loss.verdict import verdict
from app.modules.pairs.optimal import best_pairs
from app.modules.slack.registry import build_registry, covered, to_route_half


def reconcile(calibrated, joined, loss, slack=None):
    points, measurements = calibrated['aligned']['design'], loss['rows']
    tolerance = calibrated['settings']['design_tol_mm']
    length = calibrated['settings']['length_mm']
    registry = build_registry(slack['entries'], length) if slack else {'present': False}
    coils = registry.get('coils', [])
    corrected = [
        {**row, 'route_half_mm': to_route_half(row['midpoint_half_mm'], coils)}
        for row in measurements
    ]
    valid = [row for row in points if not row.get('code')]
    links = best_pairs([r['chain_mm'] * 2 for r in valid],
                       [r['route_half_mm'] for r in corrected], tolerance * 2)
    mapped = {valid[i]['id']: corrected[j] for i, j in links}
    used = {j for _, j in links}
    rows = []
    for point in points:
        pair = mapped.get(point['id'])
        is_covered = covered(point['chain_mm'], registry)
        near_singles = [dict(id=r['id'], source=r['source'], line=r['line']) for r in joined['singles']
                        if abs(r['chain_mm'] - point['chain_mm']) <= tolerance and not point.get('code')]
        if point.get('code'):
            code = point['code']
        elif registry['present'] and not is_covered:
            code = 'PENDING_SLACK_RECORDS'
        elif not pair:
            code = 'SINGLE_SIDE_ONLY' if near_singles else 'NO_COUPLED_EVIDENCE'
        else:
            code = verdict(pair['net_double_mdb'], point['limit_mdb'])
        bucket = {'PASS': 'passed', 'OVER_LIMIT': 'over_limit'}.get(code, 'missing')
        rows.append({'joint': point['id'], 'chain_mm': point['chain_mm'], 'design_line': point['line'],
                     'limit_mdb': point['limit_mdb'], 'pair': pair['pair'] if pair else None,
                     'net_db': pair['net_db'] if pair else None, 'code': code, 'bucket': bucket,
                     'near_singles': near_singles,
                     'a_line': pair['a']['line'] if pair else None,
                     'b_line': pair['b']['line'] if pair else None,
                     'gain_ends': pair['gain_ends'] if pair else [],
                     'evidence_ready': code != 'PENDING_SLACK_RECORDS',
                     'slack_covered': (not registry['present']) or is_covered,
                     'coil_ids': [coil['id'] for coil in coils if coil['route_mm'] <= point['chain_mm']]})
    totals = {key: sum(r['bucket'] == key for r in rows) for key in ('passed', 'over_limit', 'missing')}
    orphans = [r for i, r in enumerate(corrected) if i not in used]
    measured = len(calibrated['aligned']['a']) + len(calibrated['aligned']['b'])
    pending = sum(r['code'] == 'PENDING_SLACK_RECORDS' for r in rows)
    return {'design_count': len(points), **totals, 'balanced': len(points) == sum(totals.values()), 'rows': rows,
            'orphans': orphans, 'orphan_pairs': len(orphans), 'singles': joined['singles'],
            'single_count': joined['single_count'],
            'measurements': measured,
            'measurements_balanced': measured == 2 * (len(mapped) + len(orphans)) + joined['single_count'],
            'slack': _registry_view(registry) if slack else {'present': False},
            'pending_slack': pending,
            'ready_count': sum(r['evidence_ready'] for r in rows)}


def _registry_view(registry):
    return {'present': True,
            'coil_count': len(registry['coils']),
            'clear_count': len(registry['clears']),
            'coverage_mm': registry['coverage_mm'],
            'total_coil_mm': registry['total_coil_mm'],
            'entries': [{'id': row['id'], 'kind': row['kind'], 'route_mm': row['route_mm'],
                         'length_mm': row['length_mm'], 'line': row['line'],
                         'cumulative_mm': row['cumulative_mm']}
                        for row in sorted(registry['entries'], key=lambda item: (item['route_mm'], item['id']))]}
