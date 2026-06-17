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

# ========== 八字命理 API ==========

@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    data = request.get_json(force=True)
    try:
        year  = int(data["year"])
        month = int(data["month"])
        day   = int(data["day"])
        hour  = int(data.get("hour", 12))
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

    result = full_analysis(year, month, day, hour, sex, birthplace)
    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ========== 紫微斗数 API ==========

@app.route("/ziwei", methods=["POST", "OPTIONS"])
def ziwei_api():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
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

    result = full_ziwei_analysis(year, month, day, hour, sex)
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
def health():
    return jsonify({"status": "ok", "service": "命理乾坤 API"})
