from time import perf_counter

from app.errors import InspectionError
from app.pipeline import run
from .identity import record
from .storage import get, publish


def archive(database, materials):
    start = perf_counter()
    results = run(materials)
    return publish(database, record(materials, results, start))


def backfill_slack(database, identifier, slack_text):
    """Recompute an existing inspection after slack records are supplied.

    Backfills chain: when the source archive already carries a registry, the new
    rows are appended to it (duplicate ids rejected by the normal parser rules).
    Earlier snapshots stay untouched; repeating the same registry returns the
    already-published row without creating a duplicate.
    """
    if not isinstance(slack_text, str):
        raise InspectionError('TRACE_TEXT_REQUIRED', status=400)
    existing = get(database, identifier)
    previous = existing['material']['traces'].get('slack')
    merged = slack_text if previous is None else previous + slack_text
    materials = {**existing['material'],
                 'traces': {**existing['material']['traces'], 'slack': merged}}
    start = perf_counter()
    report, fresh = publish(database, record(materials, run(materials), start))
    return {'source_inspection_id': identifier, 'inspection_id': report['inspection_id'],
            'created': fresh, 'record': report}
