"""
命理乾坤 · 专业命理分析系统
EdgeOne Pages Cloud Function - Flask 模式
所有 API 路由统一由此文件处理
"""

import sys
import os
import json as _json
import time as _time

# 将 cloud-functions 目录加入 Python 路径，确保 utils 模块可被正确导入
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from utils.bazi_core import (
    full_analysis, get_four_pillars, GAN, ZHI,
    WXG, WXZ, ZHICANG, SHISHEN,
    calc_dayun
)
from utils.ziwei_core import full_ziwei_analysis

# ===== 排盘缓存（P55） =====
_CACHE_DIR = os.environ.get("TMPDIR", os.environ.get("TEMP", os.path.dirname(os.path.abspath(__file__))))
_ZIWEI_CACHE_FILE = os.path.join(_CACHE_DIR, "ml_ziwei_cache.json")
_ZIWEI_CACHE_TTL = 3600  # 1小时
_ZIWEI_CACHE_MAX = 100

def _load_ziwei_cache() -> dict:
    if not os.path.exists(_ZIWEI_CACHE_FILE):
        return {}
    try:
        with open(_ZIWEI_CACHE_FILE, 'r', encoding='utf-8') as f:
            raw = _json.load(f)
        now = _time.time()
        clean = {}
        for k, v in raw.items():
            if isinstance(v, dict) and v.get('ts', 0) > now - _ZIWEI_CACHE_TTL:
                clean[k] = v['data']
        return clean
    except Exception:
        return {}

def _save_ziwei_cache(key: str, data: dict):
    merged = {}
    if os.path.exists(_ZIWEI_CACHE_FILE):
        try:
            with open(_ZIWEI_CACHE_FILE, 'r', encoding='utf-8') as f:
                merged = _json.load(f)
        except Exception:
            pass
    merged[key] = {'data': data, 'ts': _time.time()}
    if len(merged) > _ZIWEI_CACHE_MAX:
        sorted_items = sorted(merged.items(), key=lambda x: x[1].get('ts', 0))
        merged = dict(sorted_items[-_ZIWEI_CACHE_MAX:])
    try:
        with open(_ZIWEI_CACHE_FILE, 'w', encoding='utf-8') as f:
            _json.dump(merged, f, ensure_ascii=False)
    except Exception:
        pass

_ZIWEI_CACHE = _load_ziwei_cache()

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
        # P55: 排盘缓存（同八字+时辰缓存1小时）
        cache_key = f"ziwei:{year}:{month}:{day}:{hour}:{sex}"
        force_refresh = data.get("refresh", False)
        if not force_refresh and cache_key not in _ZIWEI_CACHE:
            # P58: 内存miss时回源文件(多worker/进程写入的文件缓存共享)
            try:
                _ZIWEI_CACHE.update(_load_ziwei_cache())
            except Exception:
                pass
        if not force_refresh and cache_key in _ZIWEI_CACHE:
            result = _ZIWEI_CACHE[cache_key]
            result["_from_cache"] = True
            response = jsonify(result)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["X-Cache"] = "HIT"
            return response

        # P57: single-flight 文件锁（跨worker防重复计算）
        # 外网链路约80s无数据会断连, 断开后客户端重试时:
        # - 若无锁: 多个worker重复计算 → DeepSeek并发限流 → 全部变慢 → 缓存永远写不上
        # - 有锁: 只有第一个请求计算, 后续请求收到202秒回, 前端轮询至缓存HIT
        import hashlib as _hl
        _lock_name = "ml_lock_" + _hl.md5(cache_key.encode()).hexdigest()[:16] + ".lock"
        _lock_file = os.path.join(_CACHE_DIR, _lock_name)
        if not force_refresh and os.path.exists(_lock_file):
            try:
                _lock_age = _time.time() - os.path.getmtime(_lock_file)
            except Exception:
                _lock_age = 999
            if _lock_age < 300:  # 锁5分钟内有效
                resp = jsonify({"status": "computing", "message": "深度分析进行中，请稍后重试", "retry_after": 30})
                resp.status_code = 202
                resp.headers["Access-Control-Allow-Origin"] = "*"
                resp.headers["Retry-After"] = "30"
                return resp
            else:
                try: os.remove(_lock_file)  # 过期锁清理
                except Exception: pass

        # 创建锁后开始计算
        try:
            with open(_lock_file, 'w') as _lf:
                _lf.write(str(_time.time()))
        except Exception:
            pass

        try:
            result = full_ziwei_analysis(year, month, day, hour, sex, force_refresh=force_refresh)
            # P55: 写入缓存
            _ZIWEI_CACHE[cache_key] = result
            _save_ziwei_cache(cache_key, result)
        finally:
            try: os.remove(_lock_file)
            except Exception: pass
    except Exception as e:
        import traceback
        err_msg = "分析异常: %s" % str(e)[:200]
        try:
            sys.stderr.write("[ziwei] %s | %s\n" % (err_msg, traceback.format_exc()[:500]))
        except: pass
        return jsonify({"error": err_msg, "trace": traceback.format_exc()[:1000]}), 500

    response = jsonify(result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["X-Cache"] = "MISS"
    return response


# ========== 交互式问答 API（P56） ==========

@app.route("/ask", methods=["POST", "OPTIONS"])
def ask_api():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    try:
        data = request.get_json(force=True) or {}
        question = data.get("question", "").strip()
        year = data.get("year")
        month = data.get("month")
        day = data.get("day")
        hour = data.get("hour", 12)
        sex = data.get("sex", "男")

        if not question:
            return jsonify({"error": "请输入问题"}), 400
        if not all([year, month, day]):
            return jsonify({"error": "参数不完整"}), 400

        # 先排盘（命中缓存→秒回）
        cache_key = f"ziwei:{year}:{month}:{day}:{hour}:{sex}"
        if cache_key in _ZIWEI_CACHE:
            result = _ZIWEI_CACHE[cache_key]
        else:
            result = full_ziwei_analysis(year, month, day, hour, sex)
            _ZIWEI_CACHE[cache_key] = result
            _save_ziwei_cache(cache_key, result)

        # LLM 生成针对性回答
        from utils.llm_client import llm_call
        # 构建命盘摘要（用于 LLM 上下文）
        places = result.get("十二宫", [])
        sihua = result.get("四化", {})
        palace_summary = []
        for p in places:
            stars = "、".join(p.get("主星", []) + p.get("辅星", []))
            palace_summary.append(f"{p['宫名']}宫({p['天干']}{p['地支']}): {stars}")
        sihua_summary = f"年干{sihua.get('年干','')}: 化禄{sihua.get('化禄','')}/化权{sihua.get('化权','')}/化科{sihua.get('化科','')}/化忌{sihua.get('化忌','')}"

        prompt = f"""你是资深命理师。用户命盘如下：
{chr(10).join(palace_summary[:6])}
四化: {sihua_summary}

用户问题: {question}

请结合命盘数据，给出针对性回答（200字以内）:
1. 问题分析（结合命盘宫位/星曜/四化）
2. 具体建议（该怎么做）
3. 化解方法（如果有不利影响）

语气专业有温度，直接输出回答。"""

        answer = llm_call(prompt, cache_key=f"ask:{hash(question)}", max_tokens=600, retries=1)
        if not answer:
            return jsonify({"error": "AI 分析超时，请稍后重试"}), 500

        response = jsonify({"answer": answer, "question": question})
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as e:
        import traceback
        return jsonify({"error": "分析异常: %s" % str(e)[:200]}), 500


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
# REBUILD_MARKER_v8.35_20260727 — 飞化串联+来因宫叙事+页面拆分+应期预警
def health():
    from utils.ziwei_llm import _last_llm_debug
    # P55: 网络测试（检查EdgeOne云函数能否访问DeepSeek API）
    import urllib.request, ssl, time as _time
    network_test = {"deepseek": "unknown", "google": "unknown"}
    try:
        ctx_ssl = ssl.create_default_context()
        ctx_ssl.check_hostname = False; ctx_ssl.verify_mode = ssl.CERT_NONE
        start = _time.time()
        req = urllib.request.Request("https://api.deepseek.com/v1/models", headers={'User-Agent': 'mq/1.0'})
        with urllib.request.urlopen(req, timeout=5, context=ctx_ssl) as resp:
            network_test["deepseek"] = f"ok ({_time.time()-start:.1f}s)"
    except Exception as e:
        network_test["deepseek"] = f"fail ({str(e)[:50]})"
    try:
        start = _time.time()
        req = urllib.request.Request("https://www.google.com", headers={'User-Agent': 'mq/1.0'})
        with urllib.request.urlopen(req, timeout=5, context=ctx_ssl) as resp:
            network_test["google"] = f"ok ({_time.time()-start:.1f}s)"
    except Exception as e:
        network_test["google"] = f"fail ({str(e)[:50]})"
    return jsonify({"status": "ok", "service": "命理乾坤 API", "version": "v8.65-network-test", "has_split_parser": True, "has_palace_sihua": True, "has_liunian_md_parser": True, "has_miaowang": True, "has_pattern_activation": True, "has_cexiang": True, "has_changsheng": True, "has_feihua_chain": True, "has_laiyin_narrative": True, "has_ziwei_llm": True, "has_cache": True, "cache_v19": True, "llm_debug": _last_llm_debug, "network_test": network_test})
# REBUILD_FORCE: 2026-07-27 18:55 CST — v8.35 飞化串联+来因宫叙事
