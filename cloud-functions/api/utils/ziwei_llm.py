"""
命理乾坤 · LLM 生成模块
供 ziwei_core 调用
版本: v1.0
"""
from .llm_client import llm_call, _profile_text, _phash, _stable_hash, _feedback_text, _fhash
from .ziwei_data import _SIHUA_TABLE, _SIHUA_LABELS

# 诊断日志（最多存10条）
_last_llm_debug = []

# P60: 强制刷新LLM标志(由ziwei_core设置,勾选"强制刷新LLM"时为True)
_FORCE_REFRESH = False


def _profile_ctx(result):
    """P70: 从result取命主画像,返回(prompt注入文本, 画像hash)二元组"""
    p = result.get("命主画像") if isinstance(result, dict) else None
    return _profile_text(p), _phash(p)


def _feedback_ctx(result):
    """P80: 从result取验证反馈,返回(prompt注入文本, 反馈hash)二元组"""
    fb = result.get("验证反馈") if isinstance(result, dict) else None
    return _feedback_text(fb), _fhash(fb)


def _chart_key(result):
    """P75: 命盘唯一指纹(公历+性别)——zw缓存key此前只有age/dayun_age,
    summary的age为空串→所有命盘共用一条summary缓存(A盘总结串到B盘),
    liunian/dayun/feihua/monthly同理按干支/年龄段互相串盘"""
    info = result.get("基本信息", {}) if isinstance(result, dict) else {}
    return _stable_hash(f"{info.get('公历','')}|{info.get('性别','')}")


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
    _ptext, _ph = _profile_ctx(result)  # P70
    _ftext, _fh = _feedback_ctx(result)  # P80
    return {
        "ln_gz": gz,
        "ln_palace_sihua": ln_palace_sihua,
        "ln_taisui": f"{year}年{year_zhi}",
        "ln_star_mw": ln_star_mw,
        "era_info": era_info,
        "ln_age": ln_age,
        "age_stage": _age_stage(ln_age),
        "profile_text": _ptext,
        "profile_phash": _ph,
        "feedback_text": _ftext,
        "feedback_fhash": _fh,
        "chart_key": _chart_key(result),
    }


def _build_dayun_context(dy, result, patterns):
    """构建大运LLM上下文"""
    birth = result.get("基本信息", {}).get("公历", "")[:4]
    bazi = result.get("八字联合", {}).get("日主", "") + result.get("八字联合", {}).get("日主状态", "")
    scores = dy.get("评分", {})
    score_str = " ".join([f"{k}{v}分" for k, v in scores.items() if not k.endswith("_llm")])
    # P58: 大运四化(用户要求:维度分析须结合四化影响)
    sihua = dy.get("大运四化", {})
    # P71: 四化落宫(本命宫+大运盘宫)——此前只传星名,LLM不知落宫,
    # 把化科等泛化含义强行套到无关维度(如化科落父母宫却写成利婚姻)
    ZHI = list("子丑寅卯辰巳午未申酉戌亥")
    PALACE_SEQ = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
                  "迁移", "交友", "官禄", "田宅", "福德", "父母"]
    star_natal = {}  # 星曜→本命宫名
    gong_branch = {}  # 宫名→地支索引
    for p in result.get("十二宫", []):
        b = p.get("宫位")
        b = b if isinstance(b, int) else (ZHI.index(b) if b in ZHI else None)
        if b is not None:
            gong_branch[p.get("宫名", "")] = b
        for s in (p.get("主星") or []) + (p.get("辅星") or []):
            star_natal.setdefault(s, p.get("宫名", ""))
    # 大运命宫的地支索引(大运宫名=本命某宫名,取其地支)
    dy_branch = gong_branch.get(dy.get("大运宫名", ""))
    sihua_parts = []
    for k, v in sihua.items():
        if not v:
            continue
        natal_p = star_natal.get(v, "?")
        dy_p = "?"
        if dy_branch is not None and natal_p in gong_branch:
            dy_p = PALACE_SEQ[(dy_branch - gong_branch[natal_p]) % 12]
        sihua_parts.append(f"{k}·{v}(本命{natal_p}宫/大运{dy_p}宫)".replace("宫宫", "宫"))
    sihua_str = " ".join(sihua_parts) if sihua_parts else "无"
    # P59: 大运起始年龄的人生阶段(防止对小孩谈婚姻职场)
    age_stage = _age_stage(dy.get("起始年龄", 30))
    _ptext, _ph = _profile_ctx(result)  # P70
    _ftext, _fh = _feedback_ctx(result)  # P80
    return {
        "dayun_age": f"{dy.get('起始年龄','')}-{dy.get('结束年龄','')}",
        "dayun_gong": dy.get("大运宫名", dy.get("宫位", "")),
        "dayun_score": dy.get("综合评分", ""),
        "birth": birth,
        "bazi": bazi,
        "scores": score_str,
        "sihua": sihua_str,
        "age_stage": age_stage,
        "profile_text": _ptext,
        "profile_phash": _ph,
        "feedback_text": _ftext,
        "feedback_fhash": _fh,
        "chart_key": _chart_key(result),
    }


def _build_summary_context(result, patterns):
    """构建命盘总结LLM上下文"""
    birth = result.get("基本信息", {}).get("公历", "")[:4]
    bazi = result.get("八字联合", {}).get("日主", "") + result.get("八字联合", {}).get("日主状态", "")
    pattern_names = "、".join([p.get("name", "") for p in patterns[:3]])
    laiyin = result.get("来因宫", {})
    laiyin_stars = "、".join(laiyin.get("主星", []))
    # P79: 来因宫宫名必须给出(此前只传主星且本盘主星为空,LLM把来因宫错猜成财帛宫)
    laiyin_text = f"{laiyin.get('宫名','')}宫（{laiyin_stars or '借对宫'}，{laiyin.get('辅星') and '辅星' + '、'.join(laiyin['辅星']) or '无辅星'}）"
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
    # P74: 当前+下一步大运真实数据注入(此前summary无任何大运数据,
    # LLM编造"36-45文曲化忌"等——实测文曲忌属56-65己干,当前36-45为巨门忌)
    dayun_info = ""
    try:
        import datetime as _dt4
        _ZHI4 = list("子丑寅卯辰巳午未申酉戌亥")
        _SEQ4 = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
                 "迁移", "交友", "官禄", "田宅", "福德", "父母"]
        _by4 = int(birth) if birth and birth.isdigit() else 0
        _age4 = _dt4.datetime.now().year - _by4 + 1 if _by4 else 0
        _gb4 = {}   # 宫名→地支索引
        _sn4 = {}   # 星曜→本命宫名
        for p in result.get("十二宫", []):
            b = p.get("宫位")
            b = b if isinstance(b, int) else (_ZHI4.index(b) if b in _ZHI4 else None)
            if b is not None:
                _gb4[p.get("宫名", "")] = b
            for s in (p.get("主星") or []) + (p.get("辅星") or []):
                _sn4.setdefault(s, p.get("宫名", ""))
        _picked = []
        for _i, _dy in enumerate(result.get("大运", [])):
            if _dy.get("起始年龄", 0) <= _age4 <= _dy.get("结束年龄", 999):
                _picked.append(("当前大运", _dy))
                if _i + 1 < len(result.get("大运", [])):
                    _picked.append(("下一步大运", result["大运"][_i + 1]))
                break
        _parts = []
        for _tag, _dy in _picked:
            _dyb = _gb4.get(_dy.get("大运宫名", ""))
            _sh_parts = []
            for _k, _v in (_dy.get("大运四化") or {}).items():
                if not _v:
                    continue
                _np = _sn4.get(_v, "?")
                _dp = "?"
                if _dyb is not None and _np in _gb4:
                    _dp = _SEQ4[(_dyb - _gb4[_np]) % 12]
                _sh_parts.append(f"{_k}·{_v}(本命{_np}宫/大运{_dp}宫)".replace("宫宫", "宫"))
            _stars = "、".join(_dy.get("主星", [])) or "借对宫"
            _parts.append(
                f"{_tag}:{_dy.get('起始年龄')}-{_dy.get('结束年龄')}岁{_dy.get('大运宫名','')}宫"
                f"({_dy.get('天干','?')}干,主星{_stars}),四化:{' '.join(_sh_parts) if _sh_parts else '无'}")
        dayun_info = "\n".join(_parts)
        # P78: 本命四化落宫(用户发现"权忌同宫"被错写成迁移宫——
        # ctx只有格局名无落宫,LLM只能猜;实测男命丁干天同权+巨门忌同在官禄宫)
        _nat_sh = result.get("四化", {})
        natal_sihua = " ".join([
            f"{_k}·{_v}({_sn4.get(_v, '?')}宫)"
            for _k, _v in [("化禄", _nat_sh.get("化禄")), ("化权", _nat_sh.get("化权")),
                           ("化科", _nat_sh.get("化科")), ("化忌", _nat_sh.get("化忌"))]
            if _v
        ])
    except Exception:
        dayun_info = ""
        natal_sihua = ""
    _ptext, _ph = _profile_ctx(result)  # P70
    _ftext, _fh = _feedback_ctx(result)  # P80
    return {
        "birth": birth,
        "bazi": bazi,
        "patterns": pattern_names,
        "laiyin_stars": laiyin_text,
        "sanfang": sanfang,
        "wealth": wealth,
        "ming": ming,
        "shen": shen,
        "dayun_info": dayun_info,
        "natal_sihua": natal_sihua,
        "profile_text": _ptext,
        "profile_phash": _ph,
        "feedback_text": _ftext,
        "feedback_fhash": _fh,
        "chart_key": _chart_key(result),
    }


def _build_feihua_context(result, solar_year):
    """构建三维四化LLM上下文(P59: 大白话接地气解读)"""
    import datetime as _dt2
    feihua = result.get("飞化分析", {})
    def _fmt(items):
        return " ".join([f"{it.get('四化','')}·{it.get('星曜','')}落{it.get('来源宫','')}宫" for it in items])
    age = _dt2.datetime.now().year - solar_year + 1  # 当前虚岁
    _ptext, _ph = _profile_ctx(result)  # P70
    _ftext, _fh = _feedback_ctx(result)  # P80
    return {
        "natal": _fmt(feihua.get("飞化", [])),
        "dayun": _fmt(feihua.get("大运四化", [])),
        "liunian": _fmt(feihua.get("流年四化", [])),
        "age": age,
        "profile_text": _ptext,
        "profile_phash": _ph,
        "feedback_text": _ftext,
        "feedback_fhash": _fh,
        "chart_key": _chart_key(result),
    }


def _build_monthly_context(ln, result, solar_year):
    """构建行动清单LLM上下文(P62: 每月个性化建议)"""
    year = ln.get("年份", 0)
    months = ln.get("逐月", [])[:12]
    age = year - solar_year + 1  # 该年虚岁
    _ptext, _ph = _profile_ctx(result)  # P70
    _ftext, _fh = _feedback_ctx(result)  # P80
    return {
        "year": year,
        "months": "\n".join(months),
        "age": age,
        "age_stage": _age_stage(age),
        "profile_text": _ptext,
        "profile_phash": _ph,
        "feedback_text": _ftext,
        "feedback_fhash": _fh,
        "chart_key": _chart_key(result),
    }


# ===== P80: 过三关验证(断语生成+解析+防编造) =====

# 断语类型关键词(用于统计分桶+画像穿帮剔除)
_VERIFY_TYPES = [
    ("study",    ["学业", "学历", "考试", "读书", "升学", "专业", "高考", "大学", "求学"]),
    ("career",   ["职业", "工作", "跳槽", "转行", "升职", "事业", "离职", "创业", "岗位"]),
    ("marriage", ["婚恋", "恋爱", "结婚", "婚姻", "感情", "相亲", "配偶"]),
    ("children", ["子女", "孩子", "头胎", "生育", "怀孕"]),
    ("wealth",   ["大额", "置业", "买房", "购房", "支出", "亏损", "投资", "财务", "破财", "负债"]),
    ("health",   ["健康", "伤病", "手术", "住院", "疾"]),
    ("family",   ["父母", "迁居", "搬家", "家庭", "长辈"]),
]

_12_PALACES = {"命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
               "迁移", "交友", "官禄", "田宅", "福德", "父母"}

# P81: 过三关v5应期推断数据——红鸾天喜(卯宫起子年逆数到生年支,天喜=红鸾对宫)
_HONGLUAN = {"子": "卯", "丑": "寅", "寅": "丑", "卯": "子", "辰": "亥", "巳": "戌",
             "午": "酉", "未": "申", "申": "未", "酉": "午", "戌": "巳", "亥": "辰"}
_ZHI_OPP = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
            "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}

# 流年十神(对日主)——八字应期信号:男财=妻/官杀=子女,女官杀=夫/食伤=子女,印=学业
_GAN_WX = {"甲": ("木", 1), "乙": ("木", -1), "丙": ("火", 1), "丁": ("火", -1),
           "戊": ("土", 1), "己": ("土", -1), "庚": ("金", 1), "辛": ("金", -1),
           "壬": ("水", 1), "癸": ("水", -1)}
_WX_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_WX_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def _shishen(dm: str, gan: str) -> str:
    """流年天干对日主天干的十神"""
    if dm not in _GAN_WX or gan not in _GAN_WX:
        return ""
    dwx, dyy = _GAN_WX[dm]
    gwx, gyy = _GAN_WX[gan]
    same = (dyy == gyy)
    if gwx == dwx:
        return "比肩" if same else "劫财"
    if _WX_SHENG[dwx] == gwx:
        return "食神" if same else "伤官"
    if _WX_KE[dwx] == gwx:
        return "偏财" if same else "正财"
    if _WX_KE[gwx] == dwx:
        return "七杀" if same else "正官"
    return "偏印" if same else "正印"


def _classify_claim(claim: str) -> str:
    """断语→类型分桶(stats用)"""
    for t, kws in _VERIFY_TYPES:
        if any(k in claim for k in kws):
            return t
    return "other"


def _year_signal_rows(result, birth_year: int, day_master: str = "",
                      hl_zhi: str = "", tx_zhi: str = "") -> list:
    """结构化流年应期信号(P81v6:渲染表格与parse校验共用同一份数据,杜绝两处算法漂移)。
    每年返回: {year,gan,zhi,gz,age,ln_ming,dx,ss,hltx,sihua_text,line}"""
    import datetime as _dt
    import re as _re
    ZHI = list("子丑寅卯辰巳午未申酉戌亥")
    GAN = list("甲乙丙丁戊己庚辛壬癸")
    star_palace, branch_palace, dx_list = {}, {}, []
    for p in result.get("十二宫", []):
        for s in (p.get("主星") or []) + (p.get("辅星") or []):
            star_palace.setdefault(s, p.get("宫名", ""))
        branch_palace[p.get("地支", "")] = p.get("宫名", "")
        m = _re.match(r"(\d+)-(\d+)岁", p.get("大限", "") or "")
        if m:
            dx_list.append((int(m.group(1)), int(m.group(2)),
                            f"{p.get('天干','')}{p.get('地支','')}{p.get('宫名','')}宫".replace("宫宫", "宫")))
    now_y = _dt.datetime.now().year
    if not birth_year:
        return []
    rows = []
    for y in range(birth_year + 6, now_y + 1):
        g, z = GAN[(y - 4) % 10], ZHI[(y - 4) % 12]
        age = y - birth_year + 1
        stars = _SIHUA_TABLE.get(g, ["", "", "", ""])
        parts = []
        for hi, sname in enumerate(stars):
            if sname:
                pal = star_palace.get(sname, "?")
                parts.append(f"{_SIHUA_LABELS[hi][1]}{sname}→{pal}宫".replace("宫宫", "宫"))
        # 流年命宫(年支落本命宫)——应期第一锚点(2014甲午命入子女宫=当年得子铁证)
        ln_ming = branch_palace.get(z, "")
        # 所在大限——同四化年份(2012/2022同为壬年)只能靠大限区分应事
        dx = next((d for d in dx_list if d[0] <= age <= d[1]), None)
        dx_text = dx[2] if dx else ""
        # 流年十神(对日主)——八字应期信号(2006偏印=学业/2012偏财=妻/2014七杀=子女)
        ss = _shishen(day_master, g)
        hltx = "红鸾动" if z == hl_zhi else ("天喜动" if z == tx_zhi else "")
        tags = "/".join(t for t in [f"{age}岁",
                                    f"命入{ln_ming}宫".replace("宫宫", "宫") if ln_ming else "",
                                    f"限{dx_text}" if dx_text else "",
                                    f"{ss}年" if ss else "", hltx] if t)
        rows.append({"year": y, "gan": g, "zhi": z, "gz": g + z, "age": age,
                     "ln_ming": ln_ming, "dx": dx_text, "ss": ss, "hltx": hltx,
                     "sihua_text": " ".join(parts),
                     "line": f"{y}{g}{z}({tags}):{' '.join(parts)}"})
    return rows


def _past_liunian_table(result, birth_year: int, day_master: str = "",
                        hl_zhi: str = "", tx_zhi: str = "") -> str:
    """预计算出生6岁→当前的流年应期信号表(过三关v5升级版)。
    每行: 年份干支(虚岁/流年命宫/所在大限/流年十神/红鸾天喜): 四化落本命宫位。
    背景(v4教训):只给"四化落本命宫"一个维度,LLM无法区分同四化年份(2012/2022同为壬年
    四化全同),也没有婚恋/子女/学业的事件锚点→选年纯靠蒙,实测晚2年。
    铁律(v9.31→v9.40):LLM引用年份/四化/宫位必须能直接查表,禁止其自行推算"""
    return "\n".join(r["line"] for r in
                     _year_signal_rows(result, birth_year, day_master, hl_zhi, tx_zhi))


def _build_verify_context(result, patterns):
    """P80: 构建过三关断语LLM上下文(双盘数据交叉,全部给足)"""
    import datetime as _dt
    info = result.get("基本信息", {})
    solar = info.get("公历", "")  # "1987年7月8日"
    try:
        birth_year = int(solar[:4])
    except Exception:
        birth_year = 0
    age = _dt.datetime.now().year - birth_year + 1 if birth_year else 0  # 虚岁
    # 星曜→本命宫名 / 命宫主星 / 身宫 / 地支→宫名(P81v5:红鸾天喜落宫)
    star_palace, ming_stars, shen_palace = {}, "", ""
    branch_palace = {}
    for p in result.get("十二宫", []):
        for s in (p.get("主星") or []) + (p.get("辅星") or []):
            star_palace.setdefault(s, p.get("宫名", ""))
        branch_palace[p.get("地支", "")] = p.get("宫名", "")
        if p.get("是否命宫"):
            ming_stars = "、".join((p.get("主星") or []) + (p.get("辅星") or [])) or "借对宫"
        if p.get("是否身宫"):
            shen_palace = f"{p.get('宫名','')}宫".replace("宫宫", "宫")
    # 来因宫(与summary同款,宫名必须给出)
    laiyin = result.get("来因宫", {})
    laiyin_text = (f"来因宫为{laiyin.get('宫名','')}宫"
                   f"（{'、'.join(laiyin.get('主星', [])) or '借对宫'}）").replace("宫宫", "宫")
    # 本命四化落宫
    _sh = result.get("四化", {})
    natal_sihua = " ".join([
        f"{k}·{v}落{star_palace.get(v, '?')}宫".replace("宫宫", "宫")
        for k, v in [("化禄", _sh.get("化禄")), ("化权", _sh.get("化权")),
                     ("化科", _sh.get("化科")), ("化忌", _sh.get("化忌"))] if v
    ])
    # 八字四柱+大运(需时辰;数据源自bazi_core,与八字页完全一致)
    sizhu_text, bazi_dayun_text, xiyong = "", "", ""
    day_master = ""  # P81v5: 日主天干(流年十神用)
    try:
        from . import bazi_core as _bc
        import re as _re0
        m = _re0.match(r"(\d+)年(\d+)月(\d+)日", solar)
        hour = info.get("时辰", 12)
        if m and birth_year:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            fp = _bc.get_four_pillars(y, mo, d, hour)
            day_master = fp["day"][0]
            sizhu_text = "/".join(["".join(fp["year"]), "".join(fp["month"]),
                                   "".join(fp["day"]), "".join(fp["hour"])])
            sex = info.get("性别", "男")
            _qy, dy_list = _bc.calc_dayun(sex, fp["year"][0], tuple(fp["month"]), y, mo, d)
            dy_parts = []
            for dy in dy_list[:8]:
                dy_parts.append(f"{y + dy['age_start']}-{y + dy['age_end']}年{dy['gan']}{dy['zhi']}"
                                f"({dy['age_start']}-{dy['age_end']}岁)")
            bazi_dayun_text = "；".join(dy_parts)
        bzl = result.get("八字联合", {})
        xiyong = "、".join(bzl.get("喜用神", [])) or ""
        if bzl.get("日主"):
            sizhu_text += f"，日主{bzl['日主']}{bzl.get('身强身弱', '')}"
    except Exception:
        pass
    # P81v5: 红鸾天喜(生年支起例)——婚恋应期经典锚点
    hltx_text, hl_zhi, tx_zhi = "", "", ""
    if birth_year:
        ZHI = list("子丑寅卯辰巳午未申酉戌亥")
        birth_zhi = ZHI[(birth_year - 4) % 12]
        hl_zhi = _HONGLUAN.get(birth_zhi, "")
        tx_zhi = _ZHI_OPP.get(hl_zhi, "")
        if hl_zhi:
            hltx_text = (f"红鸾在{hl_zhi}宫(本命{branch_palace.get(hl_zhi, '?')}宫)，"
                         f"天喜在{tx_zhi}宫(本命{branch_palace.get(tx_zhi, '?')}宫)"
                         f"——{hl_zhi}年红鸾动、{tx_zhi}年天喜动，婚恋喜庆应期").replace("宫宫", "宫")
    _ptext, _ph = _profile_ctx(result)
    return {
        "gen_type": "verify",
        "gender": info.get("性别", ""),
        "age": age,
        "sizhu": sizhu_text,
        "xiyong": xiyong,
        "bazi_dayun": bazi_dayun_text,
        "ming_stars": ming_stars,
        "shen_palace": shen_palace,
        "laiyin_text": laiyin_text,
        "natal_sihua": natal_sihua,
        "hltx_text": hltx_text,
        "past_liunian": _past_liunian_table(result, birth_year, day_master, hl_zhi, tx_zhi),
        "profile_text": _ptext,
        "profile_phash": _ph,
        "chart_key": _chart_key(result),
    }


def _valid_ganzhi_set(result, birth_year: int) -> set:
    """命盘真实干支全集:四柱+八字大运+流年(出生→当前+4)。
    断语/依据中出现的干支必须∈此集合(60甲子合法但非本盘数据的也算编造)"""
    import datetime as _dt
    GAN = list("甲乙丙丁戊己庚辛壬癸")
    ZHI = list("子丑寅卯辰巳午未申酉戌亥")
    valid = set()
    now_y = _dt.datetime.now().year
    if birth_year:
        for y in range(birth_year, now_y + 5):
            valid.add(GAN[(y - 4) % 10] + ZHI[(y - 4) % 12])
    for dy in result.get("大运", []):
        gan, zhi = dy.get("天干", ""), dy.get("地支", "")
        if gan and zhi:
            valid.add(f"{gan}{zhi}")
    return valid


def _day_master_of(result) -> str:
    """从命盘基本信息推日主天干(供parse校验十神引用);失败返回''"""
    try:
        from . import bazi_core as _bc
        import re as _re0
        info = result.get("基本信息", {})
        m = _re0.match(r"(\d+)年(\d+)月(\d+)日", info.get("公历", ""))
        if not m:
            return ""
        fp = _bc.get_four_pillars(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                  info.get("时辰", 12))
        return fp["day"][0]
    except Exception:
        return ""


def parse_verify(text: str, result, birth_year: int):
    """解析+防编造过滤断语。返回 [{'claim','basis','type'}...] 或 None(<5条降级)。
    三重白名单:年份范围 / 干支∈命盘真实集 / 宫位∈12宫"""
    import re as _re
    import datetime as _dt
    if not text:
        return None
    line_re = _re.compile(r"「(.+?)」\s*[｜|]\s*依据[:：]\s*(.+)")
    gz_re = _re.compile(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]")
    year_re = _re.compile(r"(19|20)(\d{2})")
    # X宫 token 提取:取分隔符前1-4字,再判断是否以12宫名结尾
    # (用"结尾匹配"而非"整体匹配"——否则"落福德宫"会被误判为非法"德宫")
    # P81v7: 宫位引用必须带信号位前缀(→/入/限/冲/落)才校验——泛化叙述词("健康宫位受冲""配偶星宫位化权")
    # 中的"X宫"不是宫位引用,旧正则任意"X宫"都校验→两处实测误杀(2007恋爱/2018手术,断语本身正确)
    palace_re = _re.compile(r"(?:→|入|限|冲|落)([^\s，。、·:：→|｜/()（）「」]{1,4})宫")
    _pal_names = sorted(_12_PALACES, key=len, reverse=True)
    valid_gz = _valid_ganzhi_set(result, birth_year)
    now_y = _dt.datetime.now().year
    # P81v6: 结构化流年信号(与prompt表格同源)——⑤c-⑤f事件类型-信号匹配校验用
    _sig_rows = {}
    if birth_year:
        _ZHI0 = list("子丑寅卯辰巳午未申酉戌亥")
        _hl0 = _HONGLUAN.get(_ZHI0[(birth_year - 4) % 12], "")
        _tx0 = _ZHI_OPP.get(_hl0, "")
        _sig_rows = {r["year"]: r for r in _year_signal_rows(
            result, birth_year, _day_master_of(result), _hl0, _tx0)}
    _gender0 = result.get("基本信息", {}).get("性别", "男")
    items = []
    for line in text.split("\n"):
        m = line_re.search(line)
        if not m:
            continue
        claim, basis = m.group(1).strip(), m.group(2).strip()
        if len(claim) < 8 or len(claim) > 80:  # P80v2: prompt限40字,80作容错上限
            continue
        ok = True
        # ① 年份白名单:断语必须断过去(出生年~当前年)
        for ym in year_re.finditer(claim + basis):
            y = int(ym.group(0))
            if birth_year and not (birth_year <= y <= now_y):
                ok = False
                break
        # ② 干支白名单:必须∈命盘真实干支集
        if ok:
            for gz in gz_re.findall(claim + basis):
                if gz not in valid_gz:
                    ok = False
                    break
        # ③ 宫位白名单(仅严格校验依据部分;断语正文允许"事业"等口语词不带"宫")
        # v7:只校验信号位(→/入/限/冲/落)后的宫位引用——泛化叙述中的"X宫"(健康宫位/配偶星宫位)不校验
        # 三判定:token以12宫名结尾(→福德宫/入父母宫) 或 token+宫本身即宫名(→命宫)
        # 或 token以"命"结尾(1987-7-17盘实测误杀:"太阳忌入命宫"→token="阳忌入命",
        # 正则以宫为分隔符,token永远不可能以"命宫"结尾——_12_PALACES中唯"命宫"带宫字,需单列)
        if ok:
            for tok in palace_re.findall(basis):
                if not (any(tok.endswith(pn) for pn in _pal_names)
                        or (tok + "宫") in _12_PALACES
                        or tok.endswith("命")):
                    ok = False
                    break
        # ④ 年龄合理性兜底(prompt v4规则7的代码强制——LLM实测会违规,曾断1990女命"19虚岁生育")
        # 婚恋/生育≥20岁, 职业/财务≥16岁, 学业限6-23岁; 取断语中最小年份(区间起点)从严判定
        if ok and birth_year:
            _ctype = _classify_claim(claim)
            _years = [int(y.group(0)) for y in year_re.finditer(claim)]
            if _years:
                _age_at = min(_years) - birth_year + 1
                if _ctype in ("marriage", "children") and _age_at < 20:
                    ok = False
                elif _ctype in ("career", "wealth") and _age_at < 16:
                    ok = False
                elif _ctype == "study" and not (6 <= _age_at <= 23):
                    ok = False
        # ④b "或"字改写(P81v7第二轮):LLM"或"字惯性难禁(实测盘1单轮5/7违规,全杀→验证区为空)。
        # 改为截取首选事件(首选是LLM的第一判断,正确性由用户验证闭环仲裁,优于整条剔除);
        # "可能/大概"仍整条剔除(纯 hedging,无首选可取)
        if ok and "或" in claim:
            claim = _re.sub(r"或[^，。、；]{1,8}", "", claim)
            if len(claim) < 8:
                ok = False
        if ok and any(w in claim for w in ("可能", "大概")):
            ok = False
        # ⑤ 化曜星曜-年份交叉校验(P81v5新增):依据中"X禄/X权/X科/X忌"的星曜必须∈该行年份四化表
        # (实测漏洞:LLM把2006丙戌的文昌科安到2008戊子头上——干支/宫位白名单查不出张冠李戴)
        _gz_m = gz_re.search(claim + basis)
        if ok:
            _all_sh_stars = {s for row in _SIHUA_TABLE.values() for s in row if s}
            if _gz_m:
                _year_sh = _SIHUA_TABLE.get(_gz_m.group(0)[0], [])
                # 本命四化对(1987-7-17盘实测误杀:LLM引"夫妻宫天同化权"=本命化权,
                # 未带"本命"前缀被当流年张冠李戴——改为按本命四化表精确豁免,不再依赖前缀)
                _natal_sh = result.get("四化", {}) or {}
                _natal_pairs = {(_natal_sh.get("化" + h, ""), h) for h in "禄权科忌"}
                for _sm in _re.finditer(r"([一-龥]{2})化?(禄|权|科|忌)", basis):
                    _star, _hua = _sm.group(1), _sm.group(2)
                    if _star not in _all_sh_stars:
                        continue  # 非四化星曜引用(如"流年化忌"),不校验
                    if basis[max(0, _sm.start() - 2):_sm.start()] in ("本命", "生年"):
                        continue  # 本命四化引用不与流年表比对
                    if (_star, _hua) in _natal_pairs:
                        continue  # 与本命四化一致的引用(LLM常省略"本命"前缀),豁免
                    _idx = "禄权科忌".index(_hua)
                    if _idx >= len(_year_sh) or _year_sh[_idx] != _star:
                        ok = False
                        break
        # ⑤b 红鸾天喜/十神-年份交叉校验(P81v5第二轮):依据中"红鸾动/天喜动/X年(十神)"必须与该年实际值一致
        # (实测漏洞:LLM在巳年依据里写"红鸾动",癸巳正财年结婚写成"红鸾动"——信号虚标)
        if ok and _gz_m and birth_year:
            _ZHI = list("子丑寅卯辰巳午未申酉戌亥")
            _hl = _HONGLUAN.get(_ZHI[(birth_year - 4) % 12], "")
            _tx = _ZHI_OPP.get(_hl, "")
            _yz = _gz_m.group(0)[1]
            if ("红鸾动" in basis and _yz != _hl) or ("天喜动" in basis and _yz != _tx):
                ok = False
        if ok and _gz_m:
            _dm = _day_master_of(result)
            if _dm:
                for _ssm in _re.finditer(r"(正财|偏财|正官|七杀|正印|偏印|食神|伤官|比肩|劫财)年", basis):
                    if _shishen(_dm, _gz_m.group(0)[0]) != _ssm.group(1):
                        ok = False
                        break
        # ⑤c-⑤f 事件类型-信号匹配校验(P81v6,第二盘4条失准的代码兜底):
        # 2017买房(该年田宅信号为零)/2023投资亏损(实为禄权入田宅的置业年)/2019剖腹产(编造分娩方式)
        if ok and _sig_rows:
            _ys0 = [int(y.group(0)) for y in year_re.finditer(claim)]
            _row0 = _sig_rows.get(min(_ys0)) if _ys0 else None
            if _row0:
                _spouse_ss = {"正财", "偏财"} if _gender0 == "男" else {"正官", "七杀"}
                _child_ss = {"正官", "七杀"} if _gender0 == "男" else {"食神", "伤官"}
                # ⑤f 分娩方式改写(剖腹产/顺产=命盘断不出的编造细节,保留断语改为"生子添丁")
                if _re.search(r"剖腹产|顺产", claim):
                    _ym2, _gzm2 = year_re.search(claim), gz_re.search(claim)
                    if _ym2 and _gzm2:
                        claim = f"{_ym2.group(0)}{_gzm2.group(0)}年生子,家中添丁"
                    else:
                        ok = False
                # ⑤c 婚恋类:该年必须占①配偶星/②禄权科入夫妻/③命入夫妻至少其一(P81v7:红鸾天喜不再算合格信号——
                # 2008戊子仅红鸾动被误断恋爱,实为2007权天同入夫妻;红鸾天喜是喜庆星,恋爱结婚添丁都可能应,只作辅助)
                # P81v8: ②收紧为[禄权科]→夫妻——忌入夫妻=感情受挫(分手/争吵),不是婚恋吉事信号
                if ok and _re.search(r"结婚|领证|订婚|相亲|恋爱|拍拖|分手|离婚|再婚", claim):
                    if not (_row0["ss"] in _spouse_ss or "夫妻" in _row0["ln_ming"]
                            or _re.search(r"[禄权科][^ ]*→夫妻", _row0["sihua_text"])):
                        ok = False
                # ⑤c2 子女类:该年必须至少占1个子女信号(子女星/命入子女/四化入子女/红鸾天喜动)
                if ok and _re.search(r"生子|添丁|怀孕|生育|得子|得女|二胎", claim):
                    if not (_row0["ss"] in _child_ss or "子女" in _row0["ln_ming"]
                            or "→子女" in _row0["sihua_text"] or _row0["hltx"]):
                        ok = False
                # ⑤d 置业迁居类(P81v9收紧):合格信号仅"权/忌→田宅"或"禄→田宅+限田宅双锚"——
                # 命入田宅只是位置不是动作、化科=文书名声太轻、单化禄=财物之缘非变动动作
                # (实测:2008戊子禄贪狼→田宅+命入田宅+红鸾动被误断搬家,命主22岁大学在读并无搬家;
                # 两盘6个真实置业年全是权/忌→田宅或禄→田宅+限田宅双锚)
                if ok and _re.search(r"买房|购房|置业|卖房|装修|搬家|迁居|乔迁", claim):
                    if not (_re.search(r"[权忌][^ ]*→田宅", _row0["sihua_text"])
                            or (_re.search(r"禄[^ ]*→田宅", _row0["sihua_text"])
                                and "田宅" in _row0["dx"])):
                        ok = False
                # ⑤e 亏损类:该年必须有"化忌入财帛/兄弟"(禄权入田宅的置业年严禁断亏损)
                if ok and _re.search(r"亏损|破财|赔钱|投资失利|亏本|被坑|被骗", claim):
                    if not _re.search(r"忌[^ ]*→(财帛|兄弟)", _row0["sihua_text"]):
                        ok = False
                # ⑤g 手术住院类(P81v8):仅限"化忌→疾厄"——命入疾厄每12年一轮太泛
                # (实测:2019己亥仅命入疾厄被误断手术,命主并无手术住院)
                if ok and _re.search(r"手术|住院|大病|重病|开刀", claim):
                    if not _re.search(r"忌[^ ]*→疾厄", _row0["sihua_text"]):
                        ok = False
                # ⑤h 职业类年龄下限(P81v8):≤20岁(大学在读期)严禁跳槽/升职类断语
                # (实测:2006丙戌命入迁移被误断"跳槽",命主当年20岁实为升大学)
                if ok and birth_year:
                    _age0 = min(_ys0) - birth_year + 1
                    if _age0 <= 20 and _re.search(
                            r"跳槽|升职|创业|调岗|外派|离职|加薪|晋升|上任|换工作|入职", claim):
                        ok = False
        if ok:
            items.append({"claim": claim, "basis": basis,
                          "type": _classify_claim(claim)})
    return items[:8] if len(items) >= 5 else None


def _llm_generate(gen_type: str, ctx: dict) -> str | None:
    """通用LLM生成器: liunian/dayun/summary，失败返回None回退模板"""

    if gen_type == "liunian":
        prompt = f"""你是资深紫微斗数命理师。分析{ctx.get("ln_gz","")}年。

【必须使用以下命盘数据,编造宫位将导致分析完全错误】
化曜落宫: {ctx.get("ln_palace_sihua","")}  太岁: {ctx.get("ln_taisui","")}
命宫庙旺: {ctx.get("ln_star_mw","")}  特征: {ctx.get("era_info","")}
命主该年{ctx.get("ln_age","")}岁(虚岁),处于:{ctx.get("age_stage","")}{ctx.get("profile_text","")}

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
命主在此大运处于:{stage}{ctx.get('profile_text','')}
要求:
1. 输出7个维度:财富、事业、婚姻、子女、父母、健康、大运整体结论
2. 前6维每维严格控制在80字以内,必须结合大运四化(化禄/化权/化科/化忌)分析其对该维度的具体影响
3. 【落宫关联-最高优先级】大运四化数据已标注每颗化曜的落宫(本命宫/大运盘宫)。引用某四化分析某维度前,必须先判断其落宫与该维度宫位(财富=财帛,事业=官禄,婚姻=夫妻,子女=子女,父母=父母,健康=疾厄)的关系:只有落入该宫、或与该宫三合/对照时才能引用;落宫与维度无关时严禁强行关联(例如化科落父母宫,绝不可写成"化科利婚姻";化忌落子女宫绝不可写成"化忌冲事业")
4. 大运整体结论150字左右,详细分析这十年的整体走势、关键策略与人生建议
5. 【重要】所有内容必须符合命主该年龄段的实际生活场景,例如对3-12岁儿童只能谈学业兴趣家庭,严禁谈婚姻职场投资;对60岁以上老人不谈跳槽晋升
6. 格式:每维独立一段,开头用 **【维度名 分数】** 标记,例如 **【财富 57分】** 然后换行写内容
7. 口语务实,直接输出,不要多余开场白。"""

    elif gen_type == "dayun_brief":
        sc = ctx.get('scores','')
        prompt = f"""资深命理师。请分析这大运,输出1段约350字综合点评(包含7维):
{ctx.get('dayun_age','')}岁{ctx.get('dayun_gong','')}宫{ctx.get('dayun_score','')}分。生于{ctx.get('birth','')}年{ctx.get('bazi','')[:50]}。维度:{sc}。{ctx.get('profile_text','')}
7维(财富/事业/婚姻/子女/父母/健康/整体结论)各40-50字。
口语务实,直接输出。"""

    elif gen_type == "feihua":
        prompt = f"""你是说话接地气的资深命理师,像朋友聊天一样解读四化飞星,说人话。
命主{ctx.get('age','')}岁。{ctx.get('profile_text','')}
三组四化数据:
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
命主该年{ctx.get('age','')}岁(虚岁),处于:{ctx.get('age_stage','')}{ctx.get('profile_text','')}
每月运势数据(月份：宫位(星曜) 四化 — 主题):
{ctx.get('months','')}

要求:
1. 输出12条,格式严格为"正月：建议内容",月份必须与输入逐月对应
2. 每条25-35字,结合该月宫位主题+星曜特质+四化吉凶(如有),给出可立即执行的具体行动
3. 联系命主{ctx.get('age','')}岁的真实生活(职场/家庭/财务/健康/孩子),说人话
4. 严禁空话套话("顺势而为""把握机遇""注意身体""宜社交活动"等),要具体到事(如"把年假排在这个月带爸妈做全身体检""这个月别签任何合同,重要谈判推到下月")
5. 直接输出12条,不要开场白不要总结。"""

    elif gen_type == "summary":
        prompt = f"""你是资深命理分析师。请为以下命盘写全局总结。

生于{ctx.get('birth','')}，{ctx.get('bazi','')}，格局：{ctx.get('patterns','')}，来因宫：{ctx.get('laiyin_stars','')}，三方四正：{ctx.get('sanfang','')}，财富级别：{ctx.get('wealth','')}。命宫{ctx.get('ming','')}，身宫{ctx.get('shen','')}。{ctx.get('profile_text','')}
（来因宫宫位已明确给出,必须逐字使用,严禁改为其他宫位——曾有模型把夫妻宫的来因宫错写成财帛宫）

【本命四化落宫-最高优先级,严禁写错宫位】
{ctx.get('natal_sihua','')}
凡提及化禄/化权/化科/化忌(含"权忌同宫""禄忌交战"等组合)的所在宫位,必须逐字使用以上落宫数据,严禁凭格局名推测宫位(曾有模型把官禄宫的权忌同宫错写成迁移宫)。

【大运数据-最高优先级,严禁编造】
{ctx.get('dayun_info','')}
凡涉及大运/大限的内容(年龄段、宫位、干支、四化、主星),必须逐字使用以上数据,严禁凭记忆或推测写任何大运信息(曾有模型把当前的巨门忌错写成其他大运的文曲忌)。

从来因宫出发：①此生核心课题与天赋赛道 ②三方四正联动看一生转折点 ③结合上方大运数据谈当前与下一步大运的关键策略 ④中晚年生活形态建议。结合时代背景给出务实参考，语气专业有温度。

【篇幅硬约束】全文严格控制在1100-1400字(每部分250-350字),四个部分必须全部写完并完整收尾——宁可每部分写得精炼,也绝不许写到一半中断(上一版曾在半句话处截断)。直接输出。"""
    elif gen_type == "verify":
        # P80: 过三关断语生成。铁律:年份/干支/宫位数据全部给足,LLM只负责"断",不负责"算"
        prompt = f"""你是盲派命理师,先做"过三关":根据命盘断7条命主【已经发生过】的具体事情,供命主验证准确度。

【命主】{ctx.get('gender','')}，现年{ctx.get('age','')}岁(虚岁){ctx.get('profile_text','')}
(画像中已告知的信息是事实前提,直接采用,严禁再作为断语提问——如已知已婚,不得再断"你可能已婚",只能断"结婚年份")

【八字四柱】{ctx.get('sizhu','')}，喜用神：{ctx.get('xiyong','')}
【八字大运】{ctx.get('bazi_dayun','')}
【紫微】命宫{ctx.get('ming_stars','')}，身宫{ctx.get('shen_palace','')}，{ctx.get('laiyin_text','')}
【本命四化】{ctx.get('natal_sihua','')}
【红鸾天喜】{ctx.get('hltx_text','')}
【历年应期信号表(断语年份锚点,只允许引用下表数据)】
{ctx.get('past_liunian','')}
(每行格式: 年份干支(虚岁/流年命宫/所在大限/流年十神/红鸾天喜): 四化落本命宫位)

【应期规则-信号分权重,严禁只看四化选年】
- 婚恋(恋爱/结婚/领证/订婚): 权重①配偶星年(男命正财/偏财年、女命正官/七杀年) ②流年化禄/化权/化科入夫妻宫 ③流年命入夫妻宫 ④红鸾天喜动(仅辅助加分)。⚠️①②③全无的年份,即使红鸾/天喜动也严禁断任何婚恋事件(含恋爱)——红鸾天喜是"喜庆星",婚恋/添丁/庆典都可能应,不是婚恋专属铁证(实测教训:2014仅有天喜动被误断结婚,实为添丁;2008仅有红鸾动被误断恋爱,真正的恋爱年2007=化权天同入夫妻宫;真正的结婚年2012=正官年+化禄入夫妻宫)
- 子女(怀孕/生育): 权重①子女星年(男命正官/七杀年、女命食神/伤官年) ②流年命入子女宫或四化入子女宫 ③红鸾天喜动(添丁亦主喜庆)。生育断语年份必须晚于结婚断语年份(不主动断未婚先孕)
- 学业考试: 正印/偏印年; 化科(文昌/文曲化科分量最重)
- 置业迁居(买房/卖房/搬家/迁居/装修): 只允许在①"化权/化忌入田宅宫"或②"化禄入田宅宫且同年所在大限为田宅宫(双锚)"的年份下断。⚠️单化科入田宅分量太轻(科=文书名声,不是重资产动作),严禁据"科入田宅"断买房搬家——即使同年命入田宅也不算(实测教训:2015乙未命入田宅+紫微化科入田宅被误断买房,命主该年并未置业)。⚠️单化禄入田宅同样不够——禄=财物之缘,权/忌才是变动落实的动作四化;命入田宅+红鸾动也救不回来(实测教训:2008戊子禄贪狼→田宅+命入田宅+红鸾动被误断搬家,命主22岁大学在读并无搬家;两盘6个真实置业年全是权/忌→田宅或禄→田宅+限田宅双锚:2012权→田宅/2019忌→田宅/2023禄→田宅+限田宅)。⚠️迁移宫化忌=在外奔波受挫,严禁据此断搬家(实测教训:2005乙酉太阴化忌入迁移被误断搬家,命主该年并未搬家)
- 事业变动: 正官/七杀/正偏财年; 化禄/化权入官禄宫; 流年命入官禄宫。⚠️22岁及以前(大学在读期)严禁断跳槽/升职/创业/调岗——该年龄段命入迁移/官禄/化禄引动只能断学业事件(升学/高考/考研/转学/毕业/留学)(实测教训:2006丙戌命入迁移被误断"跳槽",命主当年20岁实为升大学)
- 健康伤病: 手术/住院/大病仅限"化忌入疾厄宫"的年份下断——流年命入疾厄每12年一轮太泛,单命入疾厄严禁断手术住院(实测教训:2019己亥仅命入疾厄被误断手术,命主该年并无手术住院;当年忌文曲→田宅,真实发生的是买房)
- 财务负面(亏损/破财/投资失利): 只允许在"化忌入财帛宫或兄弟宫"的年份下断。⚠️若该年有化禄/化权入田宅宫或命入田宅宫,财务事件只能断"买房/置业/大额支出(如贷款买房)",严禁断亏损——破军化禄/化权入田宅=置业(含贷款)大喜,绝不是破财(实测教训:2023禄破军→田宅+权巨门→财帛被误断"投资亏损",实为贷款买房)
- 财务正面(得财/进财/偏财): 女命太阳=夫星——太阳化禄/化权入命宫/财帛宫的年份得财,优先断"得偏财/进财(丈夫带来或丈夫事业进财)",比断本人投资更准(实测:2020庚子太阳化禄入命+命入财帛,命主当年得的偏财正是来自丈夫)
⚠️ 天干相同的年份四化完全相同(如2012与2022同为壬年),必须用流年命宫/大限/十神区分,只凭四化选年必错;同天干候选年之间,必须选有所在大限或流年命宫信号加持的那个(实测教训:2013与2023同为癸年破军化禄入田宅,2013大限在福德宫零加持被误断买房,实为2023限入田宅大限贷款买房)
⚠️ 写每条断语前,先按上方应期规则筛出该类事件信号最强的2-3个候选年,按权重①>②>③>④比较后只选信号最重的1个下断——不要拿到第一个有信号的年份就写(例:某年仅有天喜动、另一年是配偶星年+化禄入夫妻宫,必须选后者)

要求:
1. 7条断语必须全部是【过去已发生】的事,严禁断未来、严禁性格描述
2. 【具体化硬约束-本版核心】每条必须断一个"具体事件",事件动作必须具象(跳槽/升职/加薪/离职/创业/调岗/外派/买房/卖房/装修/搬家/结婚/领证/订婚/恋爱/分手/离婚/生子/怀孕/手术/住院/受伤/体检异常/考研/考公/留学/转学/考试失利/投资/炒股/亏损/借钱/买车/大额消费/官司/签约/父母住院/父母手术)。
   严禁笼统词:变动/调整/困扰/波动/影响/压力/不顺/考验/损耗/操心/之事——这类词放之四海皆准,命主无法判定,等于废话。
   【具象化边界】生育只断"生子/添丁/怀孕",严禁断分娩方式(顺产/剖腹产)——分娩方式命盘断不出来,属于编造细节(实测教训:断"剖腹产一子",命主实为顺产);手术/住院/受伤类仅允许在化忌入疾厄宫或命入疾厄宫的年份下断
3. 【禁止"或"字-零容忍】断语正文出现"或""可能""大概"任何一个词,该条就是废品,必须重写为单一确定事件——每条只断一件事,拿不准就整条换一条有把握的,绝不用"或"来兜底
4. 【四化混用】至少3条必须用化禄/化权/化科作依据(断具体好事:升职/置业/结婚/得财/生子/升学),严禁7条全是化忌——全断坏事是"笼统猜大概率",不是真功夫
5. 【类型分散-强制】同一类型最多2条,7条必须覆盖≥4类(学业/职业/婚恋/子女/财务/健康/家庭迁居),且必须包含至少1条婚恋或家庭或健康类——严禁4条以上都是事业类(只盯官禄宫是偷懒)
6. 每条必须具体到公历年份(如"2016丙申年"),单年拿不准可给两年区间(如"2016-2017年")
7. 【年龄合理性硬约束】写每条之前先算年龄(虚岁=年份-出生年+1):婚恋/生育类必须≥20岁,职业/财务类必须≥16岁,学业类限6-23岁,父母事件不限年龄。年龄不合理的年份直接换年份,严禁出现"14岁结婚"式笑话
8. 【篇幅硬约束】断语正文≤40字且只断一件事(严禁"晋升+健康损耗"式复合断语,命主无法判定);依据≤25字,只写最关键的1-2个数据点(如"丙申年廉贞忌→夫妻宫"),严禁长篇论证——token预算内必须完整写完7行
9. 每条严格用一行格式: 「断语内容」｜依据:干支/四化/宫位
10. 引用的年份、干支、四化落宫、十神、流年命宫必须逐字来自该年那一行,严禁跨行拼凑(曾把2006丙戌行的文昌科安到2008戊子年头上——张冠李戴即编造);依据里优先写该行的触发信号(如"命入子女宫""七杀年""天喜动")+1个四化落宫
11. 断语要有区分度,严禁放之四海皆准的废话(如"你经历过挫折""你人缘不错")

【坏断语-笼统,严禁模仿】
「2020庚子年工作有变动」(错:"有变动"无法判定,必须说清跳槽/升职/离职哪一件)
「2024甲辰年家庭方面有困扰」(错:"困扰"是万能废话,必须说清搬家/装修/父母健康哪一件)
「2019己亥年买房或大额置业」(错:严禁"或"字,只断一件)
「2008戊子年恋爱,感情开始」(该年仅红鸾动,化权太阴入迁移宫而非夫妻宫;2007丁亥年化权天同入夫妻宫信号更重)(错:恋爱同属婚恋类,单凭红鸾天喜严禁下断)
「2013癸巳年买房置业」(与2023癸卯同为癸年、破军化禄入田宅完全相同,但2023限入田宅大限信号更重)(错:同天干年必须选有大限/命宫加持的年份)
「2015乙未年买房置业」(该年命入田宅+紫微化科入田宅,但无禄/权/忌入田宅)(错:化科=文书名声分量太轻,命入田宅只是位置不是动作,置业必须禄/权/忌入田宅或限入田宅大限)
「2008戊子年搬家迁居」(该年禄贪狼→田宅+命入田宅+红鸾动,但无化权/化忌入田宅、大限也不在田宅宫)(错:单化禄入田宅只是财物之缘不是变动动作,置业搬家必须权/忌入田宅或禄入田宅+限田宅双锚)
「2006丙戌年跳槽」(命主当年20岁还在读大学)(错:22岁前变动信号只能断升学/学业事件,严禁断跳槽)
「2019己亥年手术」(该年仅命入疾厄,无化忌入疾厄)(错:命入疾厄每12年一轮太泛,手术住院仅限化忌入疾厄年;该年忌文曲→田宅,真实发生的是买房)
「2019己亥年剖腹产一子」(错:严禁断分娩方式,只能断"生子添丁")
「2023癸卯年投资亏损破财」(若该年化禄入田宅宫)(错:禄入田宅=置业大喜,只能断买房/大额支出,严禁断亏损)
【好断语-具体,照此风格】
「2016丙申年跳槽换了工作」
「2019己亥年买房,有置业大额支出」
「2013癸巳年升职,职位上了一个台阶」
直接输出7行,不要开场白。"""
        # P81v6: 重试警告(首轮断语被parse判废后由/verify端点注入,二轮重写)
        prompt += ctx.get("retry_note", "") or ""

    else:
        return None

    # P80: 验证反馈注入(verify自身不注入——它是反馈的来源,注入会污染断语)
    if gen_type != "verify":
        prompt += ctx.get("feedback_text", "") or ""

    # 缓存key：简洁格式,gen_type+年龄+画像hash+反馈hash
    # (P70:画像不同内容不同,必须入key; P80:反馈不同内容不同,同样必须入key→v33)
    import time as _t
    try:
        age = ctx.get('dayun_age', ctx.get('ln_gz', ''))
        # P81: verify的prompt v9(置业再收紧:单化禄→田宅不算动作信号,须权/忌→田宅或禄→田宅+限田宅双锚
        # ——实测2008戊子禄贪狼→田宅+命入田宅+红鸾被误断搬家,命主22岁大学在读并无搬家;
        # v8=置业信号收紧为禄权忌→田宅/限田宅,命入田宅+化科不算;职业类≤20岁禁断;
        # 手术住院仅限忌→疾厄;忌入夫妻不算婚恋吉信号;女命太阳=夫星得财优先断丈夫带来;
        # v7=⑤c红鸾天喜降为纯辅助+同天干年必须选大限/命宫加持年;v6=信号权重排序+置业/亏损/分娩方式纠偏)
        # →独立递增,不影响其他gen_type缓存
        _ck_ver = "v42" if gen_type == "verify" else "v33"
        ck = f"zw:{gen_type}:{_stable_hash(str(age))}:{ctx.get('chart_key','')}:{ctx.get('profile_phash','noprof')}:{ctx.get('feedback_fhash','nofb')}:{_ck_ver}"
        if ctx.get("retry_note"):
            ck += ":r1"  # P81v6: 重试轮独立缓存key,不与首轮互相污染
    except:
        ck = f"zw:{gen_type}:{int(_t.time())}"
    # P56: 保持800（用户要求，不能减少）
    # P76: summary例外——v9.34注入大运数据后总结变多章节,800token写不下截断半句;
    # 提1200后LLM按比例写更满(1786字)仍截断 → 1500+prompt限幅1100-1400字双保险
    max_tok = 1500 if gen_type == "summary" else (1200 if gen_type == "verify" else 800)
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
