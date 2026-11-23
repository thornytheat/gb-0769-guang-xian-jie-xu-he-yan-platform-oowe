from app.pipeline import run

HEADER = 'coil_id,route_m,length_m,kind\n'


def design_with_two_mileage_collisions(material):
    material['traces']['design'] += 'D-1,400,m,0.2\nD-2,400,m,0.2\n'
    return material


def test_same_mileage_joints_without_slack_cannot_borrow_each_others_evidence(clean):
    design_with_two_mileage_collisions(clean)
    rows = run(clean)['design']['rows']
    collided = [row for row in rows if row['joint'] in {'D-1', 'D-2'}]
    assert [row['code'] for row in collided] == ['NO_COUPLED_EVIDENCE', 'NO_COUPLED_EVIDENCE']
    assert all(row['pair'] is None for row in collided)


def test_recorded_coil_lets_each_same_mileage_joint_keep_its_own_coupled_reading(clean):
    design_with_two_mileage_collisions(clean)
    # instrument reads both joints at route 400 m shifted by the 10 m coil (chain 400/401/402 m)
    clean['traces']['a'] += 'SA-4,405,m,0.1\nSA-5,406,m,0.1\n'
    clean['traces']['b'] += 'SB-4,108,m,0.1\nSB-5,109,m,0.1\n'
    clean['traces']['slack'] = HEADER + 'S-01,400,10,COIL\n'
    result = run(clean)['design']
    collided = {row['joint']: row for row in result['rows'] if row['joint'] in {'D-1', 'D-2'}}
    assert {row['code'] for row in collided.values()} == {'PASS'}
    pairs = {row['pair'] for row in collided.values()}
    assert len(pairs) == 2 and all(row['slack_covered'] for row in collided.values())
    # each joint claims its own two-end readings, no shared pair
    assert {row['a_line'] for row in collided.values()} == {5, 6}


def test_design_points_beyond_last_slack_entry_stay_pending(clean):
    clean['traces']['slack'] = HEADER + 'S-01,100,0,CLEAR\n'
    rows = run(clean)['design']['rows']
    assert rows[0]['code'] == 'PASS'
    assert all(row['code'] == 'PENDING_SLACK_RECORDS' for row in rows[1:])
    assert all(not row['evidence_ready'] for row in rows[1:])


def test_clear_entry_confirms_segment_without_coils(clean):
    clean['traces']['slack'] = HEADER + 'C-01,450,0,CLEAR\n'
    result = run(clean)['design']
    assert result['pending_slack'] == 0 and result['passed'] == 3


def test_coil_shifts_misaligned_instrument_reading_back_onto_route(clean):
    # instrument pair lands 10 m past the design point because the coil adds 10 m
    clean['traces']['design'] = 'joint,distance,unit,limit_db\nC-X,100,m,0.2\n'
    clean['traces']['a'] = 'event,distance,unit,loss_db\nAX-1,115,m,0.1\n'
    clean['traces']['b'] = 'event,distance,unit,loss_db\nBX-1,400,m,0.1\n'
    clean['traces']['slack'] = HEADER + 'S-01,100,10,COIL\n'
    row = run(clean)['design']['rows'][0]
    assert row['code'] == 'PASS' and row['coil_ids'] == ['S-01']


def test_pending_joints_keep_confirmed_sections_verifiable(clean):
    clean['traces']['slack'] = HEADER + 'S-01,100,0,CLEAR\n'
    result = run(clean)['design']
    assert result['rows'][0]['evidence_ready'] is True
    assert result['ready_count'] == 1 and result['pending_slack'] == 2


def test_design_balances_hold_with_slack(clean):
    clean['traces']['slack'] = HEADER + 'S-01,100,10,COIL\nC-01,450,0,CLEAR\n'
    result = run(clean)['design']
    assert result['balanced'] and result['measurements_balanced']
    assert result['slack']['coil_count'] == 1 and result['slack']['total_coil_mm'] == 10000
