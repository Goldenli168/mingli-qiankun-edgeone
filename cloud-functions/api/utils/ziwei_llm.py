"""
命理乾坤 · LLM 生成模块
供 ziwei_core 调用
版本: v1.0
"""
from .llm_client import llm_call

# 诊断日志（最多存10条）
_last_llm_debug = []


def _build_liunian_context(ln, result, patterns, solar_year):
    """构建流年LLM上下文"""
    year = ln.get("年份", 0)
    gz = ln.get("流年干支", "")
    # 太岁
    ZHI = list("子丑寅卯辰巳午未申酉戌亥")
    year_zhi = ZHI[(year - 4) % 12]
    # 命宫
    ming_branch = None
    for p in result.get("十二宫", []):
        if p.get("是否命宫"):
            ming_branch = p["宫位"]
            break
    # 化曜落宫
    sihua = ln.get("四化", {})
    sihua_parts = []
    for k, v in sihua.items():
        if v:
            sihua_parts.append(f"{k}:{v}")
    ln_palace_sihua = " | ".join(sihua_parts) if sihua_parts else "无"
    # 命宫庙旺
    ln_star_mw = ""
    if ming_branch:
        for p in result.get("十二宫", []):
            if p["宫位"] == ming_branch:
                mw = p.get("庙旺", {})
                if mw:
                    mw_parts = [f"{s}{v}" for s, v in mw.items() if v]
                    ln_star_mw = "、".join(mw_parts)
                break
    # 时代背景
    era_info = "2026年丙午，火旺之年，利行动忌冲动"
    return {
        "ln_gz": gz,
        "ln_palace_sihua": ln_palace_sihua,
        "ln_taisui": f"{year}年{year_zhi}",
        "ln_star_mw": ln_star_mw,
        "era_info": era_info,
    }


def _build_dayun_context(dy, result, patterns):
    """构建大运LLM上下文"""
    birth = result.get("基本信息", {}).get("公历", "")[:4]
    bazi = result.get("八字联合", {}).get("日主", "") + result.get("八字联合", {}).get("日主状态", "")
    scores = dy.get("评分", {})
    score_str = " ".join([f"{k}{v}分" for k, v in scores.items() if not k.endswith("_llm")])
    return {
        "dayun_age": f"{dy.get('起始年龄','')}-{dy.get('结束年龄','')}",
        "dayun_gong": dy.get("大运宫名", dy.get("宫位", "")),
        "dayun_score": dy.get("综合评分", ""),
        "birth": birth,
        "bazi": bazi,
        "scores": score_str,
    }


def _build_summary_context(result, patterns):
    """构建命盘总结LLM上下文"""
    birth = result.get("基本信息", {}).get("公历", "")[:4]
    bazi = result.get("八字联合", {}).get("日主", "") + result.get("八字联合", {}).get("日主状态", "")
    pattern_names = "、".join([p.get("name", "") for p in patterns[:3]])
    laiyin = result.get("来因宫", {})
    laiyin_stars = "、".join(laiyin.get("主星", []))
    # 三方四正
    ming_branch = None
    for p in result.get("十二宫", []):
        if p.get("是否命宫"):
            ming_branch = p["宫位"]
            break
    sanfang = ""
    if ming_branch is not None:
        ZHI = list("子丑寅卯辰巳午未申酉戌亥")
        # ming_branch 可能是数字索引（宫位）或地支名称
        if isinstance(ming_branch, int):
            mi = ming_branch
        else:
            mi = ZHI.index(ming_branch)
        offsets = [4, 8, 6]  # 财帛、官禄、迁移
        sf_names = []
        for off in offsets:
            idx = (mi + off) % 12
            for p in result.get("十二宫", []):
                if p["宫位"] == idx:
                    stars = "、".join(p.get("主星", [])[:2])
                    if stars:
                        sf_names.append(f"{p['宫名']}({stars})")
                    break
        sanfang = "、".join(sf_names)
    wealth = result.get("财富级别", {}).get("级别", "")
    ming = result.get("命宫地支", "")
    shen = result.get("身宫地支", "")
    return {
        "birth": birth,
        "bazi": bazi,
        "patterns": pattern_names,
        "laiyin_stars": laiyin_stars,
        "sanfang": sanfang,
        "wealth": wealth,
        "ming": ming,
        "shen": shen,
    }


def _llm_generate(gen_type: str, ctx: dict) -> str | None:
    """通用LLM生成器: liunian/dayun/summary，失败返回None回退模板"""

    if gen_type == "liunian":
        prompt = f"""你是资深紫微斗数命理师。分析{ctx.get("ln_gz","")}年。

【必须使用以下命盘数据,编造宫位将导致分析完全错误】
化曜落宫: {ctx.get("ln_palace_sihua","")}  太岁: {ctx.get("ln_taisui","")}
命宫庙旺: {ctx.get("ln_star_mw","")}  特征: {ctx.get("era_info","")}

|||分隔3段,禁止输出"A""B""C"等标题:

段1(40字): 仅一句话,化忌在【XX宫】(必须从上方化曜数据提取),点出全年最大问题

段2(>130字,5项,每项基于上方化曜+庙旺数据):
1机会:化禄/权/科各落入哪个宫(从上方数据提取) - 怎么加把劲发挥极致(庙旺星加分)
2风险:化忌落入哪个宫(从上方数据提取) - 哪些具体事件(健康/财务/感情)会触发
3联动:化忌冲对宫产生什么连锁影响
4应期:该宫位问题最可能哪个农历月爆发
5避灾:一句化解建议

段3(>120字): 6双月每双月15字具体应事:
正二月-事件|||三四月-事件|||五六月-事件|||七八月-事件|||九十月-事件|||十一十二月-事件

禁止输出"2020s""经济周期""时代背景""第一段"等标签。"""

    elif gen_type == "dayun":
        sc = ctx.get('scores','')
        prompt = f"""资深命理师。请分析这大运,输出1段约500字综合点评(包含7维):
{ctx.get('dayun_age','')}岁{ctx.get('dayun_gong','')}宫{ctx.get('dayun_score','')}分。生于{ctx.get('birth','')}年{ctx.get('bazi','')[:50]}。维度:{sc}。
内容要包含:财富、事业、婚姻、子女、父母、健康、大运整体结论7部分,各部分60-80字。
口语务实,结合时代背景,直接输出。"""

    elif gen_type == "dayun_brief":
        sc = ctx.get('scores','')
        prompt = f"""资深命理师。请分析这大运,输出1段约350字综合点评(包含7维):
{ctx.get('dayun_age','')}岁{ctx.get('dayun_gong','')}宫{ctx.get('dayun_score','')}分。生于{ctx.get('birth','')}年{ctx.get('bazi','')[:50]}。维度:{sc}。
7维(财富/事业/婚姻/子女/父母/健康/整体结论)各40-50字。
口语务实,直接输出。"""

    elif gen_type == "summary":
        prompt = f"""你是资深命理分析师。请为以下命盘写一段180字全局总结。

生于{ctx.get('birth','')}，{ctx.get('bazi','')}，格局：{ctx.get('patterns','')}，来因宫：{ctx.get('laiyin_stars','')}，三方四正：{ctx.get('sanfang','')}，财富级别：{ctx.get('wealth','')}。命宫{ctx.get('ming','')}，身宫{ctx.get('shen','')}。

从来因宫出发：①此生核心课题与天赋赛道 ②三方四正联动看一生转折点 ③中晚年生活形态建议。结合时代背景给出务实参考，语气专业有温度，直接输出。"""
    else:
        return None

    # 缓存key：简洁格式,gen_type+年龄
    import time as _t
    try:
        age = ctx.get('dayun_age', ctx.get('ln_gz', ''))
        ck = f"zw:{gen_type}:{hash(str(age))}:v19"
    except:
        ck = f"zw:{gen_type}:{int(_t.time())}"
    max_tok = 800  # P56: 保持800（用户要求，不能减少）
    result = llm_call(prompt, ck, max_tokens=max_tok)
    # 诊断日志(列表,最多存10条)
    global _last_llm_debug
    _last_llm_debug.append({
        'gen_type': gen_type, 'max_tok': max_tok,
        'prompt_len': len(prompt), 'prompt_head': prompt[:80],
        'result_len': len(result) if result else 0,
        'sep_count': result.count('|||') if result else 0,
        'result_head': (result[:120] if result else 'NONE'),
        'result_tail': (result[-150:] if result else 'NONE')
    })
    if len(_last_llm_debug) > 10:
        _last_llm_debug = _last_llm_debug[-10:]
    return result
