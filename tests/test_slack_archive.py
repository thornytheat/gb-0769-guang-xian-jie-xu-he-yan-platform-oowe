from app.modules.archive.service import backfill_slack

HEADER = 'coil_id,route_m,length_m,kind\n'


def publish(client, payload):
    return client.post('/api/inspections', json=payload)


def test_backfill_creates_new_archive_and_keeps_original_untouched(client, clean):
    first = publish(client, clean).json
    slack = HEADER + 'C-01,450,0,CLEAR\n'
    backfilled = client.post(f"/api/inspections/{first['inspection_id']}/slack", json={'slack': slack})
    assert backfilled.status_code == 201
    body = backfilled.json
    assert body['created'] is True and body['source_inspection_id'] == first['inspection_id']
    assert body['inspection_id'] != first['inspection_id']
    # original snapshot remains verifiable on its original evidence
    original = client.get('/api/inspections/' + first['inspection_id']).json
    assert 'slack' not in original['material']['traces'] and 'slack' not in original['computed']
    assert len(client.get('/api/inspections').json['inspections']) == 2


def test_repeating_same_backfill_is_idempotent(client, clean):
    first = publish(client, clean).json['inspection_id']
    slack = HEADER + 'C-01,450,0,CLEAR\n'
    once = client.post(f'/api/inspections/{first}/slack', json={'slack': slack})
    twice = client.post(f'/api/inspections/{first}/slack', json={'slack': slack})
    assert (once.status_code, twice.status_code, twice.json['created']) == (201, 200, False)
    assert once.json['inspection_id'] == twice.json['inspection_id']
    assert len(client.get('/api/inspections').json['inspections']) == 2


def test_backfilled_archive_recomputes_and_certificate_uses_new_evidence(client, clean):
    first_id = publish(client, clean).json['inspection_id']
    # only confirm the first section; the remaining joints stay pending
    slack = HEADER + 'C-01,100,0,CLEAR\n'
    new_id = client.post(f'/api/inspections/{first_id}/slack', json={'slack': slack}).json['inspection_id']
    certificate = client.get('/api/certificate/' + new_id).json
    assert certificate['blockers'] == ['PENDING_SLACK_RECORDS'] and certificate['approved'] is False
    old_certificate = client.get('/api/certificate/' + first_id).json
    assert old_certificate['approved'] is True and old_certificate['blockers'] == []


def test_second_backfill_chains_off_first_archive(client, clean):
    first_id = publish(client, clean).json['inspection_id']
    step1 = client.post(f'/api/inspections/{first_id}/slack',
                        json={'slack': HEADER + 'C-01,100,0,CLEAR\n'}).json
    step2 = client.post(f"/api/inspections/{step1['inspection_id']}/slack",
                        json={'slack': HEADER + 'C-02,300,0,CLEAR\n'})
    assert step2.status_code == 201
    record = client.get('/api/inspections/' + step2.json['inspection_id']).json
    assert [line['id'] for line in record['computed']['slack']['entries']] == ['C-01', 'C-02']


def test_backfill_merges_into_registry_when_archive_already_has_slack(client, clean):
    clean['traces']['slack'] = HEADER + 'C-01,100,0,CLEAR\n'
    identifier = publish(client, clean).json['inspection_id']
    response = client.post(f'/api/inspections/{identifier}/slack',
                           json={'slack': HEADER + 'C-02,300,0,CLEAR\n'})
    assert response.status_code == 201
    record = client.get('/api/inspections/' + response.json['inspection_id']).json
    assert [row['id'] for row in record['computed']['slack']['entries']] == ['C-01', 'C-02']
    # the earlier archived snapshot is not rewritten
    original = client.get('/api/inspections/' + identifier).json
    assert [row['id'] for row in original['computed']['slack']['entries']] == ['C-01']


def test_backfill_requires_slack_text(client, clean):
    identifier = publish(client, clean).json['inspection_id']
    response = client.post(f'/api/inspections/{identifier}/slack', json={})
    assert (response.status_code, response.json['code']) == (400, 'SLACK_TEXT_REQUIRED')


def test_invalid_slack_backfill_leaves_store_unchanged(client, clean):
    identifier = publish(client, clean).json['inspection_id']
    response = client.post(f'/api/inspections/{identifier}/slack',
                           json={'slack': HEADER + 'S-01,9999,10,COIL\n'})
    assert (response.status_code, response.json['code']) == (422, 'SLACK_OUTSIDE_LINK')
    assert len(client.get('/api/inspections').json['inspections']) == 1


def test_quarantined_slack_rows_block_certificate(client, clean):
    clean['traces']['slack'] = HEADER + 'C-01,450,0,CLEAR\nX-9,100,0,WEIRD\n'
    identifier = publish(client, clean).json['inspection_id']
    blockers = client.get('/api/certificate/' + identifier).json['blockers']
    assert 'UNVERIFIED_SLACK_ROWS' in blockers


def test_identity_changes_when_slack_registry_differs(tmp_path, clean):
    from app.modules.archive.storage import get
    database = tmp_path / 'db'
    first = backfill_slack(database, _seed(database, clean), HEADER + 'C-01,100,0,CLEAR\n')
    second = backfill_slack(database, _seed(database, clean), HEADER + 'C-01,300,0,CLEAR\n')
    assert first['inspection_id'] != second['inspection_id']
    assert get(database, first['inspection_id'])['computed']['design']['pending_slack'] == 2


def _seed(database, material):
    from app.modules.archive.service import archive
    return archive(database, material)[0]['inspection_id']
