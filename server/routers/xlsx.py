# 和excel工具相关的route放这个里

# builtin

# 3rd ext
from flask import request, jsonify

# int
from appImp import app
from Implement.xlsxImpl import XlsxCollection


# region init
XlsxCollection.initXlsxCollection(9999)
# endregion


# region route
@app.route('/xlsx/brief_info', methods=['GET'])
def getXlsxBriefInfo():
    app.logger.info("getXlsxBriefInfo")
    svn_version = int(request.args.get("svn_version"))
    brief_info = XlsxCollection.getXlsxCollectionInfo(svn_version)
    return jsonify(brief_info)


@app.route('/xlsx/search_key', methods=['GET'])
def getXlsxSearchKey():
    app.logger.info("getXlsxSearchKey")
    svn_version = int(request.args.get("svn_version"))
    search_key = request.args.get('search_key')
    app.logger.info(f"getXlsxSearchKey {search_key}")
    search_result = XlsxCollection.requestSearchKey(svn_version, search_key)
    return jsonify(search_result)


@app.route('/xlsx/search_keys', methods=['GET'])
def getXlsxSearchKeys():
    app.logger.info("getXlsxSearchKeys")
    svn_version = int(request.args.get("svn_version"))
    search_keys = request.args.getlist('search_keys[]')
    app.logger.info(f"getXlsxSearchKeys {search_keys}")
    search_result = XlsxCollection.requestSearchKeys(svn_version, search_keys)
    return jsonify(search_result)


@app.route('/xlsx/row_datas', methods=['GET'])
def getXlsxRowDatas():
    app.logger.info("getXlsxRowDatas")
    svn_version = int(request.args.get("svn_version"))
    sheet_name = request.args.get("sheet_name")
    row_idxs = [int(x) for x in request.args.getlist('row_idxs[]')]
    with_header = request.args.get('with_header').lower() in ['true', '1']
    ret = {
        'row_datas': XlsxCollection.requestRowData(svn_version, sheet_name, row_idxs)
    }
    if with_header:
        ret['header'] = XlsxCollection.requestTableHeader(svn_version, sheet_name)
    return jsonify(ret)


@app.route('/xlsx/header', methods=['GET'])
def getXlsxHeader():
    app.logger.info("getXlsxHeader")
    svn_version = int(request.args.get("svn_version"))
    sheet_name = request.args.get("sheet_name")
    headers = XlsxCollection.requestTableHeader(svn_version, sheet_name)
    return jsonify(headers)
