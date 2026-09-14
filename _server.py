"""临时本地预览服务器 — 命理乾坤"""
import sys, os
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'cloud-functions', 'api'))

from flask import Flask, request, jsonify, send_from_directory, send_file
app = Flask(__name__)

from utils.bazi_core import full_analysis

# P82: 挂载紫微系端点(/api/ziwei /api/verify /api/family /api/liunian /api/ask...)
# ——此前本地_preview只能跑八字页,ziwei.html的/api/*请求全404;
# 用DispatcherMiddleware把[[default]].py的app挂到/api/下(与生产Nginx /api/→/ 行为一致)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "mq_api", os.path.join(BASE, 'cloud-functions', 'api', '[[default]].py'))
_mq = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mq)
from werkzeug.middleware.dispatcher import DispatcherMiddleware
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {'/api': _mq.app})

# ========== API 鉴权（与 EdgeOne 云函数一致） ==========
_API_KEY = os.environ.get("ML_API_KEY", "mingli-qiankun-v7")  # 本地开发用固定密钥
_AUTH_WHITELIST = {"/health", "/", "/favicon.ico"}

@app.before_request
def require_api_key():
    if request.method == "OPTIONS":
        return None
    if request.path in _AUTH_WHITELIST or request.path.endswith(('.html','.css','.js','.png','.svg','.ico','.json')):
        return None
    client_key = request.headers.get("X-API-Key", "")
    if not client_key or client_key != _API_KEY:
        return jsonify({"error": "未授权访问", "code": 401}), 401

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
        resp.headers['Access-Control-Allow-Origin'] = '*'; resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
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
