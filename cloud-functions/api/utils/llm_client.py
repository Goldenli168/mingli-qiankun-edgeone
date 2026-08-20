"""
命理乾坤 · LLM 客户端（DeepSeek API 共享模块）
供 bazi_core 和 ziwei_core 共用
版本: v7.7
"""
import os
import json as _json
import time as _time

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


# ===== P70: 命主画像助手(职业/婚姻/子女/收入/关注点 → prompt文本+稳定hash) =====
def _stable_hash(s) -> str:
    """跨进程稳定的短hash(替代内置hash——多worker下内置hash因PYTHONHASHSEED
    随机化各进程不同,导致LLM缓存key不一致,4worker间缓存命中率仅25%)"""
    import hashlib
    return hashlib.md5(str(s).encode("utf-8")).hexdigest()[:12]


def _phash(profile: dict | None) -> str:
    """画像→稳定短hash(缓存key用,md5跨进程稳定,不用内置hash)"""
    if not profile:
        return "noprof"
    import hashlib
    s = _json.dumps(profile, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:8]


def _profile_text(profile: dict | None) -> str:
    """画像→prompt注入文本,空画像返回空串(不影响原有prompt)"""
    if not profile:
        return ""
    parts = []
    if profile.get("occupation"):
        parts.append(f"职业:{profile['occupation']}")
    if profile.get("marital"):
        parts.append(f"婚姻状况:{profile['marital']}")
    if profile.get("children"):
        parts.append(f"子女:{profile['children']}")
    if profile.get("income"):
        parts.append(f"年收入:{profile['income']}")
    if profile.get("focus"):
        foc = profile["focus"]
        if isinstance(foc, list) and foc:
            parts.append(f"重点关注:{'、'.join(foc)}")
    if not parts:
        return ""
    return (
        "\n【命主真实画像】已知事实:" + "；".join(parts) + "。\n"
        "要求:①上述为命主亲口提供的真实信息,直接引用(如'您从事IT管理'),严禁再猜测或与其矛盾;"
        "②婚姻维度按其真实状态写(已婚谈经营与危机预警,未婚/恋爱谈婚恋时间窗口,离异/丧偶谈再婚机遇与重建);"
        "③财富维度对照其收入层级:判断当前收入是否已达命局上限,给出跳档路径或守成策略;"
        "④事业/大运建议结合其所在行业展开;⑤其重点关注领域要分析得更详实。\n"
    )

# ===== 磁盘缓存 =====
_CACHE_DIR = os.environ.get("TMPDIR", os.environ.get("TEMP", os.path.dirname(os.path.abspath(__file__))))
_CACHE_FILE = os.path.join(_CACHE_DIR, "ml_llm_cache.json")
_CACHE_MAX = 500
_CACHE_TTL = 7 * 86400


def _load_cache() -> dict:
    if not os.path.exists(_CACHE_FILE):
        return {}
    try:
        with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
            raw = _json.load(f)
        now = _time.time()
        clean = {}
        for k, v in raw.items():
            if isinstance(v, dict) and v.get('ts', 0) > now - _CACHE_TTL:
                clean[k] = v['content']
            elif isinstance(v, str):
                clean[k] = v
        return clean
    except Exception:
        return {}


import threading as _threading
_SAVE_LOCK = _threading.Lock()  # P68: 并行LLM任务时防止读-改-写丢条目

def _save_entry(key: str, content: str):
    with _SAVE_LOCK:
        merged = {}
        if os.path.exists(_CACHE_FILE):
            try:
                with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                    merged = _json.load(f)
            except Exception:
                pass
        now = _time.time()
        merged[key] = {'content': content, 'ts': now}
        if len(merged) > _CACHE_MAX:
            sorted_items = sorted(merged.items(), key=lambda x: (
                x[1].get('ts', 0) if isinstance(x[1], dict) else 0
            ))
            merged = dict(sorted_items[-_CACHE_MAX:])
        try:
            with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
                _json.dump(merged, f, ensure_ascii=False)
        except Exception:
            pass


_LLM_CACHE = _load_cache()


def llm_call(prompt: str, cache_key: str = "", max_tokens: int = 800, retries: int = 2, skip_cache: bool = False) -> str | None:
    """通用 LLM 调用: 发 prompt 到 DeepSeek, 带缓存, 失败重试, 重试用尽返回 None"""
    import json, urllib.request, ssl

    # 缓存
    ck = cache_key or f"generic:{hash(prompt)}"
    if not skip_cache and ck in _LLM_CACHE:  # P60: skip_cache=强制刷新LLM
        return _LLM_CACHE[ck]

    if not DEEPSEEK_API_KEY:
        return None

    ctx_ssl = ssl.create_default_context()
    ctx_ssl.check_hostname = False; ctx_ssl.verify_mode = ssl.CERT_NONE
    data = json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.7, "stream": False}).encode('utf-8')

    # P55: 增加调用间隔（避免DeepSeek限流）
    _time.sleep(2)

    # 重试 2 次 (共 3 次机会)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(DEEPSEEK_URL, data=data,
                headers={'Content-Type': 'application/json',
                         'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                         'User-Agent': 'mq/1.0'})
            with urllib.request.urlopen(req, timeout=60, context=ctx_ssl) as resp:  # P56: 25s→60s（DeepSeek响应慢，自建服务器超时时间无限制）
                result = json.loads(resp.read().decode('utf-8'))
                content = result['choices'][0]['message']['content'].strip()
                if len(content) > 10:
                    _LLM_CACHE[ck] = content
                    _save_entry(ck, content)
                    return content
                return None
        except Exception as e:
            if attempt < retries:
                _time.sleep(2 * (attempt + 1))  # P55: 0.3s→2s（避免限流）
                continue
            # 最后一次失败,记录但不抛
            return None
    return None
