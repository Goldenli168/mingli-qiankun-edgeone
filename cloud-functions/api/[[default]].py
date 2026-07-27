"""
命理乾坤 · 专业命理分析系统
EdgeOne Pages Cloud Function - Flask 模式
所有 API 路由统一由此文件处理
"""

import sys
import os

# 将 cloud-functions 目录加入 Python 路径，确保 utils 模块可被正确导入
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from utils.bazi_core import (
    full_analysis, get_four_pillars, GAN, ZHI,
    WXG, WXZ, ZHICANG, SHISHEN,
    calc_dayun
)
from utils.ziwei_core import full_ziwei_analysis

app = Flask(__name__)

# ========== API 鉴权配置 ==========
#
# 部署时在 EdgeOne 环境变量中设置 ML_API_KEY
# 本地开发可通过环境变量或默认值自动生成
#
# 安全策略:
#   - /health 无需鉴权
#   - OPTIONS (CORS 预检) 无需鉴权
#   - 其他所有 API 需要 X-API-Key 头

def _get_api_key():
    """获取 API Key: 环境变量 > 默认密钥(与前端一致)"""
    return os.environ.get("ML_API_KEY", "mingli-qiankun-v7")

API_KEY = _get_api_key()

# 白名单路由: 不需要鉴权
_AUTH_WHITELIST = {"/health"}

@app.before_request
def require_api_key():
    """API 鉴权中间件 — 除白名单路由外均需验证 X-API-Key"""
    if request.method == "OPTIONS":
        return None  # CORS 预检放行
    if request.path in _AUTH_WHITELIST:
        return None

    client_key = request.headers.get("X-API-Key", "")
    if not client_key or client_key != API_KEY:
        return jsonify({"error": "未授权访问", "code": 401}), 401

# ========== 八字命理 API ==========

@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    data = request.get_json(force=True)
    try:
        year  = int(data["year"])
        month = int(data["month"])
        day   = int(data["day"])
        hour  = int(data.get("hour", 12))
        minute = int(data.get("minute", 0) or 0)
        sex   = data.get("sex", "男")
        birthplace = data.get("birthplace", "")
    except (KeyError, ValueError):
        return jsonify({"error": "请输入完整的出生信息"}), 400

    if not (1924 <= year <= 2100):
        return jsonify({"error": "年份请输入1924~2100之间"}), 400
    if not (1 <= month <= 12):
        return jsonify({"error": "月份请输入1~12之间"}), 400
    if not (1 <= day <= 31):
        return jsonify({"error": "日期请输入1~31之间"}), 400

    result = full_analysis(year, month, day, hour, sex, birthplace, minute)
    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ========== 紫微斗数 API ==========

@app.route("/ziwei", methods=["POST", "OPTIONS"])
def ziwei_api():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    data = request.get_json(force=True)
    try:
        year  = int(data["year"])
        month = int(data["month"])
        day   = int(data["day"])
        hour  = int(data.get("hour", 12))
        sex   = data.get("sex", "男")
    except (KeyError, ValueError):
        return jsonify({"error": "请输入完整的出生信息"}), 400

    if not (1900 <= year <= 2100):
        return jsonify({"error": "年份请输入1900~2100之间"}), 400
    if not (1 <= month <= 12):
        return jsonify({"error": "月份请输入1~12之间"}), 400
    if not (1 <= day <= 31):
        return jsonify({"error": "日期请输入1~31之间"}), 400

    try:
        result = full_ziwei_analysis(year, month, day, hour, sex)
    except Exception as e:
        import traceback
        err_msg = "分析异常: %s" % str(e)[:200]
        try:
            sys.stderr.write("[ziwei] %s | %s\n" % (err_msg, traceback.format_exc()[:500]))
        except: pass
        return jsonify({"error": err_msg, "trace": traceback.format_exc()[:1000]}), 500

    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ========== 流年详情 API ==========

@app.route("/liunian", methods=["GET", "OPTIONS"])
def liunian_api():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    year  = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    day   = request.args.get("day", type=int)
    hour  = request.args.get("hour", type=int, default=12)
    sex   = request.args.get("sex", "男")
    step  = request.args.get("step", type=int, default=1)

    if not all([year, month, day]):
        return jsonify({"error": "参数不完整"}), 400

    fp = get_four_pillars(year, month, day, hour)
    day_gan = fp["day"][0]
    qi_yun, dayun_list = calc_dayun(sex, fp["year"][0], tuple(fp["month"]), year, month, day)

    if step < 1 or step > len(dayun_list):
        return jsonify({"error": "无效的大运步数"}), 400

    dy = dayun_list[step - 1]
    start_y = year + dy["age_start"]
    end_y   = year + dy["age_end"] + 1

    items = []
    for y in range(start_y, end_y):
        gi = (y - 4) % 10
        zi = (y - 4) % 12
        g, z = GAN[gi], ZHI[zi]
        ss = SHISHEN[day_gan][g]
        wx = WXG[g] + "/" + WXZ[z]
        items.append({"年份": y, "干支": f"{g}{z}", "十神": ss, "五行": wx})

    response = jsonify({
        "大运": f"{dy['gan']}{dy['zhi']}",
        "年龄": f"{dy['age_start']}-{dy['age_end']}岁",
        "流年": items
    })
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ========== 健康检查 ==========

@app.route("/health", methods=["GET"])
# REBUILD_MARKER_v8.33_20260727 — 庙旺+格局激活+盲派测象+长生十二宫
def health():
    from utils.ziwei_core import _last_llm_debug
    return jsonify({"status": "ok", "service": "命理乾坤 API", "version": "v8.33-ima-optimizations", "has_split_parser": True, "has_palace_sihua": True, "has_liunian_md_parser": True, "has_miaowang": True, "has_pattern_activation": True, "has_cexiang": True, "has_changsheng": True, "cache_v18": True, "llm_debug": _last_llm_debug})
# REBUILD_FORCE: 2026-07-27 10:30 CST — v8.33 IMA知识库4项优化
