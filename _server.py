"""临时本地预览服务器 — 命理乾坤"""
import sys, os
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'cloud-functions', 'api'))

from flask import Flask, request, jsonify, send_from_directory, send_file
app = Flask(__name__)

from utils.bazi_core import full_analysis

@app.route('/')
def root():
    return send_file(os.path.join(BASE, 'index.html'))

@app.route('/<path:path>')
def static_files(path):
    target = os.path.join(BASE, path)
    if os.path.exists(target) and not os.path.isdir(target):
        return send_file(target)
    return 'Not found', 404

@app.route('/api/analyze', methods=['POST','OPTIONS'])
def analyze():
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        resp.headers['Access-Control-Allow-Origin'] = '*'; resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'; return resp
    data = request.get_json(force=True)
    try:
        year, month, day = int(data['year']), int(data['month']), int(data['day'])
        hour = int(data.get('hour',12)); minute = int(data.get('minute',0) or 0)
        sex = data.get('sex','男'); birthplace = data.get('birthplace','')
    except (KeyError, ValueError):
        return jsonify({'error':'请输入完整的出生信息'}), 400
    if not (1924 <= year <= 2100): return jsonify({'error':'年份请输入1924~2100之间'}), 400
    if not (1 <= month <= 12): return jsonify({'error':'月份请输入1~12之间'}), 400
    if not (1 <= day <= 31): return jsonify({'error':'日期请输入1~31之间'}), 400
    result = full_analysis(year, month, day, hour, sex, birthplace, minute)
    resp = jsonify(result); resp.headers['Access-Control-Allow-Origin'] = '*'; return resp

@app.route('/health')
def health(): return jsonify({'status':'ok'})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8765, debug=False)
