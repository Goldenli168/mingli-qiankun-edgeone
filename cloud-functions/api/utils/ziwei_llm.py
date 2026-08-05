"""
命理乾坤 · LLM 生成模块
供 ziwei_core 调用
版本: v1.0
"""
from .llm_client import llm_call
from .ziwei_data import _SIHUA_TABLE, _SIHUA_LABELS

# 诊断日志（最多存10条）
_last_llm_debug = []

# P60: 强制刷新LLM标志(由ziwei_core设置,勾选"强制刷新LLM"时为True)
_FORCE_REFRESH = False


def _age_stage(age):
    """人生阶段描述(P59: 用于LLM年龄约束,防止对小孩谈婚姻职场)"""
    if age < 7: return "幼儿期,只能谈:家庭环境、性格雏形、健康养育,严禁谈学业压力/感情/事业/财富"
    if age < 13: return "童年期(小学阶段),只能谈:学业启蒙、兴趣培养、性格养成、家庭氛围、童年健康,严禁谈婚姻/职场/投资"
    if age < 19: return "青少年期(中学阶段),侧重:学业考试、叛逆期心理、同学关系、兴趣方向,严禁谈婚姻/职场"
    if age < 24: return "青年早期(大学或初入社会),侧重:学业职业起点、初恋与情感探索、独立生活、方向选择"
    if age < 31: return "青年期(20多岁),侧重:事业打拼与跳槽选择、婚恋相亲、租房买房压力、自我定位"
    if age < 41: return "壮年早期(30多岁),侧重:事业上升与瓶颈、婚姻经营、育儿压力、房贷车贷、健康预警"
    if age < 51: return "壮年后期(40多岁),侧重:事业高原与转型、子女升学、父母养老、中年婚姻经营、慢性病预防"
    if age < 61: return "中年期(50多岁),侧重:事业收尾与传承、子女成家立业、孙辈、退休规划、健康管理"
    return "晚年期(60岁以上),侧重:退休生活、健康养生、含饴弄孙、财富传承、心态调适"


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
    # P59: ln["四化"]为空时用该流年自己的天干算四化+星曜落本命宫位
    # (严禁用飞化分析的流年四化——那是固定当前年的数据,会导致2028年错用2026年四化)
    if not sihua_parts:
        ln_gan = gz[0] if gz else ""  # 流年天干(如"戊申"→"戊")
        sihua_stars = _SIHUA_TABLE.get(ln_gan, ["", "", "", ""])  # [禄,权,科,忌]星名
        # 星曜在本命盘的宫位
        star_palace = {}
        for p in result.get("十二宫", []):
            for s in (p.get("主星", []) or []) + (p.get("辅星", []) or []):
                star_palace.setdefault(s, p.get("宫名", ""))
        for hi, sname in enumerate(sihua_stars):
            if sname:
                palace = star_palace.get(sname, "?")
                sihua_parts.append(f"{_SIHUA_LABELS[hi]}:{sname}落{palace}宫")
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
    # P59: 流年对应年龄+人生阶段
    ln_age = year - solar_year + 1  # 虚岁
    return {
        "ln_gz": gz,
        "ln_palace_sihua": ln_palace_sihua,
        "ln_taisui": f"{year}年{year_zhi}",
        "ln_star_mw": ln_star_mw,
        "era_info": era_info,
        "ln_age": ln_age,
        "age_stage": _age_stage(ln_age),
    }


def _build_dayun_context(dy, result, patterns):
    """构建大运LLM上下文"""
    birth = result.get("基本信息", {}).get("公历", "")[:4]
    bazi = result.get("八字联合", {}).get("日主", "") + result.get("八字联合", {}).get("日主状态", "")
    scores = dy.get("评分", {})
    score_str = " ".join([f"{k}{v}分" for k, v in scores.items() if not k.endswith("_llm")])
    # P58: 大运四化(用户要求:维度分析须结合四化影响)
    sihua = dy.get("大运四化", {})
    sihua_str = " ".join([f"{k}·{v}" for k, v in sihua.items()])
    # P59: 大运起始年龄的人生阶段(防止对小孩谈婚姻职场)
    age_stage = _age_stage(dy.get("起始年龄", 30))
    return {
        "dayun_age": f"{dy.get('起始年龄','')}-{dy.get('结束年龄','')}",
        "dayun_gong": dy.get("大运宫名", dy.get("宫位", "")),
        "dayun_score": dy.get("综合评分", ""),
        "birth": birth,
        "bazi": bazi,
        "scores": score_str,
        "sihua": sihua_str,
        "age_stage": age_stage,
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


def _build_feihua_context(result, solar_year):
    """构建三维四化LLM上下文(P59: 大白话接地气解读)"""
    import datetime as _dt2
    feihua = result.get("飞化分析", {})
    def _fmt(items):
        return " ".join([f"{it.get('四化','')}·{it.get('星曜','')}落{it.get('来源宫','')}宫" for it in items])
    age = _dt2.datetime.now().year - solar_year + 1  # 当前虚岁
    return {
        "natal": _fmt(feihua.get("飞化", [])),
        "dayun": _fmt(feihua.get("大运四化", [])),
        "liunian": _fmt(feihua.get("流年四化", [])),
        "age": age,
    }


def _build_monthly_context(ln, result, solar_year):
    """构建行动清单LLM上下文(P62: 每月个性化建议)"""
    year = ln.get("年份", 0)
    months = ln.get("逐月", [])[:12]
    age = year - solar_year + 1  # 该年虚岁
    return {
        "year": year,
        "months": "\n".join(months),
        "age": age,
        "age_stage": _age_stage(age),
    }


def _llm_generate(gen_type: str, ctx: dict) -> str | None:
    """通用LLM生成器: liunian/dayun/summary，失败返回None回退模板"""

    if gen_type == "liunian":
        prompt = f"""你是资深紫微斗数命理师。分析{ctx.get("ln_gz","")}年。

【必须使用以下命盘数据,编造宫位将导致分析完全错误】
化曜落宫: {ctx.get("ln_palace_sihua","")}  太岁: {ctx.get("ln_taisui","")}
命宫庙旺: {ctx.get("ln_star_mw","")}  特征: {ctx.get("era_info","")}
命主该年{ctx.get("ln_age","")}岁(虚岁),处于:{ctx.get("age_stage","")}

【年龄约束】所有分析必须符合命主该年实际年龄的生活场景(例如对10岁孩子只谈学业兴趣,对40岁的人谈事业家庭健康),严禁出现与年龄不符的内容(如对小孩谈婚姻投资,对老人谈求职)。

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
        sihua = ctx.get('sihua','')
        stage = ctx.get('age_stage','')
        prompt = f"""资深命理师。请分析这大运,输出7个维度的点评:
{ctx.get('dayun_age','')}岁{ctx.get('dayun_gong','')}宫{ctx.get('dayun_score','')}分。生于{ctx.get('birth','')}年{ctx.get('bazi','')[:50]}。大运四化:{sihua}。维度:{sc}。
命主在此大运处于:{stage}
要求:
1. 输出7个维度:财富、事业、婚姻、子女、父母、健康、大运整体结论
2. 前6维每维严格控制在80字以内,必须结合大运四化(化禄/化权/化科/化忌)分析其对该维度的具体影响
3. 大运整体结论150字左右,详细分析这十年的整体走势、关键策略与人生建议
4. 【重要】所有内容必须符合命主该年龄段的实际生活场景,例如对3-12岁儿童只能谈学业兴趣家庭,严禁谈婚姻职场投资;对60岁以上老人不谈跳槽晋升
5. 格式:每维独立一段,开头用 **【维度名 分数】** 标记,例如 **【财富 57分】** 然后换行写内容
6. 口语务实,直接输出,不要多余开场白。"""

    elif gen_type == "dayun_brief":
        sc = ctx.get('scores','')
        prompt = f"""资深命理师。请分析这大运,输出1段约350字综合点评(包含7维):
{ctx.get('dayun_age','')}岁{ctx.get('dayun_gong','')}宫{ctx.get('dayun_score','')}分。生于{ctx.get('birth','')}年{ctx.get('bazi','')[:50]}。维度:{sc}。
7维(财富/事业/婚姻/子女/父母/健康/整体结论)各40-50字。
口语务实,直接输出。"""

    elif gen_type == "feihua":
        prompt = f"""你是说话接地气的资深命理师,像朋友聊天一样解读四化飞星,说人话。
命主{ctx.get('age','')}岁。三组四化数据:
本命四化:{ctx.get('natal','')}
大运四化:{ctx.get('dayun','')}
流年四化:{ctx.get('liunian','')}

要求:
1. 逐条输出共12条,格式严格为: "本命化X·星落X宫: 大白话解读" / "大运化X·星落X宫: ..." / "流年化X·星落X宫: ..."
2. 每条30-40字,联系命主{ctx.get('age','')}岁的真实生活场景(职场、房贷、孩子教育、父母健康、婚姻关系等)
3. 化禄=机会与收获,化权=主导与压力,化科=贵人与名声,化忌=风险与波折,解读必须符合吉凶性质
4. 严禁空话套话("宜守不宜攻""凡事留有余地""把握机遇""展现才华"等),要具体到可感知的事(如"今年赚钱门路多,但别裸辞""跟配偶容易为钱拌嘴,工资卡别藏着掖着")
5. 直接输出12条,不要开场白不要总结。"""

    elif gen_type == "monthly":
        prompt = f"""你是说话接地气的资深命理师,给命主的{ctx.get('year','')}年12个月各写一条具体行动建议。
命主该年{ctx.get('age','')}岁(虚岁),处于:{ctx.get('age_stage','')}
每月运势数据(月份：宫位(星曜) 四化 — 主题):
{ctx.get('months','')}

要求:
1. 输出12条,格式严格为"正月：建议内容",月份必须与输入逐月对应
2. 每条25-35字,结合该月宫位主题+星曜特质+四化吉凶(如有),给出可立即执行的具体行动
3. 联系命主{ctx.get('age','')}岁的真实生活(职场/家庭/财务/健康/孩子),说人话
4. 严禁空话套话("顺势而为""把握机遇""注意身体""宜社交活动"等),要具体到事(如"把年假排在这个月带爸妈做全身体检""这个月别签任何合同,重要谈判推到下月")
5. 直接输出12条,不要开场白不要总结。"""

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
        ck = f"zw:{gen_type}:{hash(str(age))}:v24"
    except:
        ck = f"zw:{gen_type}:{int(_t.time())}"
    max_tok = 800  # P56: 保持800（用户要求，不能减少）
    result = llm_call(prompt, ck, max_tokens=max_tok, skip_cache=_FORCE_REFRESH)
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
