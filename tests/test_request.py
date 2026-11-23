def test_inputs_require_three_sources(client):
    response = client.post('/api/trace', json={'traces': {'a': ''}})
    assert (response.status_code, response.json['code']) == (400, 'THREE_TRACES_REQUIRED')


def test_ingest_does_not_need_calibration(client):
    assert client.post('/api/trace', json={'sample': 'dirty', 'settings': None}).json['counts']['a']['isolated'] == 5
    assert client.post('/api/calibration', json={'sample': 'dirty', 'settings': None}).status_code == 422


def test_slack_is_optional_fourth_source(client):
    base = {'traces': {'a': 'event,distance,unit,loss_db\n', 'b': 'event,distance,unit,loss_db\n',
                       'design': 'joint,distance,unit,limit_db\n'},
            'settings': {'length_m': 100, 'zero_a_m': 0, 'zero_b_m': 0,
                         'pair_tol_m': 1, 'design_tol_m': 1, 'reference_limit_db': '0.2'}}
    legacy = client.post('/api/design', json=base)
    assert legacy.status_code == 200 and legacy.json['slack'] == {'present': False}
    with_slack = client.post('/api/design', json={**base, 'traces': {**base['traces'],
                                                                      'slack': 'coil_id,route_m,length_m,kind\nC-1,50,0,CLEAR\n'}})
    assert with_slack.json['slack']['present'] is True and with_slack.json['pending_slack'] == 0


def test_trace_stage_does_not_parse_slack(client):
    response = client.post('/api/trace', json={'traces': {'a': 'event,distance,unit,loss_db\n',
                                                          'b': 'event,distance,unit,loss_db\n',
                                                          'design': 'joint,distance,unit,limit_db\n',
                                                          'slack': 'coil_id,route_m,length_m,kind\nS-1,10,5,COIL\n'},
                                               'settings': None})
    assert response.status_code == 200 and 'slack' not in response.json


def test_bad_slack_header_reports_slack_source(client):
    settings = {'length_m': 100, 'zero_a_m': 0, 'zero_b_m': 0, 'pair_tol_m': 1, 'design_tol_m': 1,
                'reference_limit_db': '0.2'}
    response = client.post('/api/design', json={'traces': {'a': 'event,distance,unit,loss_db\n',
                                                            'b': 'event,distance,unit,loss_db\n',
                                                            'design': 'joint,distance,unit,limit_db\n',
                                                            'slack': 'x,y\n'},
                                                'settings': settings})
    assert (response.status_code, response.json['code'], response.json['source']) == (422, 'BAD_HEADER', 'slack')
