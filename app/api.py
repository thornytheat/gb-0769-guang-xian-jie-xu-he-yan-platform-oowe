from flask import Blueprint, current_app, jsonify, request

from .errors import InspectionError
from .input import request_material
from .modules.archive.service import archive, backfill_slack
from .modules.archive.storage import get, recent
from .modules.certificate.service import certify
from .pipeline import run

api = Blueprint('fiber_api', __name__, url_prefix='/api')


def calculate(stage):
    return run(request_material(), stage)[stage]


@api.post('/trace')
def trace():
    return calculate('trace')


@api.post('/calibration')
def calibration():
    return calculate('calibration')


@api.post('/pairs')
def pairs():
    return calculate('pairs')


@api.post('/loss')
def loss():
    return calculate('loss')


@api.post('/design')
def design():
    return calculate('design')


@api.post('/inspections')
def submit():
    report, fresh = archive(current_app.config['DATABASE'], request_material())
    return {'inspection_id':report['inspection_id'], 'created':fresh, 'record':report}, 201 if fresh else 200


@api.get('/inspections')
def list_inspections():
    return {'inspections':recent(current_app.config['DATABASE'])}


@api.get('/inspections/<identifier>')
def inspection(identifier):
    return get(current_app.config['DATABASE'], identifier)


@api.post('/inspections/<identifier>/slack')
def slack_backfill(identifier):
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or 'slack' not in body:
        raise InspectionError('SLACK_TEXT_REQUIRED', status=400)
    result = backfill_slack(current_app.config['DATABASE'], identifier, body['slack'])
    return result, 201 if result['created'] else 200


@api.get('/certificate/<identifier>')
def certificate(identifier):
    return certify(inspection(identifier))


@api.get('/export/<identifier>')
def export(identifier):
    response = jsonify(certificate(identifier))
    response.headers['Content-Disposition'] = f'attachment; filename="splice-{identifier[:12]}.json"'
    return response
