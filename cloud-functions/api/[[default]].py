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
_ZIWEI_CACHE_TTL = 86400  # P63: 1小时→24小时(同一八字分析内容一天内不变,避免反复重算转圈3-4分钟)
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

# P80: 轻量紫微排盘缓存(供过三关verify;八字页用户无主排盘缓存时兜底)
# ⚠️ 与主缓存严格隔离:/ziwei端点只读主缓存,轻量盘绝不被当完整结果返回
_ZIWEI_LIGHT_CACHE_FILE = os.path.join(_CACHE_DIR, "ml_ziwei_light_cache.json")

def _load_light_cache() -> dict:
    if not os.path.exists(_ZIWEI_LIGHT_CACHE_FILE):
        return {}
    try:
        with open(_ZIWEI_LIGHT_CACHE_FILE, 'r', encoding='utf-8') as f:
            raw = _json.load(f)
        now = _time.time()
        return {k: v['data'] for k, v in raw.items()
                if isinstance(v, dict) and v.get('ts', 0) > now - _ZIWEI_CACHE_TTL}
    except Exception:
        return {}

def _save_light_cache(key: str, data: dict):
    merged = {}
    if os.path.exists(_ZIWEI_LIGHT_CACHE_FILE):
        try:
            with open(_ZIWEI_LIGHT_CACHE_FILE, 'r', encoding='utf-8') as f:
                merged = _json.load(f)
        except Exception:
            pass
    merged[key] = {'data': data, 'ts': _time.time()}
    if len(merged) > _ZIWEI_CACHE_MAX:
        merged = dict(sorted(merged.items(), key=lambda x: x[1].get('ts', 0))[-_ZIWEI_CACHE_MAX:])
    try:
        with open(_ZIWEI_LIGHT_CACHE_FILE, 'w', encoding='utf-8') as f:
            _json.dump(merged, f, ensure_ascii=False)
    except Exception:
        pass

_ZIWEI_LIGHT_CACHE = _load_light_cache()

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

    force_refresh = data.get("refresh", False)  # P66: 强制刷新LLM
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else None  # P70: 命主画像
    feedback = data.get("feedback") if isinstance(data.get("feedback"), dict) else None  # P80: 验证反馈
    result = full_analysis(year, month, day, hour, sex, birthplace, minute, force_refresh=force_refresh, profile=profile, feedback=feedback)
    # P80: 顺带产出轻量紫微排盘(毫秒级,无LLM)——过三关verify需要排盘数据,
    # 八字页用户可能从未访问紫微页,主排盘缓存为空会导致verify静默隐藏
    try:
        if isinstance(result, dict) and not result.get("error"):
            from utils.ziwei_core import light_ziwei_chart
            from utils.llm_client import _phash as _ph_lc
            _lc = light_ziwei_chart(year, month, day, hour, sex)
            if _lc:
                _pk_lc = _ph_lc(profile) if profile else ""
                _lk = f"ziwei:{year}:{month}:{day}:{hour}:{sex}" + (f":{_pk_lc}" if _pk_lc else "")
                _ZIWEI_LIGHT_CACHE[_lk] = _lc
                _save_light_cache(_lk, _lc)
    except Exception:
        pass  # 轻量排盘失败绝不阻塞八字主流程
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
        # P55: 排盘缓存（同八字+时辰缓存24小时）
        # P70: 画像影响LLM内容 → 画像hash进缓存key(无画像保持原key兼容旧缓存)
        profile = data.get("profile") if isinstance(data.get("profile"), dict) else None
        feedback = data.get("feedback") if isinstance(data.get("feedback"), dict) else None  # P80: 验证反馈
        from utils.llm_client import _phash as _ph, _fhash as _fh
        _pkey = _ph(profile) if profile else ""
        _fkey = _fh(feedback) if feedback else ""
        cache_key = f"ziwei:{year}:{month}:{day}:{hour}:{sex}" + (f":{_pkey}" if _pkey else "") + (f":{_fkey}" if _fkey else "")
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
        # P64: 锁检查对force_refresh同样生效——否则前端轮询每次都带refresh:true,
        # 每次轮询都触发新的250s计算,12次轮询=12次重复计算,永远转圈
        if os.path.exists(_lock_file):
            try:
                _lock_age = _time.time() - os.path.getmtime(_lock_file)
            except Exception:
                _lock_age = 999
            if _lock_age < 400:  # P64: 锁400s有效(覆盖14个LLM任务~250-350s计算时长)
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
            result = full_ziwei_analysis(year, month, day, hour, sex, force_refresh=force_refresh, profile=profile, feedback=feedback)
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


# ========== 过三关验证 API（P80） ==========

def _get_ziwei_chart(year, month, day, hour, sex, profile, force_refresh=False):
    """取紫微排盘(内存→磁盘回源→None)。verify不主动重算排盘——
    用户必经结果页而来,排盘已在24h缓存内;miss时返回None由前端静默降级,
    避免verify与主分析双重计算放大DeepSeek成本(风险R8对策)"""
    from utils.llm_client import _phash as _ph
    _pkey = _ph(profile) if profile else ""
    cache_key = f"ziwei:{year}:{month}:{day}:{hour}:{sex}" + (f":{_pkey}" if _pkey else "")
    if not force_refresh and cache_key in _ZIWEI_CACHE:
        return _ZIWEI_CACHE[cache_key]
    try:
        _ZIWEI_CACHE.update(_load_ziwei_cache())
    except Exception:
        pass
    if cache_key in _ZIWEI_CACHE:
        return _ZIWEI_CACHE[cache_key]
    # P80: 精确key miss → 前缀扫描(fhash/phash变体的排盘数据完全相同)
    _prefix = f"ziwei:{year}:{month}:{day}:{hour}:{sex}"
    for k, v in _ZIWEI_CACHE.items():
        if k.startswith(_prefix):
            return v
    # P80: 轻量排盘缓存兜底(八字页analyze顺带产出)
    if not force_refresh and cache_key in _ZIWEI_LIGHT_CACHE:
        return _ZIWEI_LIGHT_CACHE[cache_key]
    try:
        _ZIWEI_LIGHT_CACHE.update(_load_light_cache())
    except Exception:
        pass
    if cache_key in _ZIWEI_LIGHT_CACHE:
        return _ZIWEI_LIGHT_CACHE[cache_key]
    for k, v in _ZIWEI_LIGHT_CACHE.items():
        if k.startswith(_prefix):
            return v
    return None


@app.route("/verify", methods=["POST", "OPTIONS"])
def verify_api():
    """过三关断语生成:LLM断7条已发生事件,供用户验证准确度"""
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

    try:
        profile = data.get("profile") if isinstance(data.get("profile"), dict) else None
        force_refresh = data.get("refresh", False)
        chart = _get_ziwei_chart(year, month, day, hour, sex, profile, force_refresh)
        if not chart:
            # 排盘不在缓存(超24h或直接访问) → 前端隐藏验证区,不阻塞主流程
            return jsonify({"ok": True, "verify": None, "reason": "chart_not_cached"})

        from utils import ziwei_llm as _zllm
        from utils.ziwei_llm import _build_verify_context, parse_verify
        # P80: 轻量盘无画像字段,请求带画像时注入(断语更贴合命主实际)
        if profile and isinstance(chart, dict) and not chart.get("命主画像"):
            chart["命主画像"] = profile
        _zllm._FORCE_REFRESH = bool(force_refresh)
        ctx = _build_verify_context(chart, chart.get("格局", []))
        raw = _zllm._llm_generate("verify", ctx)
        _zllm._FORCE_REFRESH = False

        # 解析+多重白名单过滤(年份/干支/宫位/年龄/或字/化曜/红鸾十神/婚恋置业亏损信号)
        birth_year = year
        items = parse_verify(raw, chart, birth_year)
        if not items:
            # P81v6: 首轮存活<5条→追加重写警告重试一次(独立缓存key:r1,不污染首轮缓存)
            ctx["retry_note"] = (
                "\n\n【重写警告】你上一轮的断语大半被判废,原因集中在:"
                "①断语或依据里出现\"或/可能/大概\"等不确定词;②引用的四化/红鸾天喜/十神与该年信号表不符;"
                "③结婚/生子/买房等事件选了信号表上无对应信号的年份。"
                "本轮必须严格逐条对照信号表下断,每条只断一件确定的事,宁缺毋滥。"
            )
            _zllm._FORCE_REFRESH = bool(force_refresh)
            raw2 = _zllm._llm_generate("verify", ctx)
            _zllm._FORCE_REFRESH = False
            items = parse_verify(raw2, chart, birth_year)
        if not items:
            return jsonify({"ok": True, "verify": None, "reason": "generate_failed"})
        for i, it in enumerate(items):
            it["id"] = i + 1
        from utils.ziwei_llm import _chart_key as _ck
        return jsonify({"ok": True, "chart_key": _ck(chart),
                        "verify": {"items": items, "total": len(items)}})
    except Exception as e:
        import traceback
        sys.stderr.write("[verify] %s | %s\n" % (str(e)[:200], traceback.format_exc()[:500]))
        return jsonify({"ok": True, "verify": None, "reason": "error"})


_VERIFY_STATS_FILE = os.path.join(_CACHE_DIR, "ml_verify_stats.json")


def _load_verify_stats() -> dict:
    if os.path.exists(_VERIFY_STATS_FILE):
        try:
            with open(_VERIFY_STATS_FILE, 'r', encoding='utf-8') as f:
                return _json.load(f)
        except Exception:
            pass
    return {"by_type": {}, "_latest": {}, "_ratelimit": {}}


def _save_verify_stats(stats: dict):
    try:
        with open(_VERIFY_STATS_FILE, 'w', encoding='utf-8') as f:
            _json.dump(stats, f, ensure_ascii=False)
    except Exception:
        pass


@app.route("/verify-feedback", methods=["POST", "OPTIONS"])
def verify_feedback_api():
    """验证反馈:计算命中率+匿名聚合统计+限频。
    隐私红线:只存type级聚合计数,不存生辰/画像/correction原文"""
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    data = request.get_json(force=True)
    chart_key = str(data.get("chart_key", ""))[:32]
    feedback = data.get("feedback") if isinstance(data.get("feedback"), dict) else None
    answers = (feedback or {}).get("answers", [])
    if not chart_key or not answers:
        return jsonify({"error": "参数不完整"}), 400

    # 清洗answers:只保留claim/verdict/correction三字段,verdict白名单
    clean_answers = []
    for a in answers[:10]:
        if not isinstance(a, dict):
            continue
        v = a.get("verdict")
        if v not in ("match", "partial", "mismatch"):
            continue
        clean_answers.append({
            "claim": str(a.get("claim", ""))[:80],
            "verdict": v,
            "correction": str(a.get("correction", ""))[:120],
        })
    if not clean_answers:
        return jsonify({"error": "无有效答案"}), 400
    feedback = {"answers": clean_answers}

    stats = _load_verify_stats()
    now = _time.time()

    # 限频:同盘1小时内最多3次变更(防刷反馈放大API成本,风险R6对策)
    rl = [ts for ts in stats["_ratelimit"].get(chart_key, []) if ts > now - 3600]
    if len(rl) >= 3:
        return jsonify({"ok": False, "rate_limited": True,
                        "message": "反馈提交过于频繁,请1小时后再试"}), 429
    rl.append(now)
    stats["_ratelimit"][chart_key] = rl

    # 命中率
    n_match = sum(1 for a in clean_answers if a["verdict"] == "match")
    n_partial = sum(1 for a in clean_answers if a["verdict"] == "partial")
    n_mismatch = sum(1 for a in clean_answers if a["verdict"] == "mismatch")
    total = len(clean_answers)
    rate = round((n_match + n_partial * 0.5) / total * 100)

    # 匿名聚合:同盘重复提交先减旧计数再加新计数(只计最后一次)
    from utils.ziwei_llm import _classify_claim
    old = stats["_latest"].get(chart_key)
    if old:
        for t, v in old.get("verdicts", []):
            bucket = stats["by_type"].get(t)
            if bucket and bucket.get(v, 0) > 0:
                bucket[v] -= 1
    new_verdicts = [(_classify_claim(a["claim"]), a["verdict"]) for a in clean_answers]
    for t, v in new_verdicts:
        bucket = stats["by_type"].setdefault(t, {"match": 0, "partial": 0, "mismatch": 0})
        bucket[v] = bucket.get(v, 0) + 1
    stats["_latest"][chart_key] = {"verdicts": new_verdicts, "ts": now}
    # 防膨胀:最多保留200个盘的记录
    if len(stats["_latest"]) > 200:
        stats["_latest"] = dict(sorted(stats["_latest"].items(),
                                       key=lambda x: x[1].get("ts", 0))[-200:])
    _save_verify_stats(stats)

    from utils.llm_client import _fhash as _fh
    if rate >= 80:
        advice = "命盘与您经历吻合度较高,以下分析可信度较高"
    elif rate >= 50:
        advice = "命盘部分吻合,分析可作参考;不符部分已在后续分析中校准"
    else:
        advice = "多条断语与您经历不符,请核对出生时间(夏令时/农历误填/时辰偏差),或点击强制刷新重新分析"

    resp = jsonify({
        "ok": True,
        "score": {"match": n_match, "partial": n_partial, "mismatch": n_mismatch, "rate": rate},
        "fhash": _fh(feedback),
        "advice": advice,
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


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
    return jsonify({"status": "ok", "service": "命理乾坤 API", "version": "v9.46-verify-v9", "has_light_chart": True, "verify_cache_v42": True,"has_split_parser": True, "has_palace_sihua": True, "has_liunian_md_parser": True, "has_miaowang": True, "has_pattern_activation": True, "has_cexiang": True, "has_changsheng": True, "has_feihua_chain": True, "has_laiyin_narrative": True, "has_ziwei_llm": True, "has_cache": True, "cache_v19": True, "has_verify": True, "has_verify_feedback": True, "llm_cache_v33": True, "llm_debug": _last_llm_debug, "network_test": network_test})
# REBUILD_FORCE: 2026-07-27 18:55 CST — v8.35 飞化串联+来因宫叙事
