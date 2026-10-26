# -*- coding: utf-8 -*-
"""P90: 流月/流日 六维度命理分析模块（事业/财运/健康/夫妻/父母/儿女）
数据层: iztro_py horoscope(流月/流日干支+宫名映射+四化) + 本命盘宫星
分析层: llm_call(prompt, cache_key) 复用现有 DeepSeek 缓存
缓存命名空间: liuri-v4:{chart}:{profile_hash}:{couple_hash}:{YYYY-MM-DD} / liuyue-v4:{chart}:{profile_hash}::{YYYY-MM}
v2: 事件化断语(具体场景+动作) + 总运指数 + 定调金句(headline)
v3: 命主档案接入(职业/婚姻/子女/关注领域定制场景) + 昨日回顾(peek_daily) + 一键应验反馈(fb_token/record_feedback)
v4: 开运元素(色/方位/数字, 规则推导零LLM) + 双盘合参(couple参数) + 月度应验统计(fb_stats)
"""
import os
import json
import hashlib
import datetime

from .llm_client import llm_call
from .bazi_data import GAN, ZHI


def _gan_zhi(stem_en, branch_en) -> str:
    """iztro 英文干支名 → 中文干支"""
    from .ziwei_core import _parse_stem, _parse_branch
    return GAN[_parse_stem(str(stem_en))] + ZHI[_parse_branch(str(branch_en))]

_LIURI_VER = "v4"

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


# ============ 命主档案 / 昨日回顾 / 应验反馈 ============

def _profile_text(profile) -> str:
    """命主档案 → prompt 行。profile 为 dict, 如 {职业:..., 婚姻:..., 子女:..., 关注:...}"""
    if not profile or not isinstance(profile, dict):
        return ""
    parts = [f"{k}={v}" for k, v in profile.items() if v]
    return " | ".join(parts)


def _profile_hash(profile) -> str:
    """档案参与缓存 key, 防换档案串号(同 bazi 缓存 key 隔离原则)"""
    if not profile:
        return ""
    raw = json.dumps(profile, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]


def peek_daily(solar_year, solar_month, solar_day, hour, sex, target: datetime.date,
               profile=None) -> dict:
    """只读缓存取某日流日摘要(昨日回顾用), 不触发 LLM 生成。
    前缀扫描兼容历史版本(v2/v3 均可被回顾)"""
    chart_key = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
    ph = _profile_hash(profile)
    suffix = f":{target.isoformat()}"
    prefix_legacy = f":{chart_key}:{target.isoformat()}"  # v1/v2 无档案段
    mid_v3 = f":{chart_key}:{ph}:"  # v3: chart:ph:date / v4: chart:ph:couple:date
    raw = _load_liuri_cache()
    for k, v in raw.items():
        if not k.startswith("liuri-"):
            continue
        if (mid_v3 in k and k.endswith(suffix)) or (not ph and k.endswith(prefix_legacy)):
            d = v.get("data") or {}
            return {"date": d.get("date"), "day_ganzhi": d.get("day_ganzhi"),
                    "score": d.get("score"), "headline": d.get("headline"),
                    "dims": d.get("dims", {}), "ver": d.get("_ver", "")}
    return None


_FB_FILE = os.path.join(_CACHE_DIR, "ml_liuri_feedback.json")


def fb_token(solar_year, solar_month, solar_day, hour, sex, date_str: str) -> str:
    """一键反馈链接的防伪 token(无需 API key, 但不可伪造)"""
    secret = os.environ.get("ML_API_KEY", "mingli-qiankun-v7")
    raw = f"fb:{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}:{date_str}:{secret}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def record_feedback(solar_year, solar_month, solar_day, hour, sex, date_str: str, value: str) -> bool:
    """记录应验反馈 hit/miss 到 ml_liuri_feedback.json"""
    if value not in ("hit", "miss"):
        return False
    try:
        raw = {}
        if os.path.exists(_FB_FILE):
            with open(_FB_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        ck = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
        raw.setdefault(ck, {})[date_str] = {"v": value, "ts": datetime.datetime.now().timestamp()}
        with open(_FB_FILE, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False)
        return True
    except Exception:
        return False


# ============ v4: 开运元素 / 应验统计 / 双盘合参 ============

# 日干五行 → 开运元素(规则推导, 零 LLM 成本)
# 开运色=日干五行本色(同气相扶); 助运方位=生日干之五行方位(印星护身); 幸运数字=日干五行河图数
_WUXING_OF_GAN = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
                  "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
_LUCKY = {
    "木": {"color": "青/绿", "direction": "北", "number": "3、8"},   # 水生木
    "火": {"color": "红/紫", "direction": "东", "number": "2、7"},   # 木生火
    "土": {"color": "黄/咖", "direction": "南", "number": "5、0"},   # 火生土
    "金": {"color": "白/金", "direction": "西南", "number": "4、9"},  # 土生金
    "水": {"color": "黑/蓝", "direction": "西", "number": "1、6"},   # 金生水
}


def lucky_elements(day_gan: str) -> dict:
    """流日天干 → 开运色/助运方位/幸运数字"""
    wx = _WUXING_OF_GAN.get(day_gan, "土")
    d = _LUCKY[wx]
    return {"wuxing": wx, "color": d["color"], "direction": d["direction"], "number": d["number"]}


def fb_stats(solar_year, solar_month, solar_day, hour, sex, year: int, month: int) -> dict:
    """读反馈文件, 统计指定月份(YYYY-MM)的应验率, 无数据返回 None"""
    if not os.path.exists(_FB_FILE):
        return None
    try:
        with open(_FB_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        ck = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
        entries = raw.get(ck, {})
        prefix = f"{year}-{month:02d}-"
        hit = sum(1 for d, v in entries.items() if d.startswith(prefix) and v.get("v") == "hit")
        miss = sum(1 for d, v in entries.items() if d.startswith(prefix) and v.get("v") == "miss")
        total = hit + miss
        if total == 0:
            return None
        return {"month": f"{year}-{month:02d}", "hit": hit, "miss": miss,
                "total": total, "rate": round(hit * 100 / total)}
    except Exception:
        return None


def _couple_hash(couple) -> str:
    if not couple:
        return ""
    return hashlib.md5(",".join(map(str, couple)).encode()).hexdigest()[:8]


def couple_analysis(main_params, couple_params, target: datetime.date, main_day_ctx: dict) -> str:
    """双盘合参: 双方当日信号交叉 → 一段互动提示(40-70字)。失败返回空串(不拖垮主流程)"""
    try:
        cy, cm, cd, ch, csex = couple_params
        c_chart = _build_chart(cy, cm, cd, ch, csex)
        _, c_h = _decadal_yearly_ctx(c_chart, target, cy)
        c_day = _scope_ctx(c_h.daily, c_chart)
        c_sihua = c_day["sihua"]
        # 双方夫妻宫落点星曜(合参核心)
        def _spouse_line(ctx):
            d = ctx["dims"].get("夫妻", {})
            stars = "、".join(d.get("major", []) or ["无正曜"])
            hits = "、".join(d.get("sihua_hits", [])) or "无"
            return f"{d.get('host_ganzhi', '?')}宫 主星{stars} 引动{hits}"
        s = main_day_ctx["sihua"]
        ck = f"llm:couple-v1:{main_params}:{couple_params}:{target.isoformat()}"
        prompt = f"""你是紫微斗数分析师, 为一对伴侣写"今日双盘合参"。
目标日期: {target.isoformat()}

甲方: 流日{main_day_ctx['ganzhi']}, 日四化 化禄{s['禄']} 化权{s['权']} 化科{s['科']} 化忌{s['忌']}
甲方夫妻宫: {_spouse_line(main_day_ctx)}
乙方: 流日{c_day['ganzhi']}, 日四化 化禄{c_sihua['禄']} 化权{c_sihua['权']} 化科{c_sihua['科']} 化忌{c_sihua['忌']}
乙方夫妻宫: {_spouse_line(c_day)}

要求:
1. 输出一段40-70字的互动提示: 点明今日两人相处的一个具体场景(如晚餐沟通/家务分工/财务商量/亲子安排), 给出"谁宜主动、谁宜让步"的明确动作
2. 紧扣双方四化引动, 禁止编造星曜; 不夸大吉凶, 不写"相克/注定"式断语
3. 只输出这一段话, 无任何标记与说明"""
        return (llm_call(prompt, cache_key=ck, max_tokens=200) or "").strip()[:120]
    except Exception:
        return ""


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
2. 事件化: 每条必须落到具体场景——点明具体事务(如签约/报销/汇报/聚餐/转账)、给出明确动作(做什么/避开什么), 可验证可执行, 禁止"易有波动""需注意"式空泛描述
3. 语气: 专业直白, 像军师对命主当面进言, 不模板化, 不堆术语
4. 信号只讲"引动/应象", 不夸大吉凶; 健康维度只提醒作息与检查, 只许用"注意/关注/宜检查"句式, 严禁断病
5. 若给出命主档案, 场景必须贴合档案: 管理层写团队/汇报/决策场景, 已婚已育写伴侣与孩子互动; 严禁错位场景(给已婚者写相亲桃花、给管理层写求职面试)
6. 严格按格式输出, 不要输出任何额外说明"""


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
                   force_refresh=False, profile=None, couple=None) -> dict:
    """流日六维度分析(轻量版)。couple=(年,月,日,时,性别) 时附双盘合参段"""
    chart_key = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
    ph = _profile_hash(profile)
    ch = _couple_hash(couple)
    rkey = f"liuri-{_LIURI_VER}:{chart_key}:{ph}:{ch}:{target.isoformat()}"
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

    ptext = _profile_text(profile)
    profile_line = f"命主档案: {ptext}\n" if ptext else ""
    prompt = f"""你是紫微斗数分析师。命主{sex}, {solar_year}年生, 当前虚岁{frame['nominal_age']}。
{profile_line}当前框架: 大限{frame['decadal_ganzhi']} | 流年{frame['yearly_ganzhi']} | 流月{mon['ganzhi']}
目标日期: {target.isoformat()} 流日{day['ganzhi']}, 日四化: 化禄{day['sihua']['禄']} 化权{day['sihua']['权']} 化科{day['sihua']['科']} 化忌{day['sihua']['忌']}

流日六维度落宫:
{_dims_text(day['dims'])}

请输出当日六维度提醒, 每维度1-2句(35-65字), 格式:
【事业】...
【财运】...
【健康】...
【夫妻】...
【父母】...
【儿女】...
【宜】3件当日适宜做的具体事(用、分隔)
【忌】3件当日应回避的具体事(用、分隔)
【指数】当日总运指数(0-100整数, 综合六维度吉凶与四化引动强弱评分, 只输出数字)
【定调】当日一句话定调(15字内, 点出当日最强信号与核心策略, 如"财星化禄, 宜谈薪签约")
{_STYLE_RULES}"""
    content = llm_call(prompt, cache_key=f"llm:{rkey}", max_tokens=1000, skip_cache=force_refresh)
    if not content:
        return {"error": "LLM 生成失败"}
    sec = _parse_sections(content, [d[0] for d in _DIMS] + ["宜", "忌", "指数", "定调"])
    import re as _re
    m = _re.search(r"\d+", sec.get("指数", ""))
    score = max(0, min(100, int(m.group()))) if m else None
    result = {
        "mode": "daily", "date": target.isoformat(),
        "day_ganzhi": day["ganzhi"], "month_ganzhi": mon["ganzhi"],
        "yearly_ganzhi": frame["yearly_ganzhi"], "decadal_ganzhi": frame["decadal_ganzhi"],
        "sihua": day["sihua"],
        "dims": {d[0]: sec.get(d[0], "") for d in _DIMS},
        "yi": [x for x in sec.get("宜", "").replace("，", "、").split("、") if x][:3],
        "ji": [x for x in sec.get("忌", "").replace("，", "、").split("、") if x][:3],
        "score": score, "headline": sec.get("定调", "")[:20],
        "lucky": lucky_elements(day["gan"]),
        "_ver": _LIURI_VER,
    }
    if couple:
        main_params = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
        result["couple"] = couple_analysis(main_params, couple, target, day)
    if any(result["dims"].values()):
        _save_liuri_cache(rkey, result)
    return result


def monthly_analysis(solar_year, solar_month, solar_day, hour, sex, year: int, month: int,
                     force_refresh=False, profile=None) -> dict:
    """流月六维度分析(深度版, 含当月重点日)"""
    chart_key = f"{solar_year}:{solar_month}:{solar_day}:{hour}:{sex}"
    ph = _profile_hash(profile)
    rkey = f"liuyue-{_LIURI_VER}:{chart_key}:{ph}:{year}-{month:02d}"
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

    ptext = _profile_text(profile)
    profile_line = f"命主档案: {ptext}\n" if ptext else ""
    prompt = f"""你是紫微斗数分析师。命主{sex}, {solar_year}年生, 当前虚岁{frame['nominal_age']}。
{profile_line}当前框架: 大限{frame['decadal_ganzhi']} | 流年{frame['yearly_ganzhi']}
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
【重点日】每行一条: M月D日 具体事项(12字内, 点明做什么, 如"3月8日 宜提交晋升申请")
【总纲】本月一句话总策略(30字内)
【指数】本月总运指数(0-100整数, 综合六维度吉凶与月四化引动强弱评分, 只输出数字)
【定调】本月一句话定调(15字内, 点出本月最强信号, 如"太阴化权, 事业进取月")
{_STYLE_RULES}"""
    content = llm_call(prompt, cache_key=f"llm:{rkey}", max_tokens=1700, skip_cache=force_refresh)
    if not content:
        return {"error": "LLM 生成失败"}
    sec = _parse_sections(content, [d[0] for d in _DIMS] + ["重点日", "总纲", "指数", "定调"])
    key_days = []
    for ln in sec.get("重点日", "").splitlines():
        for item in ln.replace(";", "；").split("；"):
            item = item.strip()
            if item:
                key_days.append(item)
    key_days = key_days[:5]
    import re as _re
    m = _re.search(r"\d+", sec.get("指数", ""))
    score = max(0, min(100, int(m.group()))) if m else None
    result = {
        "mode": "monthly", "month": f"{year}-{month:02d}",
        "month_ganzhi": mon["ganzhi"], "yearly_ganzhi": frame["yearly_ganzhi"],
        "decadal_ganzhi": frame["decadal_ganzhi"], "sihua": mon["sihua"],
        "dims": {d[0]: sec.get(d[0], "") for d in _DIMS},
        "key_days": key_days, "summary": sec.get("总纲", ""),
        "score": score, "headline": sec.get("定调", "")[:20],
        "_ver": _LIURI_VER,
    }
    # 上月应验统计(有反馈数据才附)
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    stats = fb_stats(solar_year, solar_month, solar_day, hour, sex, py, pm)
    if stats:
        result["fb_stats"] = stats
    if any(result["dims"].values()):
        _save_liuri_cache(rkey, result)
    return result
