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
                      hl_zhi: str = "", tx_zhi: str = "", end_year: int = 0) -> list:
    """结构化流年应期信号(P81v6:渲染表格与parse校验共用同一份数据,杜绝两处算法漂移)。
    每年返回: {year,gan,zhi,gz,age,ln_ming,dx,ss,hltx,sihua_text,line}
    end_year(family用): >0时表格延伸到该年(未来预测锚点);默认0=到当前年为止"""
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
                            f"{p.get('天干','')}{p.get('地支','')}{p.get('宫名','')}宫".replace("宫宫", "宫"),
                            p.get("天干", "")))
    now_y = _dt.datetime.now().year
    if not birth_year:
        return []
    _end_y = max(now_y, end_year) if end_year else now_y
    rows = []
    for y in range(birth_year + 6, _end_y + 1):
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
        # v13: 大限干四化(禄/忌)——岁限双忌=大事应期决定性叠加(盘1父亡2026=丙午限+丙午年双廉贞忌入父母宫)
        dx_sihua, double_ji = "", False
        if dx and dx[3]:
            dstars = _SIHUA_TABLE.get(dx[3], ["", "", "", ""])
            dparts = []
            for hi2 in (0, 3):  # 只取大限禄/忌(权科噪音大,先不上)
                sname2 = dstars[hi2]
                if sname2:
                    pal2 = star_palace.get(sname2, "?")
                    dparts.append(f"限{_SIHUA_LABELS[hi2][1]}{sname2}→{pal2}宫".replace("宫宫", "宫"))
            dx_sihua = " ".join(dparts)
            if dstars[3] and stars[3] and \
                    star_palace.get(dstars[3], "") == star_palace.get(stars[3], "?"):
                double_ji = True
        # 流年十神(对日主)——八字应期信号(2006偏印=学业/2012偏财=妻/2014七杀=子女)
        ss = _shishen(day_master, g)
        hltx = "红鸾动" if z == hl_zhi else ("天喜动" if z == tx_zhi else "")
        tags = "/".join(t for t in [f"{age}岁",
                                    f"命入{ln_ming}宫".replace("宫宫", "宫") if ln_ming else "",
                                    f"限{dx_text}" if dx_text else "",
                                    f"{ss}年" if ss else "", hltx,
                                    "⚠岁限双忌" if double_ji else ""] if t)
        rows.append({"year": y, "gan": g, "zhi": z, "gz": g + z, "age": age,
                     "ln_ming": ln_ming, "dx": dx_text, "ss": ss, "hltx": hltx,
                     "sihua_text": " ".join(parts),
                     "dx_sihua": dx_sihua, "double_ji": double_ji,
                     "line": f"{y}{g}{z}({tags}):{' '.join(parts)}"
                             + (f" |{dx_sihua}" if dx_sihua else "")})
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


def _eligible_years_text(result, birth_year: int, day_master: str = "",
                         hl_zhi: str = "", tx_zhi: str = "", gender: str = "男") -> str:
    """P82v18(C方案): 候选年预筛——按事件类型用parse闸门同款规则逐年判定合格年,
    写进prompt作为LLM选年的唯一范围(选年数据化,LLM只断不算)。
    背景(盘3 12轮全灭):LLM选年被prompt示例年(其他盘案例)锚定,反锚定警告+具体化重试
    均压不住;同干支年四化相同,LLM分不清"示例结构"与"本盘数据"。
    规则必须与parse_verify的⑤c/⑤c2/⑤d/⑤e/⑤g/⑤j/⑤l/⑤o/⑤p保持完全一致——
    清单是引导,parse闸门仍全量兜底"""
    import re as _re
    if not birth_year:
        return ""
    rows = _year_signal_rows(result, birth_year, day_master, hl_zhi, tx_zhi)
    spouse_ss = {"正财", "偏财"} if gender == "男" else {"正官", "七杀"}
    child_ss = {"正官", "七杀"} if gender == "男" else {"食神", "伤官"}
    cats = {k: [] for k in ("升学", "学业节点", "恋爱", "结婚", "添丁",
                            "置业", "职业变动", "得财", "亏损", "手术住院", "家庭大事")}

    for r in rows:
        y, age = r["year"], r["age"]
        ss, ln, sh = r["ss"], r["ln_ming"], r["sihua_text"]
        dx, dxsh, hltx = r["dx"], r["dx_sihua"], r["hltx"]
        tag = f"{y}{r['gz']}({age}岁)"
        ke_changqu = _re.search(r"科(文昌|文曲)→", sh)
        # 升学(考入大学/本科): ⑤o双信号=印年+文昌/文曲化科, 17-23岁窗口
        if 16 <= age <= 23 and ss in ("正印", "偏印") and ke_changqu:
            cats["升学"].append(f"{tag}{ss}+{ke_changqu.group(0).rstrip('→')}化科")
        # 学业节点(考研/考公/毕业/转学/考证): ⑤l=化科入命/官禄/父母 或 昌曲化科
        elif 6 <= age <= 30 and (_re.search(r"科[^ ]*→(命宫|官禄宫|父母宫)", sh) or ke_changqu):
            anchor = ke_changqu.group(0).rstrip("→") + "化科" if ke_changqu else "化科入命/官禄/父母"
            cats["学业节点"].append(f"{tag}{anchor}")
        # 恋爱: ⑤c=配偶星年/[禄权科]→夫妻/命入夫妻, ≥20岁
        if age >= 20 and (ss in spouse_ss or "夫妻" in ln
                          or _re.search(r"[禄权科][^ ]*→夫妻", sh)):
            why = "配偶星年" if ss in spouse_ss else ("命入夫妻" if "夫妻" in ln else "化曜入夫妻")
            cats["恋爱"].append(f"{tag}{why}")
        # 结婚/领证: ⑤p双锚=配偶星年+大限加持夫妻宫(限入夫妻 或 限禄/限权→夫妻)
        if age >= 20 and ss in spouse_ss and (
                "夫妻" in dx or _re.search(r"限[禄权][^ ]*→夫妻", dxsh)):
            cats["结婚"].append(f"{tag}{ss}年+大限加持夫妻")
        # 添丁: ⑤c2=子女星/命入子女/→子女/红鸾天喜(无夫妻化曜时)
        if age >= 20:
            child_sig = ss in child_ss or "子女" in ln or "→子女" in sh
            if child_sig or (hltx and not _re.search(r"[禄权科][^ ]*→夫妻", sh)):
                why = ("子女星年" if ss in child_ss else
                       "命入子女" if "子女" in ln else
                       "化曜入子女" if "→子女" in sh else hltx)
                cats["添丁"].append(f"{tag}{why}")
        # 置业: ⑤d=权/忌→田宅 或 禄→田宅+限田宅
        if _re.search(r"[权忌][^ ]*→田宅", sh):
            cats["置业"].append(f"{tag}化权/忌入田宅")
        elif _re.search(r"禄[^ ]*→田宅", sh) and "田宅" in dx:
            cats["置业"].append(f"{tag}禄入田宅+限田宅")
        # 职业变动(跳槽/升职): >20岁, 命入官禄或化曜入官禄(忌入官禄=受挫变动)
        if age > 20 and ("官禄" in ln or _re.search(r"[禄权科忌][^ ]*→官禄", sh)):
            why = "命入官禄" if "官禄" in ln else "化曜入官禄"
            cats["职业变动"].append(f"{tag}{why}")
        # 得财: 禄→命/财帛 或 命入财帛
        if age >= 16 and (_re.search(r"禄[^ ]*→(命宫|财帛宫)", sh) or "财帛" in ln):
            cats["得财"].append(tag)
        # 亏损: ⑤e=忌→财帛/兄弟
        if _re.search(r"忌[^ ]*→(财帛|兄弟)", sh):
            cats["亏损"].append(tag)
        # 手术住院: ⑤g=忌→疾厄
        if _re.search(r"忌[^ ]*→疾厄", sh):
            cats["手术住院"].append(tag)
        # 家庭大事: 岁限双忌
        if r["double_ji"]:
            cats["家庭大事"].append(f"{tag}⚠岁限双忌")

    lines = []
    for k in ("升学", "学业节点", "恋爱", "结婚", "添丁", "置业",
              "职业变动", "得财", "亏损", "手术住院", "家庭大事"):
        v = cats[k]
        lines.append(f"- {k}: " + (" / ".join(v) if v else f"无合格年(严禁断{k}类事件)"))
    return "\n".join(lines)


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
        "eligible_text": _eligible_years_text(result, birth_year, day_master,
                                              hl_zhi, tx_zhi, info.get("性别", "男")),
        "profile_text": _ptext,
        "profile_phash": _ph,
        "chart_key": _chart_key(result),
    }


def _build_family_context(result, patterns):
    """P82: 家庭分析LLM上下文(父母画像/父财/父母健康/手足)。
    取象规则来自盘3(1989-7-2辰时女:眼疾/夜场/流产三案例)与盘4(2014-1-19辰时男:
    父母画像/父财台阶/手足妹妹2022/健康取象双锚点确认)人工推演验证,全部数据给足,
    LLM只断不算——严禁其自行排盘或推算宫位。"""
    import datetime as _dt
    info = result.get("基本信息", {})
    solar = info.get("公历", "")
    try:
        birth_year = int(solar[:4])
    except Exception:
        birth_year = 0
    age = _dt.datetime.now().year - birth_year + 1 if birth_year else 0

    star_palace, branch_palace, pal_by_name, dx_list = {}, {}, {}, []
    ZHI = list("子丑寅卯辰巳午未申酉戌亥")
    import re as _re
    for p in result.get("十二宫", []):
        for s in (p.get("主星") or []) + (p.get("辅星") or []):
            star_palace.setdefault(s, p.get("宫名", ""))
        branch_palace[p.get("地支", "")] = p.get("宫名", "")
        pal_by_name[p.get("宫名", "")] = p
        m = _re.match(r"(\d+)-(\d+)岁", p.get("大限", "") or "")
        if m:
            dx_list.append((int(m.group(1)), int(m.group(2)),
                            p.get("天干", ""), p.get("地支", ""), p.get("宫名", "")))

    def _fmt_palace(p):
        """宫位数据行:宫名(干支): 主星(庙旺)、辅星 小星:..."""
        if not p:
            return "(无此宫数据)"
        mwd = p.get("庙旺", {}) or {}
        parts = []
        for s in (p.get("主星") or []) + (p.get("辅星") or []):
            lab = mwd.get(s, "")
            parts.append(f"{s}({lab})" if lab else s)
        minor = (p.get("小星") or [])[:6]
        txt = (f"{p.get('宫名','')}宫({p.get('天干','')}{p.get('地支','')}): "
               f"{'、'.join(parts) or '无主星(借对宫)'}").replace("宫宫", "宫")
        if minor:
            txt += f" 小星:{'、'.join(minor)}"
        return txt

    def _sihua_of_gan(gan):
        """某天干四化→落本命宫文本(化禄/化权/化科/化忌全称,LLM需区分吉凶)"""
        stars = _SIHUA_TABLE.get(gan, ["", "", "", ""])
        out = []
        for hi, sname in enumerate(stars):
            if sname:
                pal = star_palace.get(sname, "?")
                out.append(f"{_SIHUA_LABELS[hi]}{sname}→{pal}宫".replace("宫宫", "宫"))
        return " ".join(out)

    parent_p = pal_by_name.get("父母", {})
    bro_p = pal_by_name.get("兄弟", {})
    prop_p = pal_by_name.get("田宅", {})
    health_p = pal_by_name.get("疾厄", {})
    ming_p = next((p for p in result.get("十二宫", []) if p.get("是否命宫")), {})

    # 父母宫干四化(宫位飞化:父母宫天干飞出的四化=父母带来的缘)
    parent_gan = parent_p.get("天干", "")
    parent_sihua = _sihua_of_gan(parent_gan) if parent_gan else ""

    # 父之财帛位(父母宫立太极)——环向从命盘自身数据推导(命→财帛的支距),不硬编码方向
    father_wealth_text = ""
    ming_zhi, caibo_zhi = ming_p.get("地支", ""), pal_by_name.get("财帛", {}).get("地支", "")
    parent_zhi = parent_p.get("地支", "")
    if ming_zhi and caibo_zhi and parent_zhi:
        off = (ZHI.index(ming_zhi) - ZHI.index(caibo_zhi)) % 12  # 命→财帛的环向支距(=4)
        fw_zhi = ZHI[(ZHI.index(parent_zhi) - off) % 12]
        fw_name = branch_palace.get(fw_zhi, "")
        fw_p = pal_by_name.get(fw_name, {})
        if fw_p:
            father_wealth_text = (f"父之财帛位=本命{fw_name}宫({fw_zhi}) "
                                  + _fmt_palace(fw_p)).replace("宫宫", "宫")

    # 太阳(父星)/太阴(母星)落宫+庙旺+同宫煞星
    def _star_line(star):
        pal = star_palace.get(star, "")
        p = pal_by_name.get(pal, {})
        if not p:
            return f"{star}: (盘中无此星)"
        mwd = (p.get("庙旺", {}) or {}).get(star, "")
        co = [s for s in (p.get("主星") or []) + (p.get("辅星") or []) if s != star]
        return (f"{star}落{pal}宫({p.get('地支','')})" +
                (f"({mwd})" if mwd else "") +
                (f" 同宫:{'、'.join(co)}" if co else "")).replace("宫宫", "宫")

    # 大限干四化(禄/权/忌落宫)——十年气候(盘4父财:限武曲禄灌父之财帛=最厚积累期)
    dx_lines = []
    for dx in sorted(dx_list, key=lambda d: d[0]):
        stars = _SIHUA_TABLE.get(dx[2], ["", "", "", ""])
        parts = []
        for hi in (0, 1, 3):  # 禄/权/忌
            if stars[hi]:
                pal = star_palace.get(stars[hi], "?")
                parts.append(f"限{_SIHUA_LABELS[hi][1]}{stars[hi]}→{pal}宫".replace("宫宫", "宫"))
        dx_lines.append(f"{dx[0]}-{dx[1]}岁 {dx[2]}{dx[3]}限(本命{dx[4]}宫): "
                        f"{' '.join(parts)}".replace("宫宫", "宫"))

    # 八字四柱+大运(偏财=父星/正印=母星/比劫=手足 旁证)
    sizhu_text, bazi_dayun_text, day_master = "", "", ""
    try:
        from . import bazi_core as _bc
        m = _re.match(r"(\d+)年(\d+)月(\d+)日", solar)
        hour = info.get("时辰", 12)
        if m and birth_year:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            fp = _bc.get_four_pillars(y, mo, d, hour)
            day_master = fp["day"][0]
            sizhu_text = "/".join(["".join(fp["year"]), "".join(fp["month"]),
                                   "".join(fp["day"]), "".join(fp["hour"])])
            sex = info.get("性别", "男")
            _qy, dy_list = _bc.calc_dayun(sex, fp["year"][0], tuple(fp["month"]), y, mo, d)
            bazi_dayun_text = "；".join(
                f"{y + dy['age_start']}-{y + dy['age_end']}年{dy['gan']}{dy['zhi']}"
                f"({dy['age_start']}-{dy['age_end']}岁)" for dy in dy_list[:8])
            bzl = result.get("八字联合", {})
            if bzl.get("日主"):
                sizhu_text += f"，日主{bzl['日主']}{bzl.get('身强身弱', '')}"
    except Exception:
        pass

    # 红鸾天喜(家庭事件辅助:添丁/婚庆)
    hl_zhi = tx_zhi = ""
    if birth_year:
        hl_zhi = _HONGLUAN.get(ZHI[(birth_year - 4) % 12], "")
        tx_zhi = _ZHI_OPP.get(hl_zhi, "")
    # 信号表延伸到现在+15年(未来大限段趋势的流年锚点,防止LLM自行推算年份)
    now_y = _dt.datetime.now().year
    sig_lines = [r["line"] for r in _year_signal_rows(
        result, birth_year, day_master, hl_zhi, tx_zhi, end_year=now_y + 15)]

    _sh = result.get("四化", {})
    natal_sihua = " ".join([
        f"{k}·{v}落{star_palace.get(v, '?')}宫".replace("宫宫", "宫")
        for k, v in [("化禄", _sh.get("化禄")), ("化权", _sh.get("化权")),
                     ("化科", _sh.get("化科")), ("化忌", _sh.get("化忌"))] if v
    ])
    _ptext, _ph = _profile_ctx(result)
    # P82v2: 全量数据文本(parse_family星曜白名单校验用——LLM提到的星曜必须∈此文本,
    # 实测编造:"小星天寿、天巫、yuede同宫"——轻量盘根本没有小星数据)
    _ctx_text = "\n".join([
        _fmt_palace(parent_p), parent_sihua, _star_line("太阳"), _star_line("太阴"),
        _fmt_palace(bro_p), _fmt_palace(prop_p), _fmt_palace(health_p),
        father_wealth_text, "\n".join(dx_lines), "\n".join(sig_lines), natal_sihua])
    return {
        "gen_type": "family",
        "gender": info.get("性别", ""),
        "age": age,
        "birth_year": birth_year,
        "sizhu": sizhu_text,
        "bazi_dayun": bazi_dayun_text,
        "ming_stars": "、".join((ming_p.get("主星") or []) + (ming_p.get("辅星") or [])) or "借对宫",
        "natal_sihua": natal_sihua,
        "parent_palace": _fmt_palace(parent_p),
        "parent_sihua": parent_sihua,
        "sun_line": _star_line("太阳"),
        "moon_line": _star_line("太阴"),
        "bro_palace": _fmt_palace(bro_p),
        "prop_palace": _fmt_palace(prop_p),
        "health_palace": _fmt_palace(health_p),
        "father_wealth": father_wealth_text,
        "dx_sihua": "\n".join(dx_lines),
        "signal_table": "\n".join(sig_lines),
        "profile_text": _ptext,
        "profile_phash": _ph,
        "chart_key": _chart_key(result),
        "ctx_text": _ctx_text,
    }


# P82v2: 星曜全集(parse_family白名单校验用)。
# 剔除与日常词同形的星名(天才/天空/晦气/破碎/天福等)防误杀;LLM正常行文不会引用这些词当星曜
_FAMILY_KNOWN_STARS = (
    "紫微", "天机", "太阳", "武曲", "天同", "廉贞", "天府", "太阴", "贪狼", "巨门",
    "天相", "天梁", "七杀", "破军",
    "文昌", "文曲", "左辅", "右弼", "天魁", "天钺", "禄存", "擎羊", "陀罗",
    "火星", "铃星", "地空", "地劫", "天马",
    "红鸾", "天喜", "天姚", "天刑", "天巫", "天寿", "月德", "天月", "阴煞",
    "台辅", "封诰", "龙池", "凤阁", "天官", "天厨", "孤辰", "寡宿", "蜚廉",
    "华盖", "咸池", "吊客", "病符", "大耗", "小耗", "劫煞", "灾煞", "指背",
    "白虎", "丧门", "贯索", "岁驿", "息神", "将星", "攀鞍", "天哭", "天虚",
    "解神", "恩光", "天贵", "三台", "八座", "旬空", "截空", "空亡", "天伤", "天使")


def parse_family(text: str, ctx_text: str = ""):
    """P82: 解析family四段输出 → [{'title','content'}...]。
    防编造三重校验:①≥3段 ②宫位引用(→/入/限/冲/落 X宫)∈12宫(与parse_verify三判定一致)
    ③v2星曜白名单:内容中的星曜名必须∈ctx_text(上下文全量数据文本)——
    实测盘1手足段编造"小星天寿、天巫、yuede同宫"(轻量盘无小星数据),此类幻觉必须代码拦截。
    判废返回None(由/family端点注入警告重试一次)"""
    import re as _re
    if not text:
        return None
    parts = _re.split(r"\*\*【(.+?)】\*\*", text)
    secs = []
    for i in range(1, len(parts) - 1, 2):
        title, content = parts[i].strip(), parts[i + 1].strip()
        if title and len(content) >= 30:
            secs.append({"title": title, "content": content})
    if len(secs) < 3:
        return None
    # 宫位引用白名单(信号位前缀才校验,与parse_verify三判定完全一致——泛化叙述中的"X宫"不算引用)
    palace_re = _re.compile(r"(?:→|入|限|冲|落)([^\s，。、·:：→|｜/()（）「」]{1,4})宫")
    _pal_names = sorted(_12_PALACES, key=len, reverse=True)
    for sec in secs:
        for tok in palace_re.findall(sec["content"]):
            if not (any(tok.endswith(pn) for pn in _pal_names)
                    or (tok + "宫") in _12_PALACES
                    or tok.endswith("命")):
                return None
    # v2: 星曜白名单——提到的星曜必须在上下文数据文本中出现过
    if ctx_text:
        for sec in secs:
            for star in _FAMILY_KNOWN_STARS:
                if star in sec["content"] and star not in ctx_text:
                    return None
    return secs


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


def parse_verify(text: str, result, birth_year: int, reject_log=None):
    """解析+防编造过滤断语。返回 [{'claim','basis','type'}...] 或 None(<5条降级)。
    三重白名单:年份范围 / 干支∈命盘真实集 / 宫位∈12宫。
    reject_log(P81v11):传入list则收集每条判废原因[{"claim","reason"}],供/verify构建具体化重写警告"""
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
        _why0 = []  # P81v11: 本条判废原因(喂回重试prompt)
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
                    ok = False; _why0.append(f"年龄不合理:{_age_at}岁婚恋/生育类须≥20岁")
                elif _ctype in ("career", "wealth") and _age_at < 16:
                    ok = False; _why0.append(f"年龄不合理:{_age_at}岁职业/财务类须≥16岁")
                elif _ctype == "study" and not (6 <= _age_at <= 23):
                    ok = False; _why0.append(f"年龄不合理:{_age_at}岁学业类限6-23岁")
        # ④b "或"字改写(P81v7第二轮):LLM"或"字惯性难禁(实测盘1单轮5/7违规,全杀→验证区为空)。
        # 改为截取首选事件(首选是LLM的第一判断,正确性由用户验证闭环仲裁,优于整条剔除);
        # "可能/大概"仍整条剔除(纯 hedging,无首选可取)
        if ok and "或" in claim:
            claim = _re.sub(r"或[^，。、；]{1,8}", "", claim)
            if len(claim) < 8:
                ok = False
        if ok and any(w in claim for w in ("可能", "大概")):
            ok = False; _why0.append("含'可能/大概'不确定词")
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
                        ok = False; _why0.append(f"依据引用{_star}化{_hua}与该年四化不符(张冠李戴)")
                        break
        # ⑤b 红鸾天喜/十神-年份交叉校验(P81v5第二轮):依据中"红鸾动/天喜动/X年(十神)"必须与该年实际值一致
        # (实测漏洞:LLM在巳年依据里写"红鸾动",癸巳正财年结婚写成"红鸾动"——信号虚标)
        if ok and _gz_m and birth_year:
            _ZHI = list("子丑寅卯辰巳午未申酉戌亥")
            _hl = _HONGLUAN.get(_ZHI[(birth_year - 4) % 12], "")
            _tx = _ZHI_OPP.get(_hl, "")
            _yz = _gz_m.group(0)[1]
            if ("红鸾动" in basis and _yz != _hl) or ("天喜动" in basis and _yz != _tx):
                ok = False; _why0.append("红鸾/天喜动标注与该年实际不符")
        if ok and _gz_m:
            _dm = _day_master_of(result)
            if _dm:
                for _ssm in _re.finditer(r"(正财|偏财|正官|七杀|正印|偏印|食神|伤官|比肩|劫财)年", basis):
                    if _shishen(_dm, _gz_m.group(0)[0]) != _ssm.group(1):
                        ok = False
                        _why0.append(f"十神虚标:{_gz_m.group(0)}年为{_shishen(_dm, _gz_m.group(0)[0])}年,非{_ssm.group(1)}年——照抄信号行")
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
                        ok = False; _why0.append("该年无婚恋合格信号(配偶星年/禄权科入夫妻/命入夫妻全无)")
                # ⑤c2 子女类:该年必须至少占1个子女信号(子女星/命入子女/四化入子女/红鸾天喜动)
                # P82v16精确化:红鸾/天喜年仅作弱信号保留(盘2 2014天喜年=真实添丁,用户确认),
                # 但"红鸾/天喜年+化曜入夫妻宫"=婚恋结构,该年无子女信号时严禁断添丁——
                # 盘3实锤:2018戊戌红鸾+权太阴→夫妻被断"怀孕生子添丁",命主并无怀孕生子(应的是婚恋);
                # 盘2 2014甲午天喜年无夫妻化曜=真实添丁——两样本构成完美区分
                if ok and _re.search(r"生子|添丁|怀孕|生育|得子|得女|二胎", claim):
                    _child_sig = (_row0["ss"] in _child_ss or "子女" in _row0["ln_ming"]
                                  or "→子女" in _row0["sihua_text"])
                    if not _child_sig:
                        if not _row0["hltx"]:
                            ok = False; _why0.append("该年无子女合格信号(子女星年/命入子女/四化入子女/红鸾天喜全无)")
                        elif _re.search(r"[禄权科][^ ]*→夫妻", _row0["sihua_text"]):
                            ok = False; _why0.append("红鸾/天喜年+化曜入夫妻宫=婚恋结构非添丁(该年无子女信号),应断婚恋类事件")
                # ⑤d 置业迁居类(P81v9收紧):合格信号仅"权/忌→田宅"或"禄→田宅+限田宅双锚"——
                # 命入田宅只是位置不是动作、化科=文书名声太轻、单化禄=财物之缘非变动动作
                # (实测:2008戊子禄贪狼→田宅+命入田宅+红鸾动被误断搬家,命主22岁大学在读并无搬家;
                # 两盘6个真实置业年全是权/忌→田宅或禄→田宅+限田宅双锚)
                if ok and _re.search(r"买房|购房|置业|卖房|装修|搬家|迁居|乔迁", claim):
                    if not (_re.search(r"[权忌][^ ]*→田宅", _row0["sihua_text"])
                            or (_re.search(r"禄[^ ]*→田宅", _row0["sihua_text"])
                                and "田宅" in _row0["dx"])):
                        ok = False; _why0.append("该年无置业合格信号(须化权/化忌入田宅,或化禄入田宅+限田宅双锚)")
                # ⑤e 亏损类:该年必须有"化忌入财帛/兄弟"(禄权入田宅的置业年严禁断亏损)
                if ok and _re.search(r"亏损|破财|赔钱|投资失利|亏本|被坑|被骗", claim):
                    if not _re.search(r"忌[^ ]*→(财帛|兄弟)", _row0["sihua_text"]):
                        ok = False; _why0.append("该年无化忌入财帛/兄弟,严禁断亏损")
                # ⑤g 手术住院类(P81v8):仅限"化忌→疾厄"——命入疾厄每12年一轮太泛
                # (实测:2019己亥仅命入疾厄被误断手术,命主并无手术住院)
                if ok and _re.search(r"手术|住院|大病|重病|开刀", claim):
                    if not _re.search(r"忌[^ ]*→疾厄", _row0["sihua_text"]):
                        ok = False; _why0.append("手术/住院仅限化忌入疾厄年,该年无忌入疾厄")
                # ⑤h 职业类年龄下限(P81v8):≤20岁(大学在读期)严禁跳槽/升职类断语
                # (实测:2006丙戌命入迁移被误断"跳槽",命主当年20岁实为升大学)
                if ok and birth_year:
                    _age0 = min(_ys0) - birth_year + 1
                    if _age0 <= 20 and _re.search(
                            r"跳槽|升职|创业|调岗|外派|离职|加薪|晋升|上任|换工作|入职", claim):
                        ok = False; _why0.append(f"{_age0}岁(大学在读期)严禁职业变动类断语,该年龄段变动信号只能断学业")
                # ⑤i 依据四化落宫一致性(P81v10):依据里"星化X入Y宫/ X星→Y宫"的落宫必须与该年信号行一致——
                # ⑤只校验星+化是否属该年四化,不校验落宫(实测:盘1 2019依据写"忌文曲入田宅宫",
                # 文曲确为该年忌星⑤放行,但盘1文曲在交友宫——"忌文曲→田宅"是另一张盘的信号,张冠李戴)。
                # 本命四化引用豁免(与⑤同规则:本命落宫本就不在流年信号行里)
                # P81v13补丁:落宫"宫"字改可选——LLM写"忌文曲入田宅"(无宫字)曾绕过提取,
                # 盘1 2019"搬家迁居"带虚标依据活过校验(v11复测实战暴露)
                if ok:
                    _all_sh2 = {s for row in _SIHUA_TABLE.values() for s in row if s}
                    _nsh = result.get("四化", {}) or {}
                    _npairs = {(_nsh.get("化" + h, ""), h) for h in "禄权科忌"}
                    _row_sh = {(m.group(2), m.group(1), m.group(3).rstrip("宫"))
                               for m in _re.finditer(r"([禄权科忌])([一-龥]{2})→([一-龥]{1,3})宫?",
                                                     _row0["sihua_text"])}
                    _cites = [(m.group(1), m.group(2), m.group(3).rstrip("宫"), m.start()) for m in
                              _re.finditer(r"([一-龥]{2})化(禄|权|科|忌)[入→]([一-龥]{1,3})宫?", basis)]
                    _cites += [(m.group(2), m.group(1), m.group(3).rstrip("宫"), m.start()) for m in
                               _re.finditer(r"(?<!化)([禄权科忌])([一-龥]{2})[入→]([一-龥]{1,3})宫?", basis)]
                    for _st, _hu, _pl, _pos in _cites:
                        if _st not in _all_sh2:
                            continue  # 非四化星曜引用(如"流年化忌"),不校验
                        if basis[max(0, _pos - 2):_pos] in ("本命", "生年"):
                            continue  # 本命四化引用,落宫与流年不同,豁免
                        if (_st, _hu) in _npairs:
                            continue  # 与本命四化一致(省略"本命"前缀),豁免
                        if (_st, _hu, _pl) not in _row_sh:
                            _actual = next((p for (s2, h2, p) in _row_sh
                                            if s2 == _st and h2 == _hu), "")
                            ok = False
                            _why0.append(f"依据落宫虚标:{_st}化{_hu}实际落{_actual or '?'}宫,非{_pl}宫——照抄信号行")
                            break
                # ⑤j 考试失利/复读类(P81v11):仅限"忌→官禄"或"文昌/文曲化忌"——
                # 忌入福德=情绪郁闷与考试无关(实测:2005乙酉忌太阴→福德被误断高考复读,
                # 命主当年正常高中读书,2006应届升学;且该条是"复读或考试失利"或字改写产物)
                if ok and _re.search(r"复读|考试失利|落榜|考研失败|名落孙山", claim):
                    if not (_re.search(r"忌[^ ]*→官禄", _row0["sihua_text"])
                            or _re.search(r"忌(文昌|文曲)→", _row0["sihua_text"])):
                        ok = False; _why0.append("复读/考试失利仅限化忌入官禄或文昌文曲化忌年,该年信号不符")
                # ⑤l 学业节点锚点(P81v14,盘3实战n=2立规):升学/考入/转学/毕业/考证类断语,
                # 该年必须有"化科入命宫/官禄宫/父母宫"或"文昌/文曲化科"——科入兄弟/夫妻/疾厄等
                # 与学业无关,属硬凑(实测:2004甲申科武曲→兄弟宫被断"考取资格证书"、
                # 2000庚辰科太阴→夫妻宫被断"转学",命主仅初中毕业均无其事)
                if ok and _re.search(r"考入|升学|录取|转学|毕业|中考|高考|考研|留学|考公|资格证书|考证", claim):
                    if not (_re.search(r"科[^ ]*→(命宫|官禄宫|父母宫)", _row0["sihua_text"])
                            or _re.search(r"科(文昌|文曲)→", _row0["sihua_text"])):
                        ok = False; _why0.append("学业节点断语须化科入命/官禄/父母宫或文昌文曲化科,该年学业锚点为零")
                # ⑤m 配偶星性别错配(P82v15,盘1v46实战):婚恋类断语,男命只能引正财/偏财年
                # (正官/七杀=男命子女星!),女命只能引正官/七杀年(正财/偏财=女命父星/钱财)。
                # 实测:盘1男命断"2015乙未年结婚"引"乙未正官年"——正官对男命是子女星不是配偶星,
                # 实际结婚2012壬辰=偏财年+限夫妻宫;且2015科紫微→子女宫与婚恋无关,双重硬凑
                if ok and _classify_claim(claim) == "marriage":
                    if _gender0 == "男" and _re.search(r"正官年|七杀年", basis):
                        ok = False
                        _why0.append("配偶星性别错配:男命婚恋只能引正财/偏财年(正官/七杀=男命子女星)")
                    elif _gender0 == "女" and _re.search(r"正财年|偏财年", basis):
                        ok = False
                        _why0.append("配偶星性别错配:女命婚恋只能引正官/七杀年(正财/偏财=女命父星/财)")
                # ⑤n 命入宫位引用一致性(P82v16,盘5实战):依据中"命入X宫"必须与该年信号行
                # 流年命宫一致——⑤b只管红鸾天喜/十神,⑤i只管化曜落宫,"命入X宫"无人校验
                # (实测:盘5 2014添丁依据写"命入子女宫",实际命入田宅宫——权破军→子女
                # 被夸大成"命入子女"双锚,信号强度虚增)
                if ok:
                    for _mm5 in _re.finditer(r"(?<!限)命入([一-龥]{1,3})宫?", basis):
                        _pl5 = _mm5.group(1).rstrip("宫")
                        if _pl5 != _row0["ln_ming"].rstrip("宫"):
                            ok = False
                            _why0.append(f"命入宫位虚标:该年实际命入{_row0['ln_ming']}宫,非{_pl5}宫——照抄信号行")
                            break
                # ⑤o 升学双信号(P82v16,盘3用户实锤):考入大学/升学/本科/录取类断语,
                # 该年必须"印年(正印/偏印)+文昌/文曲化科"双信号——单化科无印年不足以断升学
                # (盘3实锤:2006丙戌正财年+科文昌→官禄被断"考入大学",命主当年高中毕业直接工作;
                # 盘1 2006=偏印+科文昌=真实升学——双信号vs单信号跨盘实证,v10 prompt规则下沉parse)
                if ok and _re.search(r"考入|升学|本科|大学|录取", claim) \
                        and not _re.search(r"落榜|失利|复读", claim):
                    if not (_row0["ss"] in ("正印", "偏印")
                            and _re.search(r"科(文昌|文曲)→", _row0["sihua_text"])):
                        ok = False
                        _why0.append("升学断语须印年+文昌/文曲化科双信号,该年不满足(单化科/单印年不断升学)")
                # ⑤p 结婚/领证双锚(P82v17,盘3用户实锤):结婚/领证/再婚类断语,该年必须
                # "配偶星年+大限加持夫妻宫(限入夫妻宫 或 大限化禄/化权入夫妻宫)"双锚——
                # 单流年信号(即使配偶星+化曜入夫妻+红鸾)只能断恋爱
                # (4样本完美区分:盘1 2012偏财+限入夫妻=结婚✓;盘2 2012正官+限禄天同→夫妻=结婚✓;
                # 盘3 2018正官+权太阴→夫妻+红鸾但限在福德=恋爱非结婚(命主至今未婚);
                # 盘3 2010科太阴→夫妻但正印年非配偶星=恋爱)
                if ok and _re.search(r"结婚|领证|再婚", claim):
                    _dx_ok = ("夫妻" in _row0["dx"]
                              or _re.search(r"限[禄权][^ ]*→夫妻", _row0["dx_sihua"]))
                    if not (_row0["ss"] in _spouse_ss and _dx_ok):
                        ok = False
                        _why0.append("结婚/领证须配偶星年+大限加持夫妻宫(限入夫妻或限禄权→夫妻)双锚,单流年信号只能断恋爱")
        # ⑤k 模糊学业评价类(P81v13):"突破/进步/优异/名列前茅"无法对碰=凑数废话,
        # 整条剔除任何年龄(实测:1997丁丑正印+权入官禄被断"学业重要突破",命主11岁小学
        # 并无明显感觉;学业只断升学/考入/录取/落榜/复读/转学/毕业/留学等节点事件)
        # 注:放_row0块外——该类断语连信号校验资格都没有,与年份信号无关
        if ok and _re.search(r"学业|考试|成绩|学习|功课", claim) and \
                _re.search(r"突破|进步|优异|名列前茅|飞跃|提升明显|刮目相看", claim) and \
                not _re.search(r"考入|升学|录取|上榜|落榜|复读|毕业|转学|留学|考研|考公|中考|高考", claim):
            ok = False
            _why0.append("学业突破/进步类模糊评价无法对碰,只断升学/考入/落榜等节点事件")
        if ok:
            items.append({"claim": claim, "basis": basis,
                          "type": _classify_claim(claim)})
        elif reject_log is not None:
            # P81v12: 附该年信号行原文——实测"十神虚标"类连两轮照犯(壬辰=偏财被写成正财/正官),
            # 只给判废原因不够,必须把正确写法(信号行)一并喂回,LLM才有"照抄"的锚
            _ys9 = [int(y.group(0)) for y in year_re.finditer(claim)]
            _rw9 = _sig_rows.get(min(_ys9)) if (_ys9 and _sig_rows) else None
            _entry = {"claim": claim, "reason": "；".join(_why0)
                      or "白名单校验未过(年份/干支/宫位数据编造)"}
            if _rw9:
                _entry["signal"] = _rw9["line"]
            reject_log.append(_entry)
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
(每行格式: 年份干支(虚岁/流年命宫/所在大限/流年十神/红鸾天喜): 四化落本命宫位 |限禄X→宫 限忌X→宫(=大限干化禄/化忌落宫,十年背景);行内标"⚠岁限双忌"=流年忌与大限忌同落一宫,是丧亲/大病/家庭重大变故等大事应期的最强结构,权重最高)

【本盘候选年清单-选年唯一范围,最高优先级】以下清单已按本盘信号表用应期规则逐年预筛,断语年份必须且只能来自清单中对应事件类别的年份:
{ctx.get('eligible_text','')}
⚠️清单=唯一选年范围:某类别下断语的年份必须在该类清单内;清单标注"无合格年"的类别,严禁断该类事件(直接换有合格年的类别);同一类别有多个候选年时,选信号最强的1个,并把该年行内信号(十神/四化落宫/流年命宫/红鸾天喜)逐字照抄进依据。这是硬性约束——清单之外的[事件类型+年份]组合会被校验器直接判废,写了也白写

【应期规则-信号分权重,严禁只看四化选年】
⚠️【示例年份锚定警告-最高优先级】本文所有规则/坏例/好例/实测教训中出现的年份(2005/2006/2007/2008/2012/2013/2014/2015/2016/2019/2020/2023等)全部来自【其他命盘】的实测案例,与当前命主毫无关系!严禁因为"示例里出现过该年"就选用——每个断语年份必须先从下方信号表按规则独立筛出,示例只用来理解"信号权重怎么比、什么算虚标"(实测教训:某新命盘7条断语整批照抄示例年份2012/2014/2020/2023,与该盘信号全不符,全灭)
- 婚恋(恋爱/结婚/领证/订婚): 权重①配偶星年(男命正财/偏财年、女命正官/七杀年) ②流年化禄/化权/化科入夫妻宫 ③流年命入夫妻宫 ④红鸾天喜动(仅辅助加分)。⚠️①②③全无的年份,即使红鸾/天喜动也严禁断任何婚恋事件(含恋爱)——红鸾天喜是"喜庆星",婚恋/添丁/庆典都可能应,不是婚恋专属铁证(实测教训:2014仅有天喜动被误断结婚,实为添丁;2008仅有红鸾动被误断恋爱,真正的恋爱年2007=化权天同入夫妻宫;真正的结婚年2012=正官年+化禄入夫妻宫)。⚠️结婚/领证是最高门槛,必须双锚:"配偶星年"+"大限加持夫妻宫(限入夫妻宫 或 大限化禄/化权入夫妻宫)"——单流年信号即使"配偶星年+化曜入夫妻+红鸾动"三齐聚也只能断恋爱(实锤教训:某女命盘2018戊戌=正官年+权太阴化权入夫妻+红鸾动被误断"结婚领证",命主至今未婚,该年应的是恋爱——她真正的大限无夫妻加持;对比:真实结婚年=偏财年+限入夫妻宫双锚/正官年+限禄入夫妻双锚)。⚠️配偶星性别错配=整批错:男命婚恋只能引正财/偏财年——正官/七杀是男命的子女星,不是配偶星;女命反之(实测教训:某男命盘断"2015乙未年结婚"引"正官年",实际结婚2012壬辰=偏财年+限夫妻宫双锚;且2015化科入子女宫与婚恋无关,属硬凑)。⚠️婚恋断语与生子断语年份必须自洽:生子年必须晚于结婚年(不主动断未婚先孕)
- 子女(怀孕/生育): 权重①子女星年(男命正官/七杀年、女命食神/伤官年) ②流年命入子女宫或四化入子女宫 ③红鸾天喜动(添丁亦主喜庆,作弱信号)。生育断语年份必须晚于结婚断语年份(不主动断未婚先孕)。⚠️红鸾/天喜年若同年有化禄/化权/化科入夫妻宫=婚恋结构,该年①②全无则严禁断添丁,应断婚恋类(实锤教训:某女命盘2018戊戌=红鸾年+权太阴化权入夫妻宫被误断"怀孕生子添丁",命主当年并无怀孕生子——红鸾+夫妻化曜应的是婚恋;对比:天喜年无夫妻化曜的年份可以应添丁)。⚠️比选规则:生子添丁多个候选年时,"子女星年+红鸾/天喜动或命入子女宫"权重高于"子女星年+化曜入子女宫"(实锤教训:2014甲午七杀+天喜动+命入子女=三信号齐聚=真实得子年,2015乙未正官+紫微化科入子女被误选,年份偏1)
- 学业考试(升学/高考/考研/考公/留学): 正印/偏印年; 化科(文昌/文曲化科分量最重)。⚠️升学硬规则:"考入大学/升学/本科/录取"类断语,只允许在"印年+文昌/文曲化科"双信号年份下断——单化科(无印年)严禁断升学(实锤教训:某女命盘2006丙戌=正财年+文昌化科入官禄被误断"考入大学",命主当年高中毕业直接工作,根本没上大学——化科入官禄应的是毕业求职不是升学)。⚠️比选规则:某年同时占"印年+文昌/文曲化科"=双信号,权重高于单印年(实测教训:2006丙戌偏印+文昌化科=真实升大学年,2007丁亥仅正印年被误选,年份偏1)。⚠️首次本科入学一般在18-20岁(虚岁):断21岁及以后的"考入大学"必须有留级/复读类强证据支撑,否则优先往18-20岁的印年找(实测教训:断2007丁亥21岁考入大学,实为2006丙戌20岁正常应届升学——错误的晚一年锚点还会诱导编造出"复读"来圆场)。⚠️学业类只断节点事件(升学/考入/录取/落榜/复读/转学/毕业/留学/考研/考公),严禁断"学业突破/成绩进步/名列前茅"类模糊评价——无法对碰等于废话,且单印年(无文昌/文曲化科)分量不够(实测教训:1997丁丑正印+权天同入官禄被误断"学业重要突破",命主11岁小学并无明显感觉;该年无昌曲化科,且忌巨门同入官禄信号混杂)。⚠️学业节点锚点规则:升学/考入/转学/毕业/考证类断语,只允许在"化科入命宫/官禄宫/父母宫"或"文昌/文曲化科"的年份下断——化科落兄弟/夫妻/疾厄等其他宫位与学业无关,严禁拿来硬凑(实测教训:某盘科武曲→兄弟宫被断"考取资格证书"、科太阴→夫妻宫被断"转学",命主仅初中毕业,两条全假)
- 考试失利/复读/落榜: 仅限"化忌入官禄宫"或"文昌/文曲化忌"的年份下断——忌入福德=情绪郁闷与考试无关,严禁据忌入福德/夫妻/迁移断考试失利(实测教训:2005乙酉忌太阴→福德被误断高考复读,命主当年正常高中读书,次年应届升学)
- 置业迁居(买房/卖房/搬家/迁居/装修): 只允许在①"化权/化忌入田宅宫"或②"化禄入田宅宫且同年所在大限为田宅宫(双锚)"的年份下断。⚠️单化科入田宅分量太轻(科=文书名声,不是重资产动作),严禁据"科入田宅"断买房搬家——即使同年命入田宅也不算(实测教训:2015乙未命入田宅+紫微化科入田宅被误断买房,命主该年并未置业)。⚠️单化禄入田宅同样不够——禄=财物之缘,权/忌才是变动落实的动作四化;命入田宅+红鸾动也救不回来(实测教训:2008戊子禄贪狼→田宅+命入田宅+红鸾动被误断搬家,命主22岁大学在读并无搬家;两盘6个真实置业年全是权/忌→田宅或禄→田宅+限田宅双锚:2012权→田宅/2019忌→田宅/2023禄→田宅+限田宅)。⚠️迁移宫化忌=在外奔波受挫,严禁据此断搬家(实测教训:2005乙酉太阴化忌入迁移被误断搬家,命主该年并未搬家)
- 事业变动: 正官/七杀/正偏财年; 化禄/化权入官禄宫; 流年命入官禄宫。⚠️22岁及以前(大学在读期)严禁断跳槽/升职/创业/调岗——该年龄段命入迁移/官禄/化禄引动只能断学业事件(升学/高考/考研/转学/毕业/留学)(实测教训:2006丙戌命入迁移被误断"跳槽",命主当年20岁实为升大学)
- 健康伤病: 手术/住院/大病仅限"化忌入疾厄宫"的年份下断——流年命入疾厄每12年一轮太泛,单命入疾厄严禁断手术住院(实测教训:2019己亥仅命入疾厄被误断手术,命主该年并无手术住院;当年忌文曲→田宅,真实发生的是买房)
- 家庭大事(父母伤病/丧亲/家庭重大变故): 优先看标"⚠岁限双忌"的年份——流年忌+大限忌同落一宫是最强大事结构,落父母宫=父母大事,落疾厄=自身大病,落夫妻=婚姻大事;无岁限双忌时退看大限忌落宫(该行末尾"限忌X→宫"=这十年受压的宫位)。⚠️行内同时出现天喜/红鸾与化忌时,丧病类化忌信号优先于喜庆星(实测教训:某盘2026命入子女+天喜动,表面像添丁,实际应的是岁限双忌廉贞入父母宫=父亲当年离世)
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
「2007丁亥年考入大学」(命主21岁才首次入学偏晚;2006丙戌20岁偏印+文昌化科双信号,才是真实升学年)(错:升学比选先看18-20岁印年+文昌/文曲化科双信号,别被单印年吸走)
「2005乙酉年高考复读」(该年忌太阴→福德宫,无化忌入官禄、文昌文曲也未化忌)(错:忌入福德=情绪郁闷与考试无关,复读/考试失利仅限化忌入官禄宫或文昌/文曲化忌年)
「2006丙戌年跳槽」(命主当年20岁还在读大学)(错:22岁前变动信号只能断升学/学业事件,严禁断跳槽)
「2019己亥年手术」(该年仅命入疾厄,无化忌入疾厄)(错:命入疾厄每12年一轮太泛,手术住院仅限化忌入疾厄年;该年忌文曲→田宅,真实发生的是买房)
「2019己亥年剖腹产一子」(错:严禁断分娩方式,只能断"生子添丁")
「2023癸卯年投资亏损破财」(若该年化禄入田宅宫)(错:禄入田宅=置业大喜,只能断买房/大额支出,严禁断亏损)
「1997丁丑年学业考试有重要突破」(该年正印+权天同入官禄,但无文昌/文曲化科,且忌巨门同入官禄)(错:"突破/进步"是模糊评价无法对碰,学业只断升学/考入/落榜/复读等节点事件,且须印年+昌曲化科双信号)
「2015乙未年得一子添丁」(该年正官+紫微化科入子女,但2014甲午七杀+天喜动+命入子女宫三信号更重)(错:生子添丁比选,优先含红鸾/天喜动或命入子女宫的子女星年)
「2018戊戌年怀孕生子添丁」(该年=红鸾年+权太阴入夫妻宫,但无子女星/命入子女/化曜入子女)(错:红鸾年+夫妻化曜=婚恋结构,应断婚恋类,严禁断添丁)
「2018戊戌年结婚领证」(该年=正官年+权太阴入夫妻+红鸾动,但大限在福德宫无夫妻加持)(错:结婚必须配偶星年+大限加持夫妻宫双锚,单流年三信号只能断恋爱——命主该年实际恋爱并未结婚)
「2006丙戌年考入大学」(该年=正财年+文昌化科入官禄,无印年)(错:单化科无印年严禁断升学——化科入官禄应的是毕业求职,命主当年高中毕业直接工作)
【好断语-具体,照此风格】
「2016丙申年跳槽换了工作」
「2019己亥年买房,有置业大额支出」
「2013癸巳年升职,职位上了一个台阶」
直接输出7行,不要开场白。"""
        # P81v6: 重试警告(首轮断语被parse判废后由/verify端点注入,二轮重写)
        prompt += ctx.get("retry_note", "") or ""

    elif gen_type == "family":
        # P82: 家庭分析(父母画像/父财/父母健康/手足)。取象规则经盘3/盘4人工推演多锚点验证,
        # 数据全部给足(含父母宫干四化/父之财帛位/大限干四化/信号表延伸到未来15年),LLM只断不算
        prompt = f"""你是资深紫微斗数命理师,为命主做家庭分析。所有数据已给出,你只负责"断"不负责"算"——严禁自行排盘,严禁引用上方未给出的星曜、宫位、干支。

【命主】{ctx.get('gender','')}，现年{ctx.get('age','')}岁(虚岁){ctx.get('profile_text','')}
【八字四柱】{ctx.get('sizhu','')}
【八字大运】{ctx.get('bazi_dayun','')}
【命宫】{ctx.get('ming_stars','')}
【本命四化】{ctx.get('natal_sihua','')}
【父母宫】{ctx.get('parent_palace','')}
【父母宫干四化(父母宫天干飞出,=父母带来的缘)】{ctx.get('parent_sihua','')}
【太阳=父星】{ctx.get('sun_line','')}
【太阴=母星】{ctx.get('moon_line','')}
【兄弟宫(手足画像位)】{ctx.get('bro_palace','')}
【田宅宫(家庭房产)】{ctx.get('prop_palace','')}
【疾厄宫(命主健康,旁证家族体质)】{ctx.get('health_palace','')}
【父之财帛位(父母宫立太极,父亲财富级别看这里)】{ctx.get('father_wealth','')}
【大限干四化(十年气候,限禄/限权/限忌落本命宫)】
{ctx.get('dx_sihua','')}
【流年信号表(过去+未来15年,引用年份/干支/四化只允许查此表)】
{ctx.get('signal_table','')}
(每行格式: 年份干支(虚岁/流年命宫/所在大限/流年十神/红鸾天喜): 流年四化落宫 |限禄X→宫 限忌X→宫)

【取象规则-已经多盘实测验证,必须遵守】
- 太阳=父亲、太阴=母亲:庙旺=有能力/身体底好,落陷或与煞星(火星/铃星/地空/地劫/擎羊/陀罗)同宫=操劳偏弱
- 父母宫主星看父母整体气质与管教方式(如紫微天相=体面规矩严管教;杀破狼=奔波忙碌)
- 父之财帛位主星看父亲财富级别与理财风格(武曲/天府=善积累入库;太阴=细水长流;破军/贪狼=起伏大敢冒险)
- 大限干化禄入父之财帛位=那十年父亲财运最厚;大限干化忌入父之财帛位或父母宫=收紧/操心期。趋势用"XX-XX岁大限段"表述,严禁精确到单年(除非信号表该行有明确锚点且你引用原文)
- 健康取象只到器官系统层级:太阳+火星=血压/心脑血管倾向;太阳+地空地劫=气血亏虚/眼目;太阴+煞星=内分泌/睡眠/妇科倾向。⚠️严禁断具体病名(如"肝癌""心梗"),严禁断父母寿数/死亡年份——只能说"倾向""注意""哪个大限段偏弱"
- 兄弟宫看手足缘分:主星明朗=有手足且得力,空宫借对宫或煞星聚集=手足缘薄或聚少离多
- 年龄约束:命主现年{ctx.get('age','')}岁——对未成年命主,父母现状与趋势是分析主体;对成年命主,兼顾其与父母的关系互动与赡养责任
- 八字旁证:偏财=父星、正印=母星、比劫=兄弟姐妹,与紫微互参,矛盾时以紫微宫位数据为准
- ⚠️星曜白名单:上下文未列出的星曜=本盘无此数据,严禁提及——出现一个上下文没有的星曜名就是编造。小星/杂曜(天巫/天寿/月德/天姚等)即使上下文给出,权重也最低,只作辅助参考,严禁仅凭小星断职业/疾病等具体结论(实测:凭"天寿天巫"断"手足从事医疗玄学"过度发挥)
- ⚠️严禁"对宫/三合借力"类自行推算——只评述数据行直接给出的落宫;宫位对冲三合关系自己算的一律算错(实测:天机落财帛宫被说成"父之财帛位对宫借力",父之财帛在午、对宫是子、天机在巳,全错)
- ⚠️大限引用必须与数据行逐字一致:该行写"限权破军→兄弟宫"就只许说化权,严禁说成"化忌入兄弟宫"(实测:手足段把甲辰限权破军错引成"化忌入兄弟宫",自相矛盾)
- 大限干四化只用于父母/父财/父母健康三段;手足段只评述兄弟宫主星+本命四化+父母宫干四化中落兄弟宫的信号

输出4段,每段严格用 **【标题】** 开头,换行写内容:
**【父母画像】**(150-200字:父母性格气质/管教方式/父母关系/与命主缘分深浅)
**【父亲事业财富】**(150-200字:父亲职业类型画像/财富级别定位/未来几个大限段的趋势节奏)
**【父母健康】**(150-200字:父亲/母亲各自需注意的器官系统+偏弱的大限段+一句养生建议)
**【手足情况】**(100-150字:手足缘分/有无倾向/手足画像)

硬约束:宫位/星曜/四化落宫必须逐字引用上方数据,张冠李戴=编造;口语务实,联系命主实际生活场景;直接输出4段,不要开场白不要总结。"""
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
        # P81: verify的prompt v18(C方案候选年预筛——盘3 12轮全灭结构性修复:LLM选年被示例年
        # 干支锚定,警告+重试双机制失效;预筛合格年清单注入,LLM只从清单选年,parse闸门仍兜底;
        # v17=⑤p结婚双锚——盘3实锤:2018正官+权太阴→夫妻+红鸾被断结婚,
        # 命主至今未婚=恋爱;结婚须配偶星年+大限加持夫妻宫;v16=⑤c2精确化+⑤n+⑤o——
        # 盘3实锤:2018红鸾年被断添丁(实无怀孕)/2006单化科被断考入大学(实高中毕业直接工作);
        # v15=⑤m配偶星性别错配——盘1v46实战:男命断2015"正官年"结婚,
        # 正官=男命子女星非配偶星,实际2012壬辰偏财年+限夫妻宫;婚恋与生子年份必须自洽;
        # v13=岁限双忌入表+大限禄忌列——盘1父亡2026双廉贞忌入父母宫实证;
        # 学业节点锚点规则:化科入命/官禄/父母或昌曲化科——盘3科入兄弟断考证/科入夫妻断转学n=2立规;
        # 多义信号化忌优先——天喜/命入子女并存时丧病类优先;
        # v12=示例年份锚定警告——新命盘7条整批照抄示例年2012/2014/2020/2023全灭;
        # v11=⑤k模糊学业评价整条剔除——1997"学业突破"11岁无感;
        # 生子添丁比选:子女星+天喜/命入子女>子女星+化曜入子女——2014三信号=真实得子年,2015偏1;
        # v10=学业比选:印年+文昌/文曲化科双信号>单印年,首入本科限18-20岁;
        # 考试失利/复读仅限忌→官禄或文昌文曲化忌——实测2007升学偏1年(实2006)+2005复读虚标;
        # v9=置业再收紧:单化禄→田宅不算动作信号,须权/忌→田宅或禄→田宅+限田宅双锚;
        # v8=置业信号收紧为禄权忌→田宅/限田宅,命入田宅+化科不算;职业类≤20岁禁断;
        # 手术住院仅限忌→疾厄;忌入夫妻不算婚恋吉信号;女命太阳=夫星得财优先断丈夫带来;
        # v7=⑤c红鸾天喜降为纯辅助+同天干年必须选大限/命宫加持年;v6=信号权重排序+置业/亏损/分娩方式纠偏)
        # →独立递增,不影响其他gen_type缓存
        # P82: family独立版本(v3=STAR_EN2CN补全杂曜拼音泄漏(yuede→月德等9+40项)+
        # 小星规则改"权重最低辅助参考"(全量盘有小星数据,轻量盘无——v2"上下文根本没给小星"表述错误);
        # v2=星曜白名单+禁对宫三合自推+大限引用逐字一致——盘1"天机对宫借力"错/甲辰限权破军误为化忌)
        _ck_ver = ("v50" if gen_type == "verify"
                   else ("v3" if gen_type == "family" else "v33"))
        ck = f"zw:{gen_type}:{_stable_hash(str(age))}:{ctx.get('chart_key','')}:{ctx.get('profile_phash','noprof')}:{ctx.get('feedback_fhash','nofb')}:{_ck_ver}"
        if ctx.get("retry_note"):
            # P81v12: key含retry_note哈希——旧版固定":r1",警告内容变了仍命中旧缓存,
            # 实测信号行注入版重试4s"秒回"(吃的是上一版警告的旧LLM输出)
            ck += ":r1:" + _stable_hash(ctx["retry_note"][:200])
    except:
        ck = f"zw:{gen_type}:{int(_t.time())}"
    # P56: 保持800（用户要求，不能减少）
    # P76: summary例外——v9.34注入大运数据后总结变多章节,800token写不下截断半句;
    # 提1200后LLM按比例写更满(1786字)仍截断 → 1500+prompt限幅1100-1400字双保险
    max_tok = (1500 if gen_type in ("summary", "family")
               else (1200 if gen_type == "verify" else 800))
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
