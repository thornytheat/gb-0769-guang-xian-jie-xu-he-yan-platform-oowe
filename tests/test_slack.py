import pytest

from app.errors import InspectionError
from app.modules.slack.registry import build_registry, covered, to_route_half
from app.modules.slack.service import receive_slack

HEADER = 'coil_id,route_m,length_m,kind\n'


def test_coil_and_clear_entries_parse_with_cumulative_length():
    parsed = receive_slack(HEADER + 'S-01,100,10,COIL\nC-01,200,0,CLEAR\nS-02,260,5,COIL\n')
    assert parsed['meta']['balanced'] is True
    assert parsed['kind_counts'] == {'COIL': 2, 'CLEAR': 1}
    registry = build_registry(parsed['entries'], 1_000_000)
    assert [(r['id'], r['cumulative_mm']) for r in registry['coils']] == [('S-01', 10000), ('S-02', 15000)]
    assert registry['coverage_mm'] == 260000 and registry['total_coil_mm'] == 15000


def test_duplicate_slack_dedupes_conflict_withdraws_whole_group():
    parsed = receive_slack(HEADER + 'S-01,100,10,COIL\nS-01,100,10,COIL\nS-02,100,8,COIL\nS-02,101,8,COIL\n')
    assert [r['id'] for r in parsed['entries']] == ['S-01']
    assert [r['code'] for r in parsed['isolated']] == ['DUPLICATE_EVENT', 'CONFLICTING_EVENT', 'CONFLICTING_EVENT']


def test_clear_requires_zero_length_and_known_kind():
    parsed = receive_slack(HEADER + 'C-01,100,2,CLEAR\nX-01,100,0,WEIRD\n')
    assert [r['code'] for r in parsed['isolated']] == ['CLEAR_NOT_ZERO', 'BAD_KIND']
    assert parsed['meta']['accepted'] == 0


def test_registry_rejects_coil_beyond_link():
    parsed = receive_slack(HEADER + 'S-01,1001,1,COIL\n')
    with pytest.raises(InspectionError, match='SLACK_OUTSIDE_LINK'):
        build_registry(parsed['entries'], 1_000_000)


def test_route_conversion_subtracts_coils_passed_by_instrument():
    registry = build_registry(receive_slack(HEADER + 'S-01,100,10,COIL\nS-02,200,5,COIL\n')['entries'], 1_000_000)
    # half-mm units: instrument 99 m (before coil), 110 m (=100+10, at coil), 215 m (after both)
    assert to_route_half(99000 * 2, registry['coils']) == 99000 * 2
    assert to_route_half(110000 * 2, registry['coils']) == 100000 * 2
    assert to_route_half(215000 * 2, registry['coils']) == 200000 * 2


def test_coverage_boundary_uses_last_registry_position():
    registry = build_registry(receive_slack(HEADER + 'S-01,100,10,COIL\nC-01,250,0,CLEAR\n')['entries'], 1_000_000)
    assert covered(250000, registry) and not covered(250001, registry)


def test_registry_sorts_unsorted_entries_before_accumulating():
    shuffled = receive_slack(HEADER + 'S-02,200,5,COIL\nS-01,100,10,COIL\n')['entries']
    registry = build_registry(list(reversed(shuffled)), 1_000_000)
    assert [coil['id'] for coil in registry['coils']] == ['S-01', 'S-02']
    assert [coil['cumulative_mm'] for coil in registry['coils']] == [10000, 15000]
