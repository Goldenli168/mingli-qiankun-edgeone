# -*- coding: utf-8 -*-
"""P90: 流月/流日 六维度命理分析模块（事业/财运/健康/夫妻/父母/儿女）
数据层: iztro_py horoscope(流月/流日干支+宫名映射+四化) + 本命盘宫星
分析层: llm_call(prompt, cache_key) 复用现有 DeepSeek 缓存
缓存命名空间: liuri-v1:{chart}:{YYYY-MM-DD} / liuyue-v1:{chart}:{YYYY-MM}
"""
import os
import json
import datetime

from .llm_client import llm_call
from .bazi_data import GAN, ZHI


def _gan_zhi(stem_en, branch_en) -> str:
    """iztro 英文干支名 → 中文干支"""
    from .ziwei_core import _parse_stem, _parse_branch
    return GAN[_parse_stem(str(stem_en))] + ZHI[_parse_branch(str(branch_en))]

_LIURI_VER = "v1"

# 六维度: (中文名, iztro宫名en, 本命宫位中文)
_DIMS = [
    ("事业", "careerPalace",   "官禄"),
    ("财运", "wealthPalace",   "财帛"),
    ("健康", "healthPalace",   "疾厄"),
    ("夫妻", "spousePalace",   "夫妻"),
    ("父母", "parentsPalace",  "父母"),
    ("儿女", "childrenPalace", "子女"),
]

# 结果缓存(与 llm 缓存分离, 存解析后的结构化结果)
_CACHE_DIR = os.environ.get("TMPDIR", os.environ.get("TEMP", os.path.dirname(os.path.abspath(__file__))))
_LIURI_CACHE_FILE = os.path.join(_CACHE_DIR, "ml_liuri_cache.json")
_LIURI_CACHE_MAX = 200
_LIURI_TTL_DAILY = 7 * 86400
_LIURI_TTL_MONTHLY = 40 * 86400


def _load_liuri_cache() -> dict:
    if not os.path.exists(_LIURI_CACHE_FILE):
        return {}
    try:
        with open(_LIURI_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_liuri_cache(key: str, data: dict):
    try:
        raw = _load_liuri_cache()
        raw[key] = {"ts": datetime.datetime.now().timestamp(), "data": data}
        # LRU: 超上限删最旧
        if len(raw) > _LIURI_CACHE_MAX:
            for k in sorted(raw, key=lambda k: raw[k].get("ts", 0))[: len(raw) - _LIURI_CACHE_MAX]:
                raw.pop(k, None)
        with open(_LIURI_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False)
    except Exception:
        pass


def _get_liuri_cache(key: str, ttl: int):
    raw = _load_liuri_cache()
    v = raw.get(key)
    if isinstance(v, dict) and v.get("ts", 0) > datetime.datetime.now().timestamp() - ttl:
        return v["data"]
    return None


# ============ 排盘数据层 ============

def _build_chart(solar_year, solar_month, solar_day, hour, sex):
    """建本命盘(iztro), 复用 ziwei_core 的时辰转换与翻译函数"""
    from iztro_py import astro
    from .ziwei_core import _hour_to_time_index
    time_index = _hour_to_time_index(hour)
    gender = "男" if sex == "男" else "女"
    solar_date = f"{solar_year}-{solar_month:02d}-{solar_day:02d}"
    return astro.by_solar(solar_date, time_index, gender, True, "zh-CN")


def _palace_stars_cn(palace):
    """取一个本命宫的主星/辅星中文名列表"""
    from .ziwei_core import _star_en_to_cn
    major, minor = [], []
    for s in (palace.major_stars or []):
        cn = _star_en_to_cn(str(s.name))
        if cn:
            major.append(cn)
    for s in (palace.minor_stars or []):
        cn = _star_en_to_cn(str(s.name))
        if cn:
            minor.append(cn)
    return major, minor


def _scope_ctx(h_item, chart):
    """解析一个 horoscope 项(流月/流日): 干支 + 四化 + 六维度落宫"""
    from .ziwei_core import _star_en_to_cn
    gz = _gan_zhi(h_item.heavenly_stem, h_item.earthly_branch)
    gan, zhi = gz[0], gz[1]
    mutagen = [_star_en_to_cn(str(m)) for m in (h_item.mutagen or [])]
    sihua = {"禄": mutagen[0] if len(mutagen) > 0 else "",
             "权": mutagen[1] if len(mutagen) > 1 else "",
             "科": mutagen[2] if len(mutagen) > 2 else "",
             "忌": mutagen[3] if len(mutagen) > 3 else ""}
    palaces = list(chart.palaces)
    pnames = list(h_item.palace_names or [])
    dims = {}
    for cn_name, en_name, natal_cn in _DIMS:
        dim = {"host_branch": "", "host_ganzhi": "", "natal_palace": natal_cn,
               "major": [], "minor": [], "sihua_hits": []}
        try:
            idx = pnames.index(en_name)
        except ValueError:
            dims[cn_name] = dim
            continue
        if 0 <= idx < len(palaces):
            p = palaces[idx]
            dim["host_ganzhi"] = _gan_zhi(p.heavenly_stem, p.earthly_branch)
            dim["host_branch"] = dim["host_ganzhi"][1]
            major, minor = _palace_stars_cn(p)
            dim["major"] = major
            dim["minor"] = minor[:6]
            # 四化星落入该宫 = 引动
            dim["sihua_hits"] = [f"{star}化{k}" for k, star in sihua.items()
                                 if star and star in major + minor]
        dims[cn_name] = dim
    return {"ganzhi": gan + zhi, "gan": gan, "zhi": zhi, "sihua": sihua, "dims": dims}


def _decadal_yearly_ctx(chart, target: datetime.date, birth_year):
    """大限+流年上下文(让流月流日分析有高层框架锚定)"""
    h = chart.horoscope(target.isoformat())
    return {
        "decadal_ganzhi": _gan_zhi(h.decadal.heavenly_stem, h.decadal.earthly_branch),
        "yearly_ganzhi": _gan_zhi(h.yearly.heavenly_stem, h.yearly.earthly_branch),
        "nominal_age": getattr(h, "nominal_age", target.year - birth_year + 1),
    }, h


def _day_ganzhi_table(year: int, month: int) -> str:
    """当月每日干支表(八字法), 供月度分析挑重点日"""
    from .bazi_core import get_four_pillars
    lines = []
    d0 = datetime.date(year, month, 1)
    while d0.month == month:
        try:
            fp = get_four_pillars(d0.year, d0.month, d0.day, 12)
            gz = "".join(fp["day"])
        except Exception:
            gz = "?"
        lines.append(f"{d0.day}日{gz}")
        d0 += datetime.timedelta(days=1)
    return "、".join(lines)


# ============ LLM 分析层 ============

_STYLE_RULES = """要求:
1. 每条紧扣给出的宫位星曜与四化引动, 禁止编造未列出的星曜
2. 语气: 专业直白, 验证式+可操作建议, 不模板化, 不堆术语
3. 信号只讲"引动/应象", 不夸大吉凶; 健康维度只提醒作息与检查, 不下断语
4. 严格按格式输出, 不要输出任何额外说明"""


def _dims_text(dims: dict) -> str:
    lines = []
    for cn, _, natal_cn in _DIMS:
        d = dims.get(cn, {})
        stars = "、".join(d.get("major", []) or ["(无正曜)"])
        minor = "、".join(d.get("minor", [])[:4])
        hits = "、".join(d.get("sihua_hits", [])) or "无"
        lines.append(f"- {cn}({natal_cn}宫): 落于本命{d.get('host_ganzhi','?')}宫 | 主星: {stars}"
                     + (f" | 辅星: {minor}" if minor else "") + f" | 四化引动: {hits}")
    return "\n".join(lines)


def _parse_sections(text: str, keys) -> dict:
    """按【key】标记切段解析"""
    import re
    out = {}
    marks = [(m.start(), m.group(1)) for m in re.finditer(r"【([^】]+)】", text or "")]
    for i, (pos, key) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out[key] = text[pos + len(key) + 2:end].strip()
    for k in keys:
        out.setdefault(k, "")
    return out


def daily_analysis(solar_year, solar_month, solar_day, hour, sex, target: datetime.date,
                   force_refresh=False) -> dict:
    """流日六维度分析(轻量版)"""
    chart_key = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
    rkey = f"liuri-{_LIURI_VER}:{chart_key}:{target.isoformat()}"
    if not force_refresh:
        hit = _get_liuri_cache(rkey, _LIURI_TTL_DAILY)
        if hit:
            hit["_from_cache"] = True
            return hit
    try:
        chart = _build_chart(solar_year, solar_month, solar_day, hour, sex)
        frame, h = _decadal_yearly_ctx(chart, target, solar_year)
        mon = _scope_ctx(h.monthly, chart)
        day = _scope_ctx(h.daily, chart)
    except Exception as e:
        return {"error": f"排盘失败: {str(e)[:150]}"}

    prompt = f"""你是紫微斗数分析师。命主{sex}, {solar_year}年生, 当前虚岁{frame['nominal_age']}。
当前框架: 大限{frame['decadal_ganzhi']} | 流年{frame['yearly_ganzhi']} | 流月{mon['ganzhi']}
目标日期: {target.isoformat()} 流日{day['ganzhi']}, 日四化: 化禄{day['sihua']['禄']} 化权{day['sihua']['权']} 化科{day['sihua']['科']} 化忌{day['sihua']['忌']}

流日六维度落宫:
{_dims_text(day['dims'])}

请输出当日六维度提醒, 每维度1-2句(30-60字), 格式:
【事业】...
【财运】...
【健康】...
【夫妻】...
【父母】...
【儿女】...
【宜】3件当日适宜做的事(用、分隔)
【忌】3件当日应回避的事(用、分隔)
{_STYLE_RULES}"""
    content = llm_call(prompt, cache_key=f"llm:{rkey}", max_tokens=900, skip_cache=force_refresh)
    if not content:
        return {"error": "LLM 生成失败"}
    sec = _parse_sections(content, [d[0] for d in _DIMS] + ["宜", "忌"])
    result = {
        "mode": "daily", "date": target.isoformat(),
        "day_ganzhi": day["ganzhi"], "month_ganzhi": mon["ganzhi"],
        "yearly_ganzhi": frame["yearly_ganzhi"], "decadal_ganzhi": frame["decadal_ganzhi"],
        "sihua": day["sihua"],
        "dims": {d[0]: sec.get(d[0], "") for d in _DIMS},
        "yi": [x for x in sec.get("宜", "").replace("，", "、").split("、") if x][:3],
        "ji": [x for x in sec.get("忌", "").replace("，", "、").split("、") if x][:3],
        "_ver": _LIURI_VER,
    }
    if any(result["dims"].values()):
        _save_liuri_cache(rkey, result)
    return result


def monthly_analysis(solar_year, solar_month, solar_day, hour, sex, year: int, month: int,
                     force_refresh=False) -> dict:
    """流月六维度分析(深度版, 含当月重点日)"""
    chart_key = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
    rkey = f"liuyue-{_LIURI_VER}:{chart_key}:{year}-{month:02d}"
    if not force_refresh:
        hit = _get_liuri_cache(rkey, _LIURI_TTL_MONTHLY)
        if hit:
            hit["_from_cache"] = True
            return hit
    target = datetime.date(year, month, 15)  # 月中取流月四化(整月不变)
    try:
        chart = _build_chart(solar_year, solar_month, solar_day, hour, sex)
        frame, h = _decadal_yearly_ctx(chart, target, solar_year)
        mon = _scope_ctx(h.monthly, chart)
    except Exception as e:
        return {"error": f"排盘失败: {str(e)[:150]}"}
    day_table = _day_ganzhi_table(year, month)

    prompt = f"""你是紫微斗数分析师。命主{sex}, {solar_year}年生, 当前虚岁{frame['nominal_age']}。
当前框架: 大限{frame['decadal_ganzhi']} | 流年{frame['yearly_ganzhi']}
目标月份: {year}年{month}月 流月{mon['ganzhi']}, 月四化: 化禄{mon['sihua']['禄']} 化权{mon['sihua']['权']} 化科{mon['sihua']['科']} 化忌{mon['sihua']['忌']}

流月六维度落宫:
{_dims_text(mon['dims'])}

当月每日流日干支: {day_table}

请输出本月六维度分析, 每维度2-3句(60-110字), 并结合每日干支挑出3-5个该维度相关或整体重要的日期, 格式:
【事业】...
【财运】...
【健康】...
【夫妻】...
【父母】...
【儿女】...
【重点日】每行一条: M月D日 事项(12字内)
【总纲】本月一句话总策略(30字内)
{_STYLE_RULES}"""
    content = llm_call(prompt, cache_key=f"llm:{rkey}", max_tokens=1600, skip_cache=force_refresh)
    if not content:
        return {"error": "LLM 生成失败"}
    sec = _parse_sections(content, [d[0] for d in _DIMS] + ["重点日", "总纲"])
    key_days = [ln.strip() for ln in sec.get("重点日", "").splitlines() if ln.strip()][:5]
    result = {
        "mode": "monthly", "month": f"{year}-{month:02d}",
        "month_ganzhi": mon["ganzhi"], "yearly_ganzhi": frame["yearly_ganzhi"],
        "decadal_ganzhi": frame["decadal_ganzhi"], "sihua": mon["sihua"],
        "dims": {d[0]: sec.get(d[0], "") for d in _DIMS},
        "key_days": key_days, "summary": sec.get("总纲", ""),
        "_ver": _LIURI_VER,
    }
    if any(result["dims"].values()):
        _save_liuri_cache(rkey, result)
    return result
