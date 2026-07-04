import time
from flask import jsonify, request
from appImp import app
from Implement.mailToolImpl import mailToolImp


def _op_name(op_code):
    op_map = {
        1: 'create',
        2: 'review',
        3: 'pass',
        4: 'auto',
        5: 'delete',
        6: 'edit',
        7: 'recall',
        8: 'reject'
    }
    return op_map.get(op_code, f'unknown({op_code})')


@app.route('/mail/op_mail', methods=['POST'])
def op_mail():
    token = request.headers.get('Access-Token', '').strip()
    username = mailToolImp.parse_username_from_token(token) if token else ''
    if not username:
        return jsonify({'message': 'Unauthorized', 'result': {'isLogin': False}}), 401

    payload = request.get_json(silent=True) or {}
    op_code = payload.get('op_code')
    try:
        op_code = int(op_code)
    except (TypeError, ValueError):
        op_code = None
    request_mail_id = mailToolImp.extract_mail_id_from_payload(payload)

    started_at = time.perf_counter()

    response_body, status_code = mailToolImp.handle_op_mail(username, payload)

    result_mail_id = (((response_body or {}).get('result') or {}).get('mail_id'))
    if result_mail_id is None:
        result_mail_id = (((response_body or {}).get('result') or {}).get('mailId'))
    if result_mail_id is None:
        result_mail_id = request_mail_id

    duration_ms = int((time.perf_counter() - started_at) * 1000)
    app.logger.info(
        f"[mail_op] op_type={_op_name(op_code)} op_code={op_code} user={username} mail_id={result_mail_id} status={status_code} cost_ms={duration_ms}"
    )

    return jsonify(response_body), status_code


@app.route('/mail/select_mail', methods=['GET'])
def select_mail():
    response_body, status_code = mailToolImp.handle_select_mail(request.args)
    return jsonify(response_body), status_code


@app.route('/mail/detail', methods=['GET'])
def mail_detail():
    response_body, status_code = mailToolImp.handle_mail_detail(request.args)
    return jsonify(response_body), status_code


@app.route('/mail/kdip-options', methods=['GET'])
def mail_kdip_options():
    response_body, status_code = mailToolImp.handle_kdip_options(request.args)
    return jsonify(response_body), status_code


@app.route('/mail/templates', methods=['GET'])
def mail_templates_get():
    response_body, status_code = mailToolImp.handle_get_mail_templates()
    return jsonify(response_body), status_code


@app.route('/mail/templates', methods=['POST'])
def mail_templates_save():
    token = request.headers.get('Access-Token', '').strip()
    username = mailToolImp.parse_username_from_token(token) if token else ''
    if not username:
        return jsonify({'message': 'Unauthorized', 'result': {'isLogin': False}}), 401

    payload = request.get_json(silent=True) or {}
    response_body, status_code = mailToolImp.handle_save_mail_templates(username, payload)
    return jsonify(response_body), status_code
