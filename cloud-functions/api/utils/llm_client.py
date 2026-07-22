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


def _save_entry(key: str, content: str):
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


def llm_call(prompt: str, cache_key: str = "", max_tokens: int = 800, retries: int = 2) -> str | None:
    """通用 LLM 调用: 发 prompt 到 DeepSeek, 带缓存, 失败重试, 重试用尽返回 None"""
    import json, urllib.request, ssl

    # 缓存
    ck = cache_key or f"generic:{hash(prompt)}"
    if ck in _LLM_CACHE:
        return _LLM_CACHE[ck]

    if not DEEPSEEK_API_KEY:
        return None

    ctx_ssl = ssl.create_default_context()
    ctx_ssl.check_hostname = False; ctx_ssl.verify_mode = ssl.CERT_NONE
    data = json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.7, "stream": False}).encode('utf-8')

    # 重试 2 次 (共 3 次机会)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(DEEPSEEK_URL, data=data,
                headers={'Content-Type': 'application/json',
                         'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                         'User-Agent': 'mq/1.0'})
            with urllib.request.urlopen(req, timeout=8, context=ctx_ssl) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                content = result['choices'][0]['message']['content'].strip()
                if len(content) > 10:
                    _LLM_CACHE[ck] = content
                    _save_entry(ck, content)
                    return content
                return None
        except Exception as e:
            if attempt < retries:
                _time.sleep(0.3 * (attempt + 1))  # 指数退避: 0.3s, 0.6s
                continue
            # 最后一次失败,记录但不抛
            return None
    return None
