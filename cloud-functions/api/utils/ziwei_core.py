# v7.10 deploy trigger 20260721-0816
"""
命理乾坤 · 紫微斗数核心计算引擎 v7.6
基于 iztro-py 排盘，联合八字喜用神解读
拆分: 所有常量表已提取至 bazi_data.py 和 ziwei_data.py
"""

import os
import datetime

# 导入共用八字常量 + 紫微专用常量
from .bazi_data import *
from .ziwei_data import *

# ---- 庙旺查询工具函数 ----
def _get_miaowang_label(star, zhi):
    """返回7级庙旺标签: 庙/旺/得/利/平/不/陷"""
    return MIAO_WANG_TABLE.get(star, {}).get(zhi, "")

def _get_miaowang_coeff(star_name, zhi_name):
    """返回星曜在当前地支的7级庙旺系数"""
    label = _get_miaowang_label(star_name, zhi_name)
    return _MW_COEFF_7.get(label, 1.0)

# ---- 工具函数 ----
def _hour_to_time_index(hour):
    """将24小时制转为iztro的时辰索引(0-12)"""
    if hour >= 23 or hour < 1:
        return 0   # 子时
    elif hour < 3:
        return 1   # 丑时
    elif hour < 5:
        return 2   # 寅时
    elif hour < 7:
        return 3   # 卯时
    elif hour < 9:
        return 4   # 辰时
    elif hour < 11:
        return 5   # 巳时
    elif hour < 13:
        return 6   # 午时
    elif hour < 15:
        return 7   # 未时
    elif hour < 17:
        return 8   # 申时
    elif hour < 19:
        return 9   # 酉时
    elif hour < 21:
        return 10  # 戌时
    else:
        return 11  # 亥时


def _parse_ju_name(ju_en):
    """解析五行局英文名，返回(中文五行, 局数)"""
    if not ju_en:
        return "木", 3
    for cn_name, wx in JU_EN2CN.items():
        if cn_name in ju_en or wx in ju_en:
            return wx, JU_NUM[wx]
    # 尝试从数字解析
    if "二" in ju_en or "2" in ju_en:
        return "水", 2
    if "三" in ju_en or "3" in ju_en:
        return "木", 3
    if "四" in ju_en or "4" in ju_en:
        return "金", 4
    if "五" in ju_en or "5" in ju_en:
        return "土", 5
    if "六" in ju_en or "6" in ju_en:
        return "火", 6
    return "木", 3


def _parse_branch(branch_en):
    """解析iztro的地支英文名为索引"""
    if not branch_en:
        return 0
    mapping = {
        "zi": 0, "chou": 1, "yin": 2, "mao": 3,
        "chen": 4, "si": 5, "wu": 6, "wei": 7,
        "shen": 8, "you": 9, "xu": 10, "hai": 11
    }
    for en, idx in mapping.items():
        if en in branch_en.lower():
            return idx
    return 0


def _parse_stem(stem_en):
    """解析iztro的天干英文名为索引"""
    if not stem_en:
        return 0
    mapping = {
        "jia": 0, "yi": 1, "bing": 2, "ding": 3,
        "wu": 4, "ji": 5, "geng": 6, "xin": 7,
        "ren": 8, "gui": 9
    }
    for en, idx in mapping.items():
        if en in stem_en.lower():
            return idx
    return 0


def _star_en_to_cn(star_en):
    """将iztro的星曜英文名转为中文名"""
    if not star_en:
        return ""
    # 直接匹配
    if star_en in STAR_EN2CN:
        return STAR_EN2CN[star_en]
    # 尝试部分匹配
    for en, cn in STAR_EN2CN.items():
        if en.startswith(star_en) or star_en.startswith(en):
            return cn
    return star_en


def _sihua_en_to_cn(mutagen):
    """将iztro的四化英文名转为中文"""
    if not mutagen:
        return None
    for en, cn in SIHUA_EN2CN.items():
        if en in str(mutagen).lower():
            return cn
    # 尝试直接中文匹配
    if "禄" in str(mutagen):
        return "化禄"
    if "权" in str(mutagen):
        return "化权"
    if "科" in str(mutagen):
        return "化科"
    if "忌" in str(mutagen):
        return "化忌"
    return None


# ----- 格局检测 -----
def _detect_patterns(places, ming_branch, sihua, year_gan):
    """检测命盘中的著名紫微格局（参照《紫微斗数全书》）"""
    patterns = []
    zhi_to_p = {}
    for p in places:
        zhi_to_p[p.get("宫位")] = p

    # ---- 辅助函数 ----
    def _stars_at(branch):
        """获取某地支的全部星曜（主星+辅星）"""
        p = zhi_to_p.get(branch, {})
        return p.get("主星", []) + p.get("辅星", [])

    def _stars_offset(offset):
        """获取命宫偏移某宫位的全部星曜"""
        return _stars_at((ming_branch - offset) % 12)

    def _sihua_at(branch):
        """获取某地支的四化信息"""
        return zhi_to_p.get(branch, {}).get("四化", {})

    def _sihua_offset(offset):
        """获取命宫偏移某宫位的四化信息"""
        return _sihua_at((ming_branch - offset) % 12)

    def _palace_name(branch):
        """获取某地支的宫名"""
        return zhi_to_p.get(branch, {}).get("宫名", "")

    # 常用参考
    ming_stars = zhi_to_p.get(ming_branch, {}).get("主星", [])
    dup_gong = (ming_branch - 6) % 12  # 对宫（迁移宫）
    dup_stars = zhi_to_p.get(dup_gong, {}).get("主星", [])
    all_stars = sum([zhi_to_p.get(i, {}).get("主星", []) + zhi_to_p.get(i, {}).get("辅星", []) for i in range(12)], [])
    ming_zhi_name = zhi_to_p.get(ming_branch, {}).get("地支", "")
    shen_places = [p for p in places if p.get("是否身宫")]
    sha = ["擎羊", "陀罗", "火星", "铃星"]

    # ---- 1. 日月并明格 / 丹墀桂墀格（《全书》经典富贵格局） ----
    sun_branch = None
    moon_branch = None
    for i in range(12):
        ss = zhi_to_p.get(i, {}).get("主星", [])
        if "太阳" in ss:
            sun_branch = i
        if "太阴" in ss:
            moon_branch = i

    rymm_detected = False

    # Case 1: 天梁在丑(1)坐命 + 太阳在巳(5) + 太阴在酉(9) — 日月庙旺合照命宫
    if ming_branch == 1 and "天梁" in ming_stars and sun_branch == 5 and moon_branch == 9:
        rymm_detected = True
        patterns.append({"name": "日月并明格", "desc": "天梁丑宫坐命，日月庙旺合照。少年即以学问扬名，一世荣华。曾国藩同格，宜公职、学术、教育", "level": "good"})

    # Case 2: 命宫午(6)无正曜 + 寅(2)巨门太阳 + 子(0)天同太阴 — 日月入庙旺朝照
    if not rymm_detected and ming_branch == 6 and not ming_stars:
        yin_stars = zhi_to_p.get(2, {}).get("主星", [])
        zi_stars = zhi_to_p.get(0, {}).get("主星", [])
        if "巨门" in yin_stars and "太阳" in yin_stars and "天同" in zi_stars and "太阴" in zi_stars:
            rymm_detected = True
            patterns.append({"name": "日月并明格", "desc": "命宫午无正曜，日月入庙旺朝照。外出贵显，宜传播、外交、文教事业", "level": "good"})

    # Case 3: 太阳坐命辰(4)/巳(5) + 太阴在对宫酉(9)/戌(10) — 丹墀桂墀
    if not rymm_detected and "太阳" in ming_stars and ming_branch in [4, 5]:
        exp_moon = [9, 10] if ming_branch == 4 else [9]  # 辰→戌, 巳→酉
        if moon_branch in exp_moon and "太阴" in zhi_to_p.get(moon_branch, {}).get("主星", []):
            rymm_detected = True
            patterns.append({"name": "丹墀桂墀格", "desc": "太阳在辰/巳坐命，太阴在酉/戌坐对宫，日月皆旺。心地光明，少年得志，早遂青云之志", "level": "good"})

    # Case 4: 太阴坐命酉(9)/戌(10) + 太阳在对宫辰(4)/巳(5) — 丹墀桂墀
    if not rymm_detected and "太阴" in ming_stars and ming_branch in [9, 10]:
        exp_sun = [4] if ming_branch == 10 else [4, 5]  # 戌→辰, 酉→巳
        if sun_branch in exp_sun and "太阳" in zhi_to_p.get(sun_branch, {}).get("主星", []):
            rymm_detected = True
            patterns.append({"name": "丹墀桂墀格", "desc": "太阴在酉/戌坐命，太阳在巳/辰坐对宫，日月皆旺。心地善良光明磊落，一分耕耘一分收获", "level": "good"})

    # 兜底宽泛判定：日月都在命宫三方四正且皆庙旺（旺系数>=1.10），记为"日月交辉"
    if not rymm_detected and sun_branch is not None and moon_branch is not None:
        # 要求日月都在命宫三方四正内（命宫、财帛、官禄、迁移）
        sanfang_zhis = {ming_branch, (ming_branch - 4) % 12, (ming_branch - 8) % 12, dup_gong}
        if sun_branch in sanfang_zhis and moon_branch in sanfang_zhis:
            sun_mw = _get_miaowang_coeff("太阳", ZHI[sun_branch])
            moon_mw = _get_miaowang_coeff("太阴", ZHI[moon_branch])
            if sun_mw >= 1.10 and moon_mw >= 1.10:
                patterns.append({"name": "日月交辉", "desc": "太阳太阴皆庙旺且在三方四正照命，日月同辉。心地光明磊落，有贵人运，利公职外务", "level": "good"})

    # ---- 2. 明珠出海格 — 命未(7)无主星 + 太阳卯(3) + 太阴亥(11) ----
    if ming_branch == 7 and not ming_stars and sun_branch == 3 and moon_branch == 11:
        patterns.append({"name": "明珠出海", "desc": "安命在未无正曜，日月在卯亥照命。公职考试金榜题名，政界发展飞黄腾达", "level": "good"})

    # ---- 3. 月朗天门格 — 太阴在亥(11)坐命 ----
    if ming_branch == 11 and "太阴" in ming_stars:
        patterns.append({"name": "月朗天门", "desc": "太阴在亥宫坐命，又名月落亥宫。太阴主富，亥为天门，富中带贵，利求财积累", "level": "good"})

    # ---- 4. 日照雷门格 — 太阳在卯(3)坐命 ----
    if ming_branch == 3 and "太阳" in ming_stars:
        patterns.append({"name": "日照雷门", "desc": "太阳在卯宫坐命，旭日东升之象。又名日出扶桑格，为人热情开朗，带贵气，利公职外务", "level": "good"})

    # ---- 5. 日丽中天格 — 太阳在午(6)坐命 ----
    if ming_branch == 6 and "太阳" in ming_stars:
        patterns.append({"name": "日丽中天", "desc": "太阳在午宫坐命，光芒最盛之时。又名金灿光辉格，光明正大，领导气质，利仕途掌权", "level": "good"})

    # ---- 6. 日月同宫格 — 日月同在丑(1)/未(7)坐命 ----
    if ming_branch in [1, 7] and "太阳" in ming_stars and "太阴" in ming_stars:
        patterns.append({"name": "日月同宫", "desc": "日月同在丑/未宫坐命，日月交辉。主晋升之象，事业稳步上升，人际关系圆融", "level": "good"})

    # ---- 7. 日月反背格 — 太阳戌+太阴辰，两星皆弱 ----
    if ("太阳" in ming_stars and ming_branch == 10 and moon_branch == 4) or \
       ("太阴" in ming_stars and ming_branch == 4 and sun_branch == 10):
        patterns.append({"name": "日月反背", "desc": "太阳在戌太阴在辰，两星光芒皆弱。劳碌命，求人不如求己，早年辛苦，宜脚踏实地", "level": "warn"})

    # ---- 8. 日月夹命格 — 命丑/未 + 日月在左右邻宫相夹 ----
    if ming_branch in [1, 7]:
        left_zhi = (ming_branch - 1) % 12
        right_zhi = (ming_branch + 1) % 12
        left_stars = zhi_to_p.get(left_zhi, {}).get("主星", [])
        right_stars = zhi_to_p.get(right_zhi, {}).get("主星", [])
        has_sun = "太阳" in left_stars or "太阳" in right_stars
        has_moon = "太阴" in left_stars or "太阴" in right_stars
        if has_sun and has_moon:
            patterns.append({"name": "日月夹命", "desc": "太阳太阴在左右邻宫相夹命宫。有财运，利事业发展，贵人助力强", "level": "good"})

    # ---- 9. 紫府同宫格 — 紫微+天府同宫在寅(2)或申(8) ----
    if ming_branch in [2, 8] and "紫微" in ming_stars and "天府" in ming_stars:
        patterns.append({"name": "紫府同宫", "desc": "紫微天府二帝同宫坐命，贵气极重。宜领导管理岗位，但决策需果断不可犹豫", "level": "good"})

    # ---- 10. 府相朝垣格 — 天府+天相在三方四正照命 ----
    sanfang = [(ming_branch - 4) % 12, (ming_branch - 8) % 12, dup_gong]
    has_tf = any("天府" in zhi_to_p.get(s, {}).get("主星", []) for s in sanfang)
    has_tx = any("天相" in zhi_to_p.get(s, {}).get("主星", []) for s in sanfang)
    if has_tf and has_tx:
        patterns.append({"name": "府相朝垣", "desc": "天府天相在三方四正照命，衣食无忧。为官或做主管机运佳，宜稳定发展", "level": "good"})

    # ---- 11. 机月同梁格 — 命宫三方见天机+太阴+天同+天梁 ----
    sanfang_all_stars = []
    for sz in sanfang + [ming_branch]:
        sanfang_all_stars.extend(zhi_to_p.get(sz, {}).get("主星", []))
    if all(s in sanfang_all_stars for s in ["天机", "太阴", "天同", "天梁"]):
        patterns.append({"name": "机月同梁", "desc": "天机太阴天同天梁四星在三方四正交会。所谓机月同梁做吏人，宜公职军公教", "level": "info"})

    # ---- 12. 巨日同宫格 — 巨门+太阳同宫在寅(2)或申(8) ----
    if ming_branch in [2, 8] and "巨门" in ming_stars and "太阳" in ming_stars:
        patterns.append({"name": "巨日同宫", "desc": "巨门太阳同在寅/申坐命。又名官封三代格，为贵格，求名易求利，宜从政或公众人物", "level": "good"})

    # ---- 13. 火铃贪格 — 贪狼守命 + 火星/铃星在命或三方 ----
    if "贪狼" in ming_stars:
        huo_ling = ["火星", "铃星"]
        has_hl = any(h in _stars_at(ming_branch) for h in huo_ling)
        if not has_hl:
            for sz in sanfang:
                if any(h in _stars_at(sz) for h in huo_ling):
                    has_hl = True
                    break
        if has_hl:
            patterns.append({"name": "火铃贪格", "desc": "贪狼守命遇火星/铃星会照，有突然发达、获横财之象。爆发力强，宜把握机遇", "level": "good"})

    # ---- 14. 七杀朝斗 — 七杀在子(0)/午(6)/寅(2)/申(8)守命 ----
    if "七杀" in ming_stars and ming_branch in [0, 6, 2, 8]:
        patterns.append({"name": "七杀朝斗", "desc": "七杀坐命于子午寅申，威权果敢，作风强势。为贵格亦可成富，宜军警武职或创业", "level": "good"})

    # ---- 15. 英星入庙 — 破军在子(0)/午(6)守命 ----
    if "破军" in ming_stars and ming_branch in [0, 6]:
        patterns.append({"name": "英星入庙", "desc": "破军坐命于子午，有领导力，喜冒险犯难，具开创精神。宜开拓型事业，敢为天下先", "level": "good"})

    # ---- 16. 石中隐玉 — 巨门在子(0)/午(6)守命 ----
    if "巨门" in ming_stars and ming_branch in [0, 6]:
        patterns.append({"name": "石中隐玉", "desc": "巨门坐命于子午，有才能但先苦后甘。早年辛苦中晚年发达，宜专业深耕积累口碑", "level": "good"})

    # ---- 17. 命无正曜（命宫无主星） ----
    if not ming_stars:
        patterns.append({"name": "命无正曜", "desc": "命宫无主星，借迁移宫星曜论命。一生靠环境与他人搭台，宜借势而为", "level": "info"})

    # ---- 18. 阳梁昌禄格（太阳+天梁+文昌/禄存会照） ----
    if "太阳" in dup_stars and "天梁" in dup_stars and any(s in all_stars for s in ["文昌", "禄存"]):
        patterns.append({"name": "阳梁昌禄", "desc": "太阳天梁在迁移宫照命宫，配合文昌禄存，主光明磊落、仕途顺遂，宜公职竞考", "level": "good"})

    # ---- 19. 权忌同宫（官禄宫同时有化权和化忌） ----
    guanlu_sihua = _sihua_offset(8)
    if "化权" in guanlu_sihua and "化忌" in guanlu_sihua:
        patterns.append({"name": "权忌同宫", "desc": "化权与化忌同入官禄宫，有权有势但口舌是非不断，倪海厦云：权能制忌，有得有失，利创业不利打工", "level": "warn"})

    # ---- 20. 三奇嘉会（禄权科在三方四正） ----
    all_sihua = {}
    for p in places:
        all_sihua.update(p.get("四化", {}))
    if all(s in all_sihua for s in ["化禄", "化权", "化科"]):
        patterns.append({"name": "三奇嘉会", "desc": "禄权科三奇俱全，紫微最高格局之一，一生多贵人、机遇、名声，福报深厚", "level": "good"})

    # ---- 21. 天机化科在身宫 ----
    for sp in shen_places:
        sp_sihua = sp.get("四化", {})
        if "化科" in sp_sihua and sp_sihua["化科"] == "天机":
            patterns.append({"name": "天机科在身宫", "desc": "天机化科坐身宫，以智慧名声取财，宜技术、咨询、教育行业", "level": "good"})

    # ---- 22. 太阴化禄在福德 ----
    for p in places:
        if p.get("宫名") == "福德":
            fs = p.get("四化", {})
            if "化禄" in fs and fs["化禄"] == "太阴":
                patterns.append({"name": "太阴禄照福德", "desc": "太阴化禄在福德宫，福气深厚，精神富足，晚年清福，心态乐观是关键", "level": "good"})
            break

    # ---- 23. 空宫借星 ----
    kong_palaces = []
    for p in places:
        if not p.get("主星"):
            kong_palaces.append(p.get("宫名"))
    if len(kong_palaces) >= 2:
        patterns.append({"name": "多宫借星", "desc": f"{'、'.join(kong_palaces[:4])}等宫无主星，借对宫星曜论命，人生需借力而行", "level": "info"})

    # ---- 24. 命宫三方见煞（擎羊/陀罗/火星/铃星在三方） ----
    sanfang_zhis = [ming_branch, (ming_branch - 4) % 12, (ming_branch - 8) % 12]
    sha_count = 0
    for sz in sanfang_zhis:
        sf_stars = _stars_at(sz)
        sha_count += sum(1 for s in sha if s in sf_stars)
    if sha_count >= 2:
        patterns.append({"name": "三方见煞", "desc": "命宫三合方见煞星，人生波折较多但抗压能力强，宜武职技术", "level": "warn"})

    # ---- 25. 禄马交驰 — 命宫或三方有禄存/化禄+天马 ----
    has_lu = any(s in _stars_at(ming_branch) for s in ["禄存"]) or "化禄" in _sihua_at(ming_branch)
    has_ma = "天马" in _stars_at(ming_branch)
    if not (has_lu and has_ma):
        for sz in sanfang:
            sz_stars = _stars_at(sz)
            if "天马" in sz_stars:
                if any(s in sz_stars for s in ["禄存"]) or "化禄" in _sihua_at(sz):
                    has_lu, has_ma = True, True
                    break
    if has_lu and has_ma:
        patterns.append({"name": "禄马交驰", "desc": "禄存/化禄与天马同宫或会照，主奔波劳碌而招财。宜外务、贸易、物流、跨境行业", "level": "good"})

    return patterns


# ----- 格局关键星曜映射 -----
def _pattern_key_stars():
    """返回格局名→关键星曜集合的映射，用于判断格局在大运/流年中是否被激活"""
    return {
        "丹墀桂墀格":    {"太阳", "太阴"},
        "日月并明格":    {"太阳", "太阴", "天梁"},
        "日月交辉":      {"太阳", "太阴"},
        "明珠出海":      {"太阳", "太阴"},
        "月朗天门":      {"太阴"},
        "日照雷门":      {"太阳"},
        "日丽中天":      {"太阳"},
        "日月同宫":      {"太阳", "太阴"},
        "日月反背":      {"太阳", "太阴"},
        "日月夹命":      {"太阳", "太阴"},
        "紫府同宫":      {"紫微", "天府"},
        "府相朝垣":      {"天府", "天相"},
        "机月同梁":      {"天机", "太阴", "天同", "天梁"},
        "巨日同宫":      {"巨门", "太阳"},
        "火铃贪格":      {"贪狼", "火星", "铃星"},
        "七杀朝斗":      {"七杀"},
        "英星入庙":      {"破军"},
        "石中隐玉":      {"巨门"},
        "阳梁昌禄":      {"太阳", "天梁", "文昌", "禄存"},
        "禄马交驰":      {"天马"},
        "三奇嘉会":      {"__sihua_lu", "__sihua_quan", "__sihua_ke"},
        "命无正曜":      set(),
        "多宫借星":      set(),
        "三方见煞":      {"擎羊", "陀罗", "火星", "铃星"},
        "权忌同宫":      {"__sihua_quan", "__sihua_ji"},
        "天机科在身宫":  {"天机"},
        "太阴禄照福德":  {"太阴"},
    }


def _get_active_patterns(natal_patterns, active_stars, active_sihua=None):
    """
    判断哪些本命格局在当前大运/流年的活跃星曜集合中被激活。
    
    active_stars: 当前运程三方四正内的星曜列表（主星+辅星）
    active_sihua: 当前运程宫位内的四化集合（如 {"化禄":"天机","化权":"太阳"}）
    
    返回: [(格局名, 激活程度描述), ...]
    """
    if not natal_patterns:
        return []
    
    star_map = _pattern_key_stars()
    active_set = set(active_stars) if active_stars else set()
    sihua_set = set(active_sihua.keys()) if active_sihua else set()
    # 四化相关的星曜也加入激活集
    if active_sihua:
        for hua_name, star_name in active_sihua.items():
            active_set.add(star_name)
    
    activations = []
    for pat in natal_patterns:
        name = pat.get("name", "")
        level = pat.get("level", "")
        keys = star_map.get(name, set())
        if not keys:
            continue
        
        # 分离四化特殊标记
        star_keys = {k for k in keys if not k.startswith("__")}
        sihua_keys = {k.replace("__sihua_", "化") for k in keys if k.startswith("__sihua_")}
        
        star_hit = len(star_keys & active_set) if star_keys else 0
        sihua_hit = len(sihua_keys & sihua_set) if sihua_keys else 0
        total_keys = len(star_keys) + len(sihua_keys)
        total_hit = star_hit + sihua_hit
        
        if total_hit > 0:
            if total_hit >= total_keys * 0.75:
                degree = "充分激活"
            elif total_hit >= total_keys * 0.5:
                degree = "部分激活"
            else:
                degree = "星曜呼应"
            # 排除纯信息型格局（太啰嗦）
            if name not in ("多宫借星", "三方见煞", "命无正曜") or degree == "充分激活":
                activations.append((name, level, degree))
    
    # 排序：充分激活 > 部分激活 > 星曜呼应；good > warn > info
    order = {"充分激活": 0, "部分激活": 1, "星曜呼应": 2}
    level_order = {"good": 0, "warn": 1, "info": 2}
    activations.sort(key=lambda x: (order.get(x[2], 9), level_order.get(x[1], 9)))
    
    return activations


def full_ziwei_analysis(solar_year, solar_month, solar_day, hour, sex, is_solar=True, ln_weights=None):
    """
    紫微斗数全盘分析
    输入: 公历日期 + 时辰(0-23) + 性别
    返回: 完整紫微命盘数据
    ln_weights: 可选 dict，覆盖流年评分权重。Key: dy_floor, ln_ming, ln_aux,
                sihua_star, sihua_aux, sanfang。None 时使用默认值。
    """
    try:
        from iztro_py import astro
    except ImportError:
        return {"error": "iztro-py库未安装，请运行: pip install iztro-py"}

    # 转换时辰索引
    time_index = _hour_to_time_index(hour)
    gender = "男" if sex == "男" else "女"

    # 使用iztro-py排盘
    try:
        solar_date = f"{solar_year}-{solar_month:02d}-{solar_day:02d}"
        chart = astro.by_solar(solar_date, time_index, gender, True, "zh-CN")
    except Exception as e:
        return {"error": f"排盘失败: {str(e)}"}

    # 解析命宫/身宫地支
    ming_branch = _parse_branch(chart.earthly_branch_of_soul_palace)
    shen_branch = _parse_branch(chart.earthly_branch_of_body_palace)

    # 解析五行局
    ju_en = str(chart.five_elements_class)
    wx, ju_num = _parse_ju_name(ju_en)

    # 找紫微星位置
    ziwei_pos = None
    for p in chart.palaces:
        if p.major_stars:
            for s in p.major_stars:
                if "ziwei" in str(s.name).lower():
                    ziwei_pos = _parse_branch(p.earthly_branch)
                    break
        if ziwei_pos is not None:
            break
    if ziwei_pos is None:
        ziwei_pos = 0

    # 年干
    for p in chart.palaces:
        if p.name == "soulPalace":
            year_gan_idx = _parse_stem(p.heavenly_stem)

    # 从农历信息获取年干
    try:
        from lunarcalendar import Converter, Solar
        solar = Solar(solar_year, solar_month, solar_day)
        lunar = Converter.Solar2Lunar(solar)
        lunar_year = lunar.year
        lunar_month = lunar.month
        lunar_day = lunar.day
    except Exception:
        lunar_year = solar_year
        lunar_month = 1
        lunar_day = 1

    year_gan_i = (lunar_year - 4) % 10
    year_zhi_i = (lunar_year - 4) % 12
    year_gan = GAN[year_gan_i]

    # 安四化
    SIHUA = {
        "甲": ["廉贞", "破军", "武曲", "太阳"],
        "乙": ["天机", "天梁", "紫微", "太阴"],
        "丙": ["天同", "天机", "文昌", "廉贞"],
        "丁": ["太阴", "天同", "天机", "巨门"],
        "戊": ["贪狼", "太阴", "右弼", "天机"],
        "己": ["武曲", "贪狼", "天梁", "文曲"],
        "庚": ["太阳", "武曲", "太阴", "天同"],
        "辛": ["巨门", "太阳", "文曲", "文昌"],
        "壬": ["天梁", "紫微", "左辅", "武曲"],
        "癸": ["破军", "巨门", "太阴", "贪狼"],
    }
    sihua = SIHUA.get(year_gan, ["", "", "", ""])

    # 大限
    yang = year_gan in ["甲", "丙", "戊", "庚", "壬"]
    daxian_forward = (sex == "男" and yang) or (sex == "女" and not yang)

    # 构建十二宫数据
    # 从iztro结果构建地支→宫位信息的映射
    iztro_by_branch = {}
    for p in chart.palaces:
        p_branch = _parse_branch(p.earthly_branch)
        iztro_by_branch[p_branch] = p

    # 十二宫名从命宫起逆时针排列
    # 命宫在ming_branch, 兄弟在(ming_branch-1)%12, 夫妻在(ming_branch-2)%12, ...
    places = []
    for i in range(12):
        palace_name = PALACE_NAMES[i]
        palace_zhi_i = (ming_branch - i) % 12  # 逆时针排列

        # 从iztro结果中获取对应宫位
        iztro_palace = iztro_by_branch.get(palace_zhi_i)

        # 天干地支
        if iztro_palace:
            p_gan = GAN[_parse_stem(iztro_palace.heavenly_stem)]
            p_zhi = ZHI[_parse_branch(iztro_palace.earthly_branch)]
        else:
            # 使用五虎遁推算
            WUHU = {"甲": 2, "己": 2, "乙": 4, "庚": 4,
                     "丙": 6, "辛": 6, "丁": 8, "壬": 8,
                     "戊": 0, "癸": 0}
            base = WUHU.get(year_gan, 0)
            pgz_idx = (palace_zhi_i - 2) % 12
            p_gan = GAN[(base + pgz_idx) % 10]
            p_zhi = ZHI[palace_zhi_i]

        # 主星
        major_stars = []
        if iztro_palace and iztro_palace.major_stars:
            for s in iztro_palace.major_stars:
                cn = _star_en_to_cn(s.name)
                if cn:
                    major_stars.append(cn)

        # 辅星
        minor_stars = []
        if iztro_palace and iztro_palace.minor_stars:
            for s in iztro_palace.minor_stars:
                cn = _star_en_to_cn(s.name)
                if cn:
                    minor_stars.append(cn)

        # 杂耀
        adj_stars = []
        if iztro_palace and iztro_palace.adjective_stars:
            for s in iztro_palace.adjective_stars:
                cn = _star_en_to_cn(s.name)
                if cn:
                    adj_stars.append(cn)

        # 四化状态
        sihua_status = {}
        all_stars = major_stars + minor_stars
        for j, t in enumerate(["化禄", "化权", "化科", "化忌"]):
            star = sihua[j]
            if star in all_stars:
                sihua_status[t] = star

        # 也从iztro的四化信息中补充
        if iztro_palace:
            for s_list in [iztro_palace.major_stars or [], iztro_palace.minor_stars or []]:
                for s in s_list:
                    if hasattr(s, 'mutagen') and s.mutagen:
                        hua = _sihua_en_to_cn(s.mutagen)
                        if hua and hua not in sihua_status:
                            cn = _star_en_to_cn(s.name)
                            if cn:
                                sihua_status[hua] = cn

        is_ming = (palace_zhi_i == ming_branch)
        is_shen = (palace_zhi_i == shen_branch)

        # 大限 - 只取合理年龄范围（≤99岁）
        dx_age = ""
        if iztro_palace and iztro_palace.decadal and iztro_palace.decadal.range:
            dx_range = iztro_palace.decadal.range
            # 只显示合理年龄范围的大限（起始年龄≤99）
            if dx_range[0] <= 99:
                dx_age = f"{dx_range[0]}-{dx_range[1]}岁"

        desc = interpret_place(palace_name, major_stars, minor_stars, sihua_status)

        places.append({
            "宫名": palace_name,
            "宫位": palace_zhi_i,
            "天干": p_gan,
            "地支": p_zhi,
            "主星": major_stars,
            "辅星": minor_stars,
            "小星": adj_stars,
            "四化": sihua_status,
            "解读": desc,
            "是否命宫": is_ming,
            "是否身宫": is_shen,
            "大限": dx_age,
            "庙旺": {s: _get_miaowang_label(s, p_zhi) for s in major_stars + minor_stars if _get_miaowang_label(s, p_zhi)},
        })

    # 安命主/身主
    MINGZHU = {0: "贪狼", 1: "巨门", 2: "禄存", 3: "文曲",
               4: "廉贞", 5: "武曲", 6: "破军", 7: "武曲",
               8: "廉贞", 9: "文曲", 10: "禄存", 11: "巨门"}
    SHENZHU = {0: "火星", 1: "天相", 2: "天梁", 3: "天同",
               4: "天机", 5: "天机", 6: "天梁", 7: "天相",
               8: "火星", 9: "文昌", 10: "文昌", 11: "天同"}

    year_zhi_i = (lunar_year - 4) % 12

    # 提取大运原始数据，提前评分供流年三盘联动使用
    _dayun_extracted = _extract_dayun(chart, ming_branch, daxian_forward, ju_num, solar_year)
    _natal_patterns = _detect_patterns(places, ming_branch, sihua, year_gan)
    _dayun_scored = _dayun_deep_analysis(_dayun_extracted, places, year_gan, natal_patterns=_natal_patterns)

    result = {
        "基本信息": {
            "性别": sex,
            "公历": f"{solar_year}年{solar_month}月{solar_day}日",
            "农历": f"{lunar_year}年{lunar_month}月{lunar_day}日",
        },
        "命宫地支": ZHI[ming_branch],
        "身宫地支": ZHI[shen_branch],
        "五行局": wx,
        "五行局数": ju_num,
        "紫微在": ZHI[ziwei_pos],
        "格局": _natal_patterns,
        "命主": MINGZHU.get(ming_branch, ""),
        "身主": SHENZHU.get(year_zhi_i, ""),
        "十二宫": places,
        "四化": {"年干": year_gan, "化禄": sihua[0], "化权": sihua[1],
                 "化科": sihua[2], "化忌": sihua[3]},
        "大限信息": {"起运年龄": ju_num, "顺逆": "顺行" if daxian_forward else "逆行"},
        # 大运分析（含深度评分，同时传给流年做三盘联动）
        "大运": _dayun_scored,
        # 流年分析（使用已评分的大运，确保地基有效）
        "流年": _calc_liunian(solar_year, year_gan, year_zhi_i, places, ming_branch, shen_branch, _dayun_scored, ln_weights=ln_weights, birth_sihua=sihua, natal_patterns=_natal_patterns),
        # 各宫位飞化分析
        "飞化分析": _calc_feihua(year_gan, places),
        # P1: 财富级别定性评估
        "财富级别": _assess_wealth_level(places, _natal_patterns),
        # P3: 来因宫（月柱地支定位法，与文墨天机一致）
        "来因宫": _find_laiyin_palace(places, year_gan, ZHI[year_zhi_i], lunar_month),
    }

    # ① 八字+紫微联合解读：注入喜用神
    try:
        from . import bazi_core
        fp = bazi_core.get_four_pillars(solar_year, solar_month, solar_day, hour, birthplace="", minute=0)
        bazi = bazi_core.analyze_bazi(fp, sex)
        result["八字联合"] = {
            "日主": bazi["日主五行"],
            "身强身弱": bazi["日主状态"],
            "喜用神": bazi["喜用神"],
            "忌神": bazi.get("忌神", []),
            "提示": f"日主{bazi['日主五行']}{bazi['日主状态']}，喜{'、'.join(bazi['喜用神'])}，行事宜{'、'.join(bazi['喜用神'])}方位/行业",
        }
    except Exception as e:
        result["八字联合"] = {"提示": f"八字暂不可用({type(e).__name__})"}

    # ② 流年逐月简报：当前年+到当前大运结束年(覆盖整个当前大运)
    import datetime
    now_year = datetime.datetime.now().year
    _liunian_raw = result["流年"]
    # 计算当前大运结束年份
    _age = now_year - solar_year
    _liunian_end_year = now_year + 2  # 默认+2年
    for dy in result["大运"]:
        if dy.get('起始年龄', 0) <= _age <= dy.get('结束年龄', 999):
            _liunian_end_year = solar_year + dy.get('结束年龄', _age)
            break
    for ln in _liunian_raw:
        yr = ln["年份"]
        if now_year <= yr <= _liunian_end_year:
            ln["逐月"] = _monthly_brief_compact(yr, places, _zhi_to_for_monthly(places), ming_branch,
                                                   g=GAN[(yr-4)%10], z=ZHI[(yr-4)%12],
                                                   sihua=_SIHUA_TABLE.get(GAN[(yr-4)%10], ["","","",""]))
    
    # ③ LLM 并行批量生成(流年+大运+总结),控总时40s
    # 流年LLM从并行池走，不再串行逐个调用
    import datetime as _dt, time as _time
    _now = _dt.datetime.now().year; _llm_deadline = _time.time() + 25  # EdgeOne 实际限制~30s
    _age = _now - solar_year
    _dy_end = _now
    for dy in result["大运"]:
        if dy.get('起始年龄', 0) <= _age <= dy.get('结束年龄', 999):
            _dy_end = solar_year + dy.get('结束年龄', _age)
            break

    # 仅标记当前大运内的流年需LLM处理(在并行池里统一做)
    _liunian_llm_years = set()
    for ln in _liunian_raw:
        yr = ln["年份"]
        if _now <= yr <= _dy_end:
            _liunian_llm_years.add(yr)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    tasks = []  # [(gen_type, target_ref, ctx), ...]

    # 流年: 当前大运内所有剩余年份(从今年到大运结束)
    for ln in _liunian_raw:
        yr = ln["年份"]
        if yr in _liunian_llm_years:  # _liunian_llm_years 已正确过滤: _now~_dy_end
            tasks.append(("liunian", ln, _build_liunian_context(ln, result, _natal_patterns, solar_year)))

    # 总结（概要，保留）
    tasks.append(("summary", result, _build_summary_context(result, _natal_patterns)))

    # ===== 流年+总结池: 先跑(10s硬上限,剩余时间留给大运) =====
    _pool_deadline = min(_llm_deadline, _time.time() + 10)  # 最多10s
    if tasks and _time.time() < _pool_deadline:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_llm_generate, t[0], t[2]): t for t in tasks if _time.time() < _pool_deadline}
            for fut in as_completed(futures, timeout=max(1, _pool_deadline - _time.time())):
                t = futures[fut]
                try:
                    llm = fut.result()
                    gen_type, target, ctx = t
                    if not llm: continue

                    if gen_type == "liunian":
                        parts = llm.split("|||", 2)
                        def _strip_pfx(s):
                            return s.replace("段三：", "").replace("段二：", "").replace("段一：", "").strip()
                        target["简评"] = _strip_pfx(parts[0])[:50] if parts else ""
                        target["简评详情"] = _strip_pfx(parts[1]) if len(parts) > 1 else ""
                        seg3_raw = _strip_pfx(parts[2]) if len(parts) > 2 else ""
                        if seg3_raw:
                            raw_items = [m.strip() for m in seg3_raw.split("|||") if m.strip()]
                            # 只保留月份标签项(丢弃混入的简评性质长文本)
                            import re as _re_m
                            _MONTH_RE = _re_m.compile(r"^[正一二三四五六七八九十]{1,3}月$|^正二月$|^十一十二月$|^\d{1,2}月$")
                            months_filtered = []
                            for _it in raw_items:
                                _first = (_it.split("：")[0] if "：" in _it else (_it.split(":")[0] if ":" in _it else _it)).strip()
                                if _MONTH_RE.match(_first) and len(_it) <= 80:
                                    months_filtered.append(_it)
                            # 必须≥6个有效月份才覆盖(否则保留模板数据)
                            if len(months_filtered) >= 6:
                                target["逐月"] = months_filtered[:12]

                    elif gen_type == "summary":
                        target["命盘总结"] = llm
                except Exception:
                    pass

    # ===== 大运LLM: 串行调用(流年池已跑10s,剩余~12-15s给大运) =====
    # 1完整(8s) + 2精简(6s) = 14s < 15s ✓
    _age_now = _now - solar_year
    _dayun_pending = []  # 待LLM的大运列表
    for dy in result["大运"]:
        if _time.time() > _llm_deadline: break
        _age_end = dy.get('结束年龄', 0)
        # 跳过完全已过的大运(结束年龄 < 当前年龄)
        if _age_end < _age_now: continue
        # 加入待LLM列表(当前+未来所有)
        _dayun_pending.append(dy)

    # 串行调用大运LLM(避免并发限速,内置重试2次)
    # EdgeOne实际限制~30s: 1完整(8s)+2精简(8s)+总结(6s)=22s✓
    if _dayun_pending:
        import re as _re
        _FIELDS = ["综合", "财富", "事业", "婚姻", "子女", "父母"]
        _pat = r'[\[【](' + '|'.join(_FIELDS) + r')[\]】]'
        _dayun_count = 0
        for _dy in _dayun_pending:
            if _time.time() > _llm_deadline: break
            _dayun_count += 1
            try:
                # 区分任务:前2个完整,后续精简(只输出综合)
                _is_priority = (_dayun_count <= 1)  # 仅当前大运完整LLM
                if _is_priority:
                    _llm = _llm_generate("dayun", _build_dayun_context(_dy, result, _natal_patterns))
                else:
                    _llm = _llm_generate("dayun_brief", _build_dayun_context(_dy, result, _natal_patterns))
                if not _llm: continue
                _field_map = {}
                # 主解析:按【字段名】切分
                _pieces = _re.split(_pat, _llm)
                if len(_pieces) >= 3:
                    for _i in range(1, len(_pieces) - 1, 2):
                        _f_name = _pieces[_i]
                        _content = _pieces[_i + 1].strip() if _i + 1 < len(_pieces) else ''
                        if _f_name in _FIELDS and _f_name not in _field_map:
                            _field_map[_f_name] = _content
                # 备用:按 ||| 切
                if not _field_map:
                    _parts = [p.strip() for p in _llm.split("|||") if p.strip()]
                    for _p in _parts:
                        for _f_name in _FIELDS:
                            if _p.startswith(f"[{_f_name}]") or _p.startswith(f"【{_f_name}】") or _p.startswith(f"{_f_name}:") or _p.startswith(f"{_f_name}："):
                                if _f_name not in _field_map:
                                    _field_map[_f_name] = _p
                                break
                    if "综合" not in _field_map and len(_parts) >= 1:
                        _field_map["综合"] = _parts[0]
                    for _i, _f_name in enumerate(["财富","事业","婚姻","子女","父母"]):
                        if _f_name not in _field_map and _i+1 < len(_parts):
                            _field_map[_f_name] = _parts[_i+1]
                # 写入字段
                if "综合" in _field_map:
                    _dy["综合解读"] = _field_map["综合"][:400]
                for _f_name in ["财富", "事业", "婚姻", "子女", "父母"]:
                    if _f_name in _field_map:
                        _v = _field_map[_f_name]
                        for _pfx in [f"[{_f_name}]", f"【{_f_name}】", f"{_f_name}:", f"{_f_name}："]:
                            if _v.startswith(_pfx):
                                _v = _v[len(_pfx):].strip()
                                break
                        _dy.setdefault("评分", {})[_f_name + "_llm"] = _v[:400]
            except Exception:
                pass

    return result


def _build_liunian_context(ln, result, patterns, solar_year):
    _now = __import__('datetime').datetime.now().year
    dayun_now = _find_dayun_for_age(result["大运"], ln["年份"] - solar_year)
    return {
        "birth": result["基本信息"]["公历"],
        "bazi": result.get("八字联合",{}).get("提示",""),
        "patterns": "、".join([p["name"] for p in patterns[:4]]),
        "ming": result["命宫地支"], "shen": result["身宫地支"],
        "laiyin": result["来因宫"]["宫名"],
        "dayun": dayun_now,
        "ln_gz": ln["流年干支"],
        "career": ln.get("事业分","?"), "wealth": ln.get("财富分","?"),
        "marriage": ln.get("婚姻分","?"), "children": ln.get("子女分","?"),
        "health": ln.get("健康分","?"),
        "ln_brief_old": ln["简评"],
    }

def _build_dayun_context(dy, result, patterns):
    twelves = []
    for p in result["十二宫"]:
        s = "、".join(p.get("主星",[])) or "空宫"
        twelves.append(f'{p["宫名"]}({s})')
    return {
        "birth": result["基本信息"]["公历"],
        "bazi": result.get("八字联合",{}).get("提示",""),
        "patterns": "、".join([p["name"] for p in patterns[:4]]),
        "laiyin": result["来因宫"]["宫名"],
        "dayun_age": f'{dy.get("起始年龄","?")}-{dy.get("结束年龄","?")}岁',
        "dayun_gong": dy.get("大运宫名",""),
        "dayun_stars": "、".join(dy.get("主星",[])),
        "dayun_score": dy.get("综合评分","?"),
        "dayun_rating": dy.get("综合评级","?"),
        "scores": {k: dy.get("评分",{}).get(k,50) for k in ["财富","事业","婚姻","子女","健康","父母"]},
        "twelve": "，".join(twelves),
    }

def _build_summary_context(result, patterns):
    twelves = []
    for p in result["十二宫"]:
        s = "、".join(p.get("主星",[])) or "空宫"
        a = "、".join(p.get("辅星",[])[:3])
        tag = "命宫" if p.get("是否命宫") else "身宫" if p.get("是否身宫") else ""
        twelves.append(f'{p["宫名"]}{tag}({s}{"+"+a if a else ""})')
    return {
        "birth": result["基本信息"]["公历"],
        "bazi": result.get("八字联合",{}).get("提示",""),
        "patterns": "、".join([p["name"] for p in patterns]),
        "laiyin": f'{result["来因宫"]["宫名"]}({result["来因宫"].get("释义","")})',
        "wealth": result.get("财富级别",{}).get("级别","?"),
        "ming": result["命宫地支"], "shen": result["身宫地支"],
        "twelve": "；".join(twelves),
    }


# ===== LLM 调用（委托给共享 llm_client 模块） =====
from .llm_client import llm_call
_last_llm_debug = []  # 诊断用列表

def _llm_generate(gen_type: str, ctx: dict) -> str | None:
    """通用LLM生成器: liunian/dayun/summary，失败返回None回退模板"""
    
    if gen_type == "liunian":
        prompt = f"""你是资深命理分析师。请基于以下流年资料给出分析与建议。

【流年】{ctx.get('ln_gz','')}年。命主生于{ctx.get('birth','')}，{ctx.get('bazi','')[:60]}，格局{ctx.get('patterns','')[:40]}，来因{ctx.get('laiyin','')}，大运{ctx.get('dayun','')}。事业{ctx.get('career','?')} 财富{ctx.get('wealth','?')} 婚姻{ctx.get('marriage','?')} 子女{ctx.get('children','?')} 健康{ctx.get('health','?')}。

【输出格式】严格用|||分隔3段（每段内部不再使用|||）：
段一：50字punchline（事业/财富/婚姻/子女/健康五维各一句）|||
段二：100字逐年分析（结合行业趋势与家庭阶段，给可操作建议）|||
段三：6个双月提醒，月份与内容用全角冒号"："分隔，双月之间用|||分隔：
正二月：15字内提醒|||
三四月：15字内提醒|||
五六月：15字内提醒|||
七八月：15字内提醒|||
九十月：15字内提醒|||
十一十二月：15字内提醒

【要求】专业而务实，落到具体决策（跳槽/投资/备婚/教育/健康计划），口语化不敷衍。
直接输出3段内容。"""
    
    elif gen_type == "dayun":
        sc = ctx.get('scores','')
        prompt = f"""你是资深命理分析师。请用200字概括以下大运的整体走向与5维分析。
大运{ctx.get('dayun_age','')}岁{ctx.get('dayun_gong','')}宫,综合{ctx.get('dayun_score','')}分{ctx.get('dayun_rating','')}。生于{ctx.get('birth','')}年,{ctx.get('bazi','')[:60]},格局{ctx.get('patterns','')[:40]},来因{ctx.get('laiyin','')}。维度:{sc}。
严格用【字段名】前缀分6段(综合100字+5维各50字),结合时代背景,口语化务实。直接输出。"""

    elif gen_type == "dayun_brief":
        # 精简版:只输出【综合】段,200字内,用于未来非优先大运(避免超时)
        sc = ctx.get('scores','')
        prompt = f"""你是命理分析师。请用150-200字概括以下大运的整体走向和重点关注领域:
大运{ctx.get('dayun_age','')}岁{ctx.get('dayun_gong','')}宫,综合{ctx.get('dayun_score','')}分。生于{ctx.get('birth','')}年,{ctx.get('bazi','')[:60]},格局{ctx.get('patterns','')[:40]}。维度:{sc}。
用【综合】前缀开头,1段文字不需分段,结合时代背景,口语化务实。直接输出。"""
    
    elif gen_type == "summary":
        prompt = f"""你是资深命理分析师。请为以下命盘写一段180字全局总结。

生于{ctx.get('birth','')}，{ctx.get('bazi','')}，格局：{ctx.get('patterns','')}，来因宫：{ctx.get('laiyin','')}，财富级别：{ctx.get('wealth','')}。命宫{ctx.get('ming','')}，身宫{ctx.get('shen','')}。十二宫：{ctx.get('twelve','')}

从三个层面组织：①核心天赋与优势赛道 ②一生主要课题与转折点 ③中晚年生活形态建议。结合时代背景（行业周期/社会老龄化/技术变革）给出务实的人生规划参考。语气专业、有洞察力、有温度，直接输出。"""
    else:
        return None
    
    # 缓存key：简洁格式,gen_type+年龄
    import time as _t
    try:
        age = ctx.get('dayun_age', ctx.get('ln_gz', ''))
        ck = f"zw:{gen_type}:{hash(str(age))}:v4"  # v4 让旧缓存失效
    except:
        ck = f"zw:{gen_type}:{int(_t.time())}"
    max_tok = 800  # 统一 max_tokens(800对summary已验证可用,1200不稳定)
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


def _zhi_to_for_monthly(places):
    d = {}
    for p in places: d[p.get("宫位")] = p
    return d


def _find_dayun_for_age(dayun_list, age):
    for dy in dayun_list:
        if dy.get('起始年龄', 0) <= age <= dy.get('结束年龄', 999):
            return f"{dy.get('起始年龄')}-{dy.get('结束年龄')}岁,{dy.get('大运宫名','')},{dy.get('综合评级','')},{dy.get('综合评分','')}分"
    return ""


def _monthly_brief_compact(year, places, zhi_to_p, ming_branch, g="", z="", sihua=None):
    """流年逐月简报 — 纯模板(不调LLM,省token)"""
    MONTHS = [("正月",0), ("二月",1), ("三月",2), ("四月",3), ("五月",4), ("六月",5),
              ("七月",6), ("八月",7), ("九月",8), ("十月",9), ("十一月",10), ("十二月",11)]
    ZHI_CHARS = list("子丑寅卯辰巳午未申酉戌亥")
    MONTH_ZHI = ["寅","卯","辰","巳","午","未","申","酉","戌","亥","子","丑"]  # 正月寅

    # 太岁在命盘中的位置
    year_zhi_ch = z if z else ""
    year_zhi_i = ZHI_CHARS.index(year_zhi_ch) if year_zhi_ch in ZHI_CHARS else -1
    taisui_palace = zhi_to_p.get(year_zhi_i, {})  # 流年命宫所在的本命宫位
    taisui_pn = taisui_palace.get("宫名", "")

    # 构建 流年命宫 → 逐月顺时针映射
    PALACE_ORDER = ["命宫","兄弟","夫妻","子女","财帛","疾厄","迁移","交友","官禄","田宅","福德","父母"]
    taisui_order_idx = PALACE_ORDER.index(taisui_pn) if taisui_pn in PALACE_ORDER else 0

    # 宫名 → 宫位数据
    name_to_palace = {p.get("宫名"): p for p in places}

    # 宫位主题
    TOPICS = {
        "命宫":"自我运势","兄弟":"人际合作","夫妻":"感情婚姻","子女":"子女创意",
        "财帛":"财富进账","疾厄":"健康注意","迁移":"出行变动","交友":"社交人脉",
        "官禄":"事业关键","田宅":"房产家事","福德":"精神享受","父母":"长辈事宜"
    }
    # 6维影响语
    IMPACT = {
        "命宫":"自我状态变化，主导全年基调",
        "兄弟":"合伙协作或人际变动",
        "夫妻":"感情生活起伏",
        "子女":"子女或创作相关事件",
        "财帛":"财务进出的关键期",
        "疾厄":"健康状况需关注",
        "迁移":"出行或环境变迁",
        "交友":"社交圈或人脉变化",
        "官禄":"事业工作关键节点",
        "田宅":"家宅或不动产",
        "福德":"精神世界与心态",
        "父母":"长辈或家庭事务"
    }

    # 流年四化
    sihua_stars = sihua or ["","","",""]
    s_lu, s_quan, s_ke, s_ji = sihua_stars

    months = []
    for label, month_idx in MONTHS:
        # 该月对应的本命宫位
        pn = PALACE_ORDER[(taisui_order_idx + month_idx) % 12]
        p = name_to_palace.get(pn, {})

        topic = TOPICS.get(pn, pn)
        impact = IMPACT.get(pn, "")

        # 星曜
        stars = p.get("主星", [])
        aux = p.get("辅星", [])
        all_s = list(dict.fromkeys(stars + aux))
        star_str = "、".join(all_s[:3]) if all_s else ""

        # 四化高亮
        highlights = []
        for s, hl in [(s_lu,"化禄·吉"), (s_quan,"化权·成"), (s_ke,"化科·名"), (s_ji,"化忌·慎")]:
            if s and (s in stars or s in aux):
                highlights.append(hl)

        # 宫位分(若存在)
        pal_score = p.get("分", "")
        pal_score_str = f"（{pal_score}分）" if pal_score else ""

        # 组装：正月：命宫(贪狼化忌) 化忌·慎 — 自我状态变化，主导全年基调
        note = f"{label}：{pn}{pal_score_str}"
        if star_str: note += f"({star_str})"
        if highlights: note += " " + " ".join(highlights)
        note += f" — {impact}"
        months.append(note)

    return months


def interpret_place(place_name, stars, aux_stars_here, sihua_status):
    """宫位解读"""
    if not stars:
        desc = f"【{place_name}】此宫无主星，借对宫星曜论命.行事需借力使势，不宜单打独斗."
    else:
        star_descs = {
            "紫微": "紫微坐镇，为人尊贵，有领导气质，一生多遇贵人提携.",
            "天机": "天机入驻，聪明善变，谋略过人，喜研究玄学技艺.",
            "太阳": "太阳光辉，热情开朗，光明正大，利公职外务.",
            "武曲": "武曲临宫，刚毅果决，利武职金融，财运颇佳.",
            "天同": "天同照命，温和随缘，福泽深厚，一生少风波.",
            "廉贞": "廉贞坐宫，能文能武，性格刚烈，宜公职法律.",
            "天府": "天府临宫，稳重保守，有财库，善理财储蓄.",
            "太阴": "太阴入驻，温柔细腻，利房地产，女命更吉.",
            "贪狼": "贪狼坐宫，多才多艺，桃花旺盛，宜演艺交际.",
            "巨门": "巨门临宫，口才出众，善辩是非，宜教学法律.",
            "天相": "天相入驻，谨慎稳重，利辅佐之职，衣食无缺.",
            "天梁": "天梁照宫，老成持重，利教化慈善，有寿元.",
            "七杀": "七杀临宫，开创力强，性格刚猛，宜军警武职.",
            "破军": "破军坐宫，破旧立新，冒险进取，一生多变化.",
        }
        desc = f"【{place_name}】"
        for sn in stars:
            desc += star_descs.get(sn, f"{sn}入宫，影响命局.")

    # 辅星补充
    if aux_stars_here:
        aux_descs = {
            "左辅": "左辅助之，贵人暗助.",
            "右弼": "右弼辅之，人缘甚佳.",
            "文昌": "文昌入宫，利文职考试.",
            "文曲": "文曲照命，才华出众.",
            "禄存": "禄存守宫，财禄丰厚.",
            "天魁": "天魁贵人，逢凶化吉.",
            "天钺": "天钺贵人，暗中助力.",
            "擎羊": "擎羊入宫，需防刑伤.",
            "陀罗": "陀罗入宫，行事拖延.",
            "火星": "火星入宫，性急冲动.",
            "铃星": "铃星入宫，暗藏波折.",
            "地空": "地空入宫，精神空虚.",
            "地劫": "地劫入宫，破耗难免.",
        }
        for a in aux_stars_here:
            if a in aux_descs:
                desc += aux_descs[a]

    # 四化补充
    sihua_descs = {
        "化禄": "本宫化禄，利财运发展.",
        "化权": "本宫化权，权势增加.",
        "化科": "本宫化科，名利双收.",
        "化忌": "本宫化忌，需防波折."
    }
    for k, v in sihua_status.items():
        if k in sihua_descs:
            desc += sihua_descs[k]

    return desc






# ===== 大运深度分析（多维度评分） =====
# 参照：陆斌兆《紫微斗数讲义》、倪海厦《天纪》、王亭之《安星法》
#
# 评分逻辑：
# 1. 每个大运宫位对应一个"大运命宫"，由此重新排十二宫
# 2. 根据大运命宫及三方四正的主星组合评分
# 3. 四化飞入各宫影响加分/减分
# 4. 辅星（六吉/六煞）调节

# ----- 星曜基础分值表 -----
# 格式: "星名": {维度: 分值}
# 维度: 财富/事业/婚姻/子女/父母
# 分值范围: -30 ~ +40, 基准50分, 最终 clamp 到 20-100

def _score_to_percentile(score, dim, age=35):
    """将分数映射到同龄层百分位"""
    if age < 20: age = 20
    if age >= 60: age = 55
    decade = f"{(age//10)*10}-{(age//10)*10+9}"
    tbl = _PERCENTILE_TABLE.get(decade, _PERCENTILE_TABLE["30-39"])
    dim_data = tbl.get(dim, tbl.get("事业", {}))
    if not dim_data: return ""
    if score >= dim_data.get("p90", 99): return "前10%"
    if score >= dim_data.get("p75", 99): return "前25%"
    if score >= dim_data.get("p50", 99): return "前50%"
    if score >= dim_data.get("p25", 99): return "后50%"
    return "后25%"

# ----- 大运三方四正对应维度 -----
# 大运命宫三方：命宫-财帛-官禄 为核心三角
# 对宫迁移影响外务
# 大运夫妻宫、子女宫、父母宫、福德宫 分别影响对应维度

def _score_dayun(dayun_palace_stars, dayun_sihua, sanfang_stars, dim_palaces, start_age=None, dy_gan='', dy_zhi_name='', places=None):
    """
    计算单个大运的五维评分

    参数:
      dayun_palace_stars: 大运命宫的主星+辅星列表
      dayun_sihua: 大运命宫的四化状态 dict (本命)
      sanfang_stars: 三方四正星曜汇总 {宫名: [主星列表]}
      dim_palaces: 各维度对应宫位星曜 {维度: {主星:[], 辅星:[], 四化:{}}}
      dy_gan: 大运天干（用于计算大运四化参与评分）
      dy_zhi_name: 大运地支名（用于凶星座宫位情景调节）
      places: 十二宫完整数据（用于找大运四化星落宫）

    返回:
      {维度: 分数} 和 {维度: 解读文本}
    """
    DIMS = ["财富", "事业", "婚姻", "子女", "父母", "健康"]
    # 少年大运（起始年龄<20）跳过婚姻和子女维度，但保留健康
    youth_skip = start_age is not None and start_age < 20
    if youth_skip:
        DIMS = ["财富", "事业", "父母", "健康"]
    DIM_PALACE_MAP = {
        "财富": "财帛宫",
        "事业": "官禄宫",
        "婚姻": "夫妻宫",
        "子女": "子女宫",
        "父母": "父母宫",
        "健康": "疾厄宫",
    }
    STAR_TABLES = {
        "财富": _STAR_WEALTH, "事业": _STAR_CAREER,
        "婚姻": _STAR_MARRIAGE, "子女": _STAR_CHILDREN,
        "父母": _STAR_PARENTS, "健康": _STAR_HEALTH,
    }

    scores = {}
    descs = {}

    for dim in DIMS:
        base = 50  # 基准分（v5.0: 社会平均值锚定，50底+分析加成→60-80中位）

        # 1) 大运命宫主星对该维度的贡献（权重0.6，防主星独力破百）
        main_stars = dayun_palace_stars.get("主星", [])
        aux_stars = dayun_palace_stars.get("辅星", [])
        star_table = STAR_TABLES[dim]

        dim_detail_parts = []
        star_bonus = 0
        for s in main_stars:
            v = star_table.get(s, 0)
            star_bonus += int(v * 0.6)
            if abs(v) >= 15:
                sign = "+" if v > 0 else ""
                dim_detail_parts.append("%s%s(%s%d)" % (s, "主星" if v > 0 else "耗泄", sign, v))

        # 2) 三方四正中对应维度宫位的星曜贡献（权重0.5）
        dp = dim_palaces.get(dim, {})
        dp_main = dp.get("主星", [])
        dp_aux = dp.get("辅星", [])
        dp_sihua = dp.get("四化", {})
        dp_bonus = 0
        for s in dp_main:
            v = star_table.get(s, 0)
            dp_bonus += int(v * 0.5)
            if abs(v) >= 12:
                sign = "+" if v > 0 else ""
                dim_detail_parts.append("%s宫%s(%s%d)" % (DIM_PALACE_MAP[dim], s, sign, int(v * 0.7)))

        # 3) 辅星调节（含凶星宫位情景调节 —— 火空则发、金空则鸣等）
        aux_bonus = 0
        for a in aux_stars + dp_aux:
            adj = _AUX_ADJUST.get(a, {})
            bonus = adj.get(dim, 0)
            # 宫位情景调节：凶星在特定宫位凶性减弱甚至转为正面
            if dy_zhi_name and a in _AUX_PALACE_MODIFIER:
                palace_mod = _AUX_PALACE_MODIFIER[a].get(dy_zhi_name, {})
                if dim in palace_mod:
                    modifier = palace_mod[dim]
                    if modifier < 0:
                        # 负数表示凶星转为正面（如火空则发）
                        bonus = int(abs(bonus) * abs(modifier))
                    else:
                        bonus = int(bonus * modifier)
            aux_bonus += bonus

        # 4) 四化影响（本命四化 + 大运天干四化）
        sihua_bonus = 0
        all_sihua = {}
        all_sihua.update(dayun_sihua)
        all_sihua.update(dp_sihua)

        # --- 大运天干四化（权重0.6，参半于本命四化1.0）---
        if dy_gan and places:
            dy_sihua_stars = _SIHUA_TABLE.get(dy_gan, ["","","",""])
            dy_sihua_labels = _SIHUA_LABELS
            for hi, star_name in enumerate(dy_sihua_stars):
                if not star_name: continue
                hua_name = dy_sihua_labels[hi]
                # 找大运四化星在本命十二宫的落宫
                for p in places:
                    if star_name in p.get("主星",[]) + p.get("辅星",[]):
                        hua_adj_dy = _SIHUA_DIM.get(hua_name, {})
                        dy_sihua_bonus = int(hua_adj_dy.get(dim, 0) * 0.6)
                        sihua_bonus += dy_sihua_bonus
                        if abs(hua_adj_dy.get(dim, 0)) >= 8:
                            dim_detail_parts.append("%s(大运%s)(%s%d)" % (star_name, hua_name, "+" if hua_adj_dy.get(dim, 0) > 0 else "", int(hua_adj_dy.get(dim, 0) * 0.6)))
                        break

        # 权忌同宫检测：倪海厦"有权能制忌"——权忌同宫时权星优先
        has_quan = any("化权" in h for h in all_sihua.keys())
        has_ji = any("化忌" in h for h in all_sihua.keys())
        quan_ji_same_palace = has_quan and has_ji  # 同一宫位同时有权和忌

        for hua_type, star_name in all_sihua.items():
            hua_adj = _SIHUA_DIM.get(hua_type, {})
            bonus = hua_adj.get(dim, 0)
            # 权忌同宫：权×1.5，忌×0.5
            if quan_ji_same_palace:
                if "化权" in hua_type:
                    bonus = int(bonus * 1.5)
                elif "化忌" in hua_type:
                    bonus = int(bonus * 0.5)
            sihua_bonus += bonus
            if abs(hua_adj.get(dim, 0)) >= 10:
                dim_detail_parts.append("%s%s(%s%d)" % (star_name, hua_type, "+" if hua_adj.get(dim, 0) > 0 else "", hua_adj.get(dim, 0)))

        # 汇总
        total = base + star_bonus + dp_bonus + aux_bonus + sihua_bonus
        total = max(20, min(95, total))  # clamp 20-95，人间无完美之运
        scores[dim] = total

        # 解读文本
        level = "大吉" if total >= 85 else "中吉" if total >= 75 else "小吉" if total >= 65 else "偏弱" if total >= 50 else "凶"
        dim_desc = "%s评级：%s（%d分）" % (dim, level, total)
        if dim_detail_parts:
            dim_desc += "。" + "、".join(dim_detail_parts[:5])

        # 补充维度专项解读
        dim_desc += "。" + _dim_interpret(dim, total, main_stars, dp_main, dp_sihua)
        descs[dim] = dim_desc

    return scores, descs


def _dim_interpret(dim, score, ming_stars, dim_stars, dim_sihua):
    """生成维度专项解读，融合三家之言"""
    # 通用解读模板
    if score >= 85:
        base = {
            "财富": "此运财源广进，宜把握投资机遇，天府武曲太阴等财星得力，陆斌兆云：「财星守命，十年丰足」.",
            "事业": "此运事业通达，贵人扶助，紫微天府太阳坐镇，倪海厦云：「命宫得令，三方会吉，十年宏图可展」.",
            "婚姻": "此运婚姻和美，感情顺遂，太阴天同主柔顺，陆斌兆云：「夫妻宫吉，鸾凤和鸣」.",
            "子女": "此运子女有成，亲子融洽，天同天府主福泽，子女宫吉庆有余.",
            "父母": "此运与长辈缘分深厚，得荫庇助力，天梁太阳主尊长，父母宫安稳.",
        }
    elif score >= 75:
        base = {
            "财富": "此运财运平稳，量入为出，不宜冒进投机，守成为上策.",
            "事业": "此运事业渐进，踏实经营可获提升，宜稳中求变.",
            "婚姻": "此运婚姻平稳，偶有磨擦但可化解，宜多包容沟通.",
            "子女": "此运子女运中等，需多关心教育引导，不可放任.",
            "父母": "此运与父母关系尚可，宜多尽孝道，注意长辈健康.",
        }
    elif score >= 60:
        base = {
            "财富": "此运财运起伏，需谨慎理财，忌赌博投机，王亭之云：「煞星守财，宜守不宜攻」.",
            "事业": "此运事业多变，宜蛰伏蓄力，不宜轻率跳槽，需防小人.",
            "婚姻": "此运婚姻有波折，需防口舌是非，倪海厦云：「夫妻宫化忌，感情多考验」.",
            "子女": "此运子女运平淡，亲子间易生隔阂，需耐心沟通.",
            "父母": "此运与父母缘分较薄，宜多关怀长辈，注意健康问题.",
        }
    elif score >= 35:
        base = {
            "财富": "此运财运不佳，破耗之象，陆斌兆云：「地劫地空入财帛，十年虚耗」.",
            "事业": "此运事业受阻，进退两难，宜忍辱负重，蓄势待发.",
            "婚姻": "此运婚姻不利，感情多舛，需防分离变故，宜互相体谅.",
            "子女": "此运子女运较差，亲子矛盾增多，需以柔克刚.",
            "父母": "此运父母运势低，长辈健康堪忧，宜多陪伴照护.",
        }
    else:
        base = {
            "财富": "此运财劫重重，大耗之象，倪海厦云：「化忌冲财，倾囊可待」，宜保守为上.",
            "事业": "此运事业多艰，需防官非诉讼，不宜冒进，韬光养晦.",
            "婚姻": "此运婚姻大凶，感情裂痕深重，需防婚变离散.",
            "子女": "此运子女运凶，亲子关系紧张，宜以退为进，切勿强硬.",
            "父母": "此运父母宫逢大煞，长辈恐有灾厄，宜尽孝及时.",
        }

    desc = base.get(dim, "")

    # 根据特定星曜追加解读
    all_stars = ming_stars + dim_stars
    if "禄存" in all_stars and dim == "财富":
        desc += " 禄存入财帛，正财稳固，不宜贪求偏财."
    if "化禄" in dim_sihua and dim == "财富":
        desc += " 化禄入财帛，进财有道，此运可适度投资."
    if "化忌" in dim_sihua:
        desc += " 化忌入此宫，需防破局，凡事谨慎."
    if "七杀" in all_stars and dim == "事业":
        desc += " 七杀主开创，事业有冲劲但风险亦大，需量力而行."
    if "破军" in all_stars and dim in ["婚姻", "财富"]:
        desc += " 破军主变动，此运多波折，宜以静制动."
    if "贪狼" in all_stars and dim == "婚姻":
        desc += " 贪狼入夫妻宫，桃花纷扰，需守正防诱惑."
    if "天机" in all_stars and dim == "事业":
        desc += " 天机主谋略，此运宜以智取胜，不宜蛮干."

    return desc


def _dayun_deep_analysis(dayun_list, places, year_gan, natal_patterns=None):
    """
    对每个大运进行深度五维评分分析 + 本命格局激活分析

    参数:
      dayun_list: _extract_dayun() 返回的大运列表
      places: 十二宫完整数据
      year_gan: 年干
      natal_patterns: 本命格局列表（用于判断大运是否激活本命格局）

    返回:
      在每个大运数据中增加 "评分"、"深度解读"、"格局激活" 字段
    """
    # 宫名→宫位数据映射
    palace_by_name = {}
    for p in places:
        palace_by_name[p["宫名"]] = p

    # 大运命宫对应的十二宫重排映射
    # 大运命宫 = 原命宫偏移到该大运宫位
    # 三方四正：命宫-官禄-财帛-迁移
    # 对大运而言，以大运所在宫为大运命宫，
    # 其三方为：大运官禄（大运命宫偏移8位）、大运财帛（偏移4位）、大运迁移（偏移6位）

    DIM_PALACE_OFFSET = {
        "财富": 4,   # 财帛宫 = 命宫逆数4位
        "事业": 8,   # 官禄宫 = 命宫逆数8位
        "婚姻": 2,   # 夫妻宫 = 命宫逆数2位
        "子女": 3,   # 子女宫 = 命宫逆数3位
        "父母": 11,  # 父母宫 = 命宫逆数11位
        "健康": 5,   # 疾厄宫 = 命宫逆数5位（v6.0: 流年健康基于疾厄非父母）
    }

    # 从 places 中构建宫位索引到宫名映射
    zhi_to_palace = {}
    for p in places:
        zhi_to_palace[p["宫位"]] = p

    # 命宫地支索引
    ming_zhi = None
    for p in places:
        if p.get("是否命宫"):
            ming_zhi = p["宫位"]
            break
    if ming_zhi is None:
        ming_zhi = 0


    for dy in dayun_list:
        # 大运宫位地支索引
        dy_zhi = None
        for idx in range(12):
            if ZHI[idx] == dy["宫位"]:
                dy_zhi = idx
                break
        if dy_zhi is None:
            dy["评分"] = {}
            dy["深度解读"] = {}
            continue

        # 大运命宫星曜（即该大运宫位上的星）
        dayun_palace_data = zhi_to_palace.get(dy_zhi, {})
        dayun_palace_stars = {
            "主星": dayun_palace_data.get("主星", []),
            "辅星": dayun_palace_data.get("辅星", []),
        }

        # 大运命宫四化
        dayun_sihua = dayun_palace_data.get("四化", {})

        # 三方四正星曜
        sanfang_stars = {}
        # 三方：大运命宫(dy_zhi)、大运官禄((dy_zhi-8)%12)、大运财帛((dy_zhi-4)%12)
        # 对宫迁移: (dy_zhi-6)%12
        sanfang_zhis = [dy_zhi, (dy_zhi - 8) % 12, (dy_zhi - 4) % 12, (dy_zhi - 6) % 12]
        sanfang_names = ["命宫", "官禄宫", "财帛宫", "迁移宫"]
        for i, sz in enumerate(sanfang_zhis):
            sp = zhi_to_palace.get(sz, {})
            sanfang_stars[sanfang_names[i]] = sp.get("主星", [])

        # 各维度对应宫位
        dim_palaces = {}
        for dim, offset in DIM_PALACE_OFFSET.items():
            dp_zhi = (dy_zhi - offset) % 12
            dp = zhi_to_palace.get(dp_zhi, {})
            dim_palaces[dim] = {
                "主星": dp.get("主星", []),
                "辅星": dp.get("辅星", []),
                "四化": dp.get("四化", {}),
            }

        # 计算评分（传入起始年龄，少年大运自动跳过婚育维度）
        start_age = dy.get("起始年龄", 99)
        dy_gan = dy.get("天干", "")
        dy_zhi_name = dy.get("宫位", "")  # 大运地支名，用于凶星座情景调节
        scores, descs = _score_dayun(dayun_palace_stars, dayun_sihua, sanfang_stars, dim_palaces, start_age, dy_gan=dy_gan, dy_zhi_name=dy_zhi_name, places=places)

        # 综合评分 (加权平均)；少年大运自动调节权重
        if start_age < 20:
            weights = {"财富": 0.35, "事业": 0.35, "父母": 0.30}
        else:
            weights = {"财富": 0.25, "事业": 0.25, "婚姻": 0.20, "子女": 0.15, "父母": 0.15}
        total_score = 0
        for dim, w in weights.items():
            total_score += scores.get(dim, 50) * w
        total_score = int(round(total_score))

        # 综合评级（多套句式去模板化）
        import random
        seed = total_score + start_age
        random.seed(seed)
        if total_score >= 85:
            overall = "大吉"
            descs_pool = [
                "此运极佳，诸事顺遂，宜积极进取。陆斌兆云：「大运得令，十年风光」.",
                "十年佳运当头，贵人提携、机遇涌现，当放开手脚大展宏图.",
                "运势登峰，此十年是你人生的高光时刻，宜抓紧每一个风口.",
                "天时地利具备，此运顺势而为便可水到渠成，不必过度操劳.",
            ]
            overall_desc = random.choice(descs_pool)
        elif total_score >= 75:
            overall = "中吉"
            descs_pool = [
                "此运良好，虽有波折不碍大局，稳中求进。倪海厦云：「三方会吉，不失为佳运」.",
                "运势稳步上扬，十年向好值得一搏，守住主业伺机扩展.",
                "此运整体向上，偶有小挫不必惊慌，大方向是好的.",
            ]
            overall_desc = random.choice(descs_pool)
        elif total_score >= 60:
            overall = "小吉"
            descs_pool = [
                "此运平稳，无大起大落，宜守成待时。王亭之云：「平运宜守，勿贪急进」.",
                "十年平淡如水，虽无大风浪亦无大惊喜，习惯就好——积累即是胜利.",
                "此运不温不火，适合沉淀积累而非冒险扩张，静待下一波机遇.",
            ]
            overall_desc = random.choice(descs_pool)
        elif total_score >= 50:
            overall = "偏弱"
            descs_pool = [
                "此运偏弱，需防破耗是非，退守自保，不宜冒进.",
                "十年低谷期，养精蓄锐比盲目冲撞明智——熬过去就是春天.",
                "此运阻力较大，宜精细化管理，避开高风险决策，小步慢走.",
            ]
            overall_desc = random.choice(descs_pool)
        else:
            overall = "大凶"
            descs_pool = [
                "此运整体运势凶险，诸事多阻，宜韬光养晦，避凶趋吉。倪海厦云：「大运逢煞，十年坎坷，唯忍字可渡」.",
                "运逢低谷，十年荆棘路——但请记住：最低处正是反弹的起点，守心为上.",
                "此运多艰，不可轻举妄动，以退为进、以守为攻是最佳策略.",
            ]
            overall_desc = random.choice(descs_pool)

        # 追加命宫主星对大运的影响
        ming_main = dayun_palace_stars.get("主星", [])
        
        # 大运宫位名+主题（深Seek风格个性化描述）
        dy_palace_name = dayun_palace_data.get("宫名", "")
        PALACE_THEME = {
            "命宫": "自我重塑之运，个人形象与社会角色的关键十年",
            "兄弟": "手足同僚之运，人际关系、合作联盟定基调",
            "夫妻": "婚姻感情之运，配偶缘分与合作关系为主线",
            "子女": "子嗣创意之运，生育、教育、投资项目为主题",
            "财帛": "财富积累之运，正偏财运与资产配置定乾坤",
            "疾厄": "健康安身之运，身体为本，养生保健为要务",
            "迁移": "出行变动之运，外出发展、驿马奔波为主题",
            "交友": "人际交往之运，朋友下属、社会资源为主线",
            "官禄": "事业升迁之运，职场地位、权力角逐为主题",
            "田宅": "家宅房产之运，不动产、家庭根基定基调",
            "福德": "精神享受之运，内心满足、福报桃花为主题",
            "父母": "长辈荫庇之运，父母健康、上下级关系为主线",
        }
        if ming_main:
            star_summary = "、".join(ming_main)
            overall_desc += " 大运命宫主星" + star_summary + "坐镇"
            if len(ming_main) >= 2:
                overall_desc += "，星曜汇聚，力量集中"
            # 特殊组合
            if "紫微" in ming_main and "天府" in ming_main:
                overall_desc += "。紫府同宫，帝座有库，此运权财两旺，大为吉利"
            elif "太阳" in ming_main and "太阴" in ming_main:
                overall_desc += "。日月同辉，此运名利双收，但需防光芒过盛反招嫉"
            elif "武曲" in ming_main and "贪狼" in ming_main:
                overall_desc += "。武贪同宫，此运欲望与行动力并重，利开拓不利守成"
        else:
            overall_desc += "。大运命宫无主星，借对宫星曜，行事需借力使势"

        # ----- 本命格局激活分析 -----
        if natal_patterns:
            # 收集大运三方四正内所有星曜（用于判断格局激活）
            all_active_stars = set()
            for sz in sanfang_zhis:
                sp = zhi_to_palace.get(sz, {})
                all_active_stars.update(sp.get("主星", []))
                all_active_stars.update(sp.get("辅星", []))
            
            # 收集大运命宫四化
            dy_active_sihua = dayun_palace_data.get("四化", {})
            
            activations = _get_active_patterns(natal_patterns, list(all_active_stars), dy_active_sihua)
            
            if activations:
                good_acts = [(n, d) for n, l, d in activations if l == "good" and d == "充分激活"]
                warn_acts = [(n, d) for n, l, d in activations if l == "warn" and d in ("充分激活", "部分激活")]
                
                if good_acts:
                    pat_names = "、".join([n for n, d in good_acts[:2]])
                    overall_desc += f"。本命{pat_names}在此运被充分激活，格局之力加持，此十年尤为关键"
                if warn_acts:
                    pat_names = "、".join([n for n, d in warn_acts[:2]])
                    overall_desc += f"，但需注意{pat_names}在此运被引动，行事多加谨慎"
                
                # 存储激活信息
                dy["格局激活"] = [{"name": n, "level": l, "degree": d} for n, l, d in activations]
            else:
                dy["格局激活"] = []

        # 注入大运宫位主题到综合解读开头
        if dy_palace_name and dy_palace_name in PALACE_THEME:
            overall_desc = f"行{dy_palace_name}大运——{PALACE_THEME[dy_palace_name]}。" + overall_desc

        dy["评分"] = scores
        dy["综合评分"] = total_score
        dy["综合评级"] = overall
        dy["综合解读"] = overall_desc
        dy["深度解读"] = descs
        dy["大运宫名"] = dy_palace_name

    return dayun_list


# ===== 大运分析 =====
def _extract_dayun(chart, ming_branch, daxian_forward, ju_num, solar_year):
    """从iztro-py提取大运详细数据"""
    result = []
    ZHI = list("子丑寅卯辰巳午未申酉戌亥")
    GAN  = list("甲乙丙丁戊己庚辛壬癸")

    for p in chart.palaces:
        if not (p.decadal and p.decadal.range):
            continue
        rng = p.decadal.range
        if rng[0] > 99:
            continue
        branch_idx = _parse_branch(p.earthly_branch)
        stem_idx  = _parse_stem(p.heavenly_stem)

        major = []
        if p.major_stars:
            for s in p.major_stars:
                cn = _star_en_to_cn(s.name)
                if cn:
                    major.append(cn)
        minor = []
        if p.minor_stars:
            for s in p.minor_stars:
                cn = _star_en_to_cn(s.name)
                if cn:
                    minor.append(cn)

        desc = "【%s宫大运 %d-%d岁】" % (ZHI[branch_idx], rng[0], rng[1])
        if major:
            desc += "主星：" + "、".join(major) + "。"
        if minor:
            desc += "辅星：" + "、".join(minor) + "。"

        result.append({
            "宫位":   ZHI[branch_idx],
            "天干":   GAN[stem_idx],
            "地支":   ZHI[branch_idx],
            "起始年龄": rng[0],
            "结束年龄": rng[1],
            "主星":   major,
            "辅星":   minor,
            "解读":   desc,
        })

    result.sort(key=lambda x: x["起始年龄"])
    return result


# ===== 流年分析（增强版） =====
def _calc_liunian(solar_year, year_gan, year_zhi_i, places, ming_branch, shen_branch, dayun_list=None, ln_weights=None, birth_sihua=None, natal_patterns=None):
    """
    计算流年分析，包含四化评分、白话简评、四维指引 + 本命格局激活分析。

    参数:
      solar_year: 出生公历年
      year_gan: 年干
      year_zhi_i: 年支索引 (0-11)
      places: 十二宫数据列表
      ming_branch: 命宫地支索引
      natal_patterns: 本命格局列表（用于判断流年是否激活本命格局）

    返回:
      [{"年份": int, "流年干支": str, "纳音": str, "十神": str,
        "评分": int, "简评": str,
        "事业": int, "财富": int, "感情": int, "健康": int,
        "四维指引": str}, ...]
    """
    ZHI  = list("子丑寅卯辰巳午未申酉戌亥")
    GAN  = list("甲乙丙丁戊己庚辛壬癸")

    # 纳音
    NAYIN_MAP = {
        "甲子":"海中金","乙丑":"海中金","丙寅":"炉中火","丁卯":"炉中火",
        "戊辰":"大林木","己巳":"大林木","庚午":"路旁土","辛未":"路旁土",
        "壬申":"剑锋金","癸酉":"剑锋金","甲戌":"山头火","乙亥":"山头火",
        "丙子":"涧下水","丁丑":"涧下水","戊寅":"城头土","己卯":"城头土",
        "庚辰":"白蜡金","辛巳":"白蜡金","壬午":"杨柳木","癸未":"杨柳木",
        "甲申":"泉中水","乙酉":"泉中水","丙戌":"屋上土","丁亥":"屋上土",
        "戊子":"霹雳火","己丑":"劈雳火","庚寅":"松柏木","辛卯":"松柏木",
        "壬辰":"长流水","癸巳":"长流水","甲午":"沙中金","乙未":"沙中金",
        "丙申":"山下火","丁酉":"山下火","戊戌":"平地木","己亥":"平地木",
        "庚子":"壁上土","辛丑":"壁上土","壬寅":"金箔金","癸卯":"金箔金",
        "甲辰":"覆灯火","乙巳":"覆灯火","丙午":"天河水","丁未":"天河水",
        "戊申":"大驿土","己酉":"大驿土","庚戌":"钗钏金","辛亥":"钗钏金",
        "壬子":"桑柘木","癸丑":"桑柘木","甲寅":"大溪水","乙卯":"大溪水",
        "丙辰":"沙中土","丁巳":"沙中土","戊午":"天上火","己未":"天上火",
        "庚申":"石榴木","辛酉":"石榴木","壬戌":"大海水","癸亥":"大海水",
    }

    # 流年天干十神（以年干为基准）
    SHISHEN_TABLE = {
        "甲":{"甲":"比肩","乙":"劫财","丙":"食神","丁":"伤官","戊":"偏财","己":"正财","庚":"七杀","辛":"正官","壬":"偏印","癸":"正印"},
        "乙":{"甲":"劫财","乙":"比肩","丙":"伤官","丁":"食神","戊":"正财","己":"偏财","庚":"正官","辛":"七杀","壬":"正印","癸":"偏印"},
        "丙":{"甲":"偏印","乙":"正印","丙":"比肩","丁":"劫财","戊":"食神","己":"伤官","庚":"偏财","辛":"正财","壬":"七杀","癸":"正官"},
        "丁":{"甲":"正印","乙":"偏印","丙":"劫财","丁":"比肩","戊":"伤官","己":"食神","庚":"正财","辛":"偏财","壬":"正官","癸":"七杀"},
        "戊":{"甲":"七杀","乙":"正官","丙":"偏印","丁":"正印","戊":"比肩","己":"劫财","庚":"食神","辛":"伤官","壬":"偏财","癸":"正财"},
        "己":{"甲":"正官","乙":"七杀","丙":"正印","丁":"偏印","戊":"劫财","己":"比肩","庚":"伤官","辛":"食神","壬":"正财","癸":"偏财"},
        "庚":{"甲":"偏财","乙":"正财","丙":"七杀","丁":"正官","戊":"偏印","己":"正印","庚":"比肩","辛":"劫财","壬":"食神","癸":"伤官"},
        "辛":{"甲":"正财","乙":"偏财","丙":"正官","丁":"七杀","戊":"正印","己":"偏印","庚":"劫财","辛":"比肩","壬":"伤官","癸":"食神"},
        "壬":{"甲":"食神","乙":"伤官","丙":"偏财","丁":"正财","戊":"七杀","己":"正官","庚":"偏印","辛":"正印","壬":"比肩","癸":"劫财"},
        "癸":{"甲":"伤官","乙":"食神","丙":"正财","丁":"偏财","戊":"正官","己":"七杀","庚":"正印","辛":"偏印","壬":"劫财","癸":"比肩"},
    }

    # 流年四化表（引用模块级 _SIHUA_TABLE，流年/大运/本命共用同一表）

    # 星曜对各维度贡献（正值＝吉，负值＝凶）
    DIM_STAR = {
        "财富": {"天府":28,"武曲":25,"太阴":22,"禄存":28,"贪狼":10,"紫微":18,"天相":15,
                 "破军":-15,"七杀":-10,"巨门":-12,"廉贞":-8,"太阳":8,"天同":8,"天机":5,"天梁":5},
        "事业": {"紫微":35,"天府":28,"太阳":25,"天相":22,"武曲":20,"天机":15,"廉贞":12,
                 "天梁":10,"贪狼":10,"太阴":12,"七杀":8,"破军":5,"天同":8,"巨门":5},
        "婚姻": {"太阴":25,"天同":22,"天府":20,"天相":18,"天梁":15,"紫微":10,"太阳":12,
                 "贪狼":-12,"七杀":-18,"破军":-20,"廉贞":-12,"巨门":-15,"武曲":-8,"天机":5},
        "子女": {"天同":22,"天府":20,"天相":18,"太阴":15,"天梁":12,"紫微":10,"太阳":8,
                 "破军":-15,"七杀":-12,"廉贞":-10,"贪狼":-8,"巨门":-5,"武曲":-5,"天机":5},
        "健康": {"天梁":25,"天同":22,"天府":18,"天相":15,"紫微":12,"太阳":10,"太阴":10,
                 "破军":-15,"七杀":-12,"廉贞":-10,"巨门":-8,"贪狼":-8,"武曲":-5,"天机":3},
    }

    # 地支冲合
    def _chong_he(z1, z2):
        """返回地支关系"""
        diff = (z1 - z2) % 12
        if diff == 6: return "冲", -1, "太岁冲命宫，动荡多变，宜冷静应对"
        if diff == 0: return "值", 1, "太岁值命宫，变动之年，宜顺势而为"
        if diff in (4, 8): return "合", 2, "太岁与命宫相合，贵人助力，行事顺遂"
        if diff in (3, 9): return "害", -2, "太岁与命宫相害，暗藏是非"
        return "平", 0, "太岁无重大冲合，运势平稳"

    def _score_to_stars(s):
        # v3.0: 60分=3星（合格），50=2星，70=4星，80=5星
        if s >= 80: return 5
        if s >= 70: return 4
        if s >= 60: return 3
        if s >= 50: return 2
        return 1

    def _brief(y, g, z, ny, ss, sihua_stars, chong_str, sihua_info, dayun_ctx=None,
               ln_palace_name='', ln_palace_main=None, dy_foundation=None, dims=None):
        """倪海厦《天纪》风格简评 v2.9 —— 六层分析：大运→命宫→四化→忌星→冲合→锦囊+冲突对比"""
        s_lu = sihua_stars[0]; s_quan = sihua_stars[1]; s_ke = sihua_stars[2]; s_ji = sihua_stars[3]
        parts = []

        # ═══ 1) 大运基调 ── 去模板化：多变句式 ═══
        if dayun_ctx and dayun_ctx.get('palace_name'):
            dy_rating = dayun_ctx.get('rating', '平运')
            rating_vary = {
                "大吉": ["此运极盛，诸事可期","大运当头，十年风光","运势登峰，宜抓紧良机"],
                "中吉": ["运势上扬，稳中求进","此运向好，值得一搏","十年佳运，顺势而为"],
                "小吉": ["平稳十年，守成为上","此运安稳，稳扎稳打","平平淡淡即是福"],
                "偏弱": ["此运偏弱，宜退守","十年低谷，熬过即是春","运弱之年，养精蓄銳"],
                "大凶": ["运势凶险，韬光养晦","大运不利，以守为攻","十年荆棘，忍字当头"],
            }
            dy_desc = rating_vary.get(dy_rating, ["运势平稳"] )[zhi_idx % 3]
            dy_age = dayun_ctx.get('age_range', '')
            dy_palace = dayun_ctx['palace_name']
            # 随机句式
            templates = [
                f"{dy_age}{dy_palace}大运，{dy_desc}",
                f"{dy_palace}运中，{dy_desc}",
                f"此十年行{dy_palace}宫，{dy_desc}",
            ]
            parts.append(templates[y % 3])
        elif dayun_ctx:
            parts.append("大运平稳，无大风浪")

        # ═══ 2) 流年命宫 ── 太岁宫坐镇星曜，年度定调 ═══
        ln_tone_map = {
            "命宫": "流年命宫坐本命，今年你就是主角",
            "财帛": "流年命宫落财帛，财运是全年主题",
            "官禄": "流年命宫落官禄，事业今年定基调",
            "夫妻": "流年命宫落夫妻，感情婚姻是重点",
            "子女": "流年命宫落子女，孩子创意为主轴",
            "田宅": "流年命宫入田宅，房产家事为主轴",
            "迁移": "流年命宫在迁移，外出远行有机遇",
            "疾厄": "流年命宫入疾厄，健康是今年的功课",
            "福德": "流年命宫在福德，精神享受为主题",
            "交友": "流年命宫入交友，人脉圈子新变化",
            "父母": "流年命宫在父母，长辈关系是重点",
            "兄弟": "流年命宫入兄弟，手足合作是主轴",
        }
        if ln_palace_name and ln_palace_main:
            main_str = "、".join(ln_palace_main[:2])
            # 主星特性速写
            STAR_CHAR = {
                "紫微":"有贵人撑腰","天府":"稳扎稳打能守财","天相":"左右逢源","七杀":"敢拼敢闯",
                "破军":"破旧立新","贪狼":"多才多艺桃花旺","廉贞":"精明能干","太阳":"热情主动",
                "太阴":"细腻谋划","天机":"机变灵活点子多","天同":"随和享福","天梁":"稳重有担当",
                "武曲":"果断执行力强","巨门":"能言善辩","文曲":"聪明伶俐","文昌":"文采出众",
                "禄存":"自带财库","擎羊":"冲劲十足","陀罗":"慢工细活","火星":"雷厉风行",
                "铃星":"沉着冷静","地空":"灵感迸发","地劫":"另辟蹊径",
                "左辅":"得人相助","右弼":"贵人提携","天魁":"遇难成祥","天钺":"暗中有助",
                "天马":"奔波求财",
            }
            star_traits = []
            for s in ln_palace_main[:2]:
                trait = STAR_CHAR.get(s, "")
                if trait: star_traits.append(f"{s}({trait})")
            trait_str = "、".join(star_traits) if star_traits else main_str
            
            ln_tone = ln_tone_map.get(ln_palace_name, f"流年命宫坐{ln_palace_name}")
            if g[0] in "甲乙":
                ln_tone += "，开春就有转机"
            parts.append(f"{ln_tone}，{trait_str}，定全年基调")
        else:
            parts.append(f"流年命宫平稳，随大势而行")

        # ═══ 3) 四化应事层 ── 禄权科各有其应 ═══
        def _palace_effect(star, hua_type):
            p_name = sihua_info.get(star, ("?", "?"))[0] if star in sihua_info else ""
            if not p_name or p_name == "?": return ""

            lu_effects = {
                "财帛": f"{star}禄入财帛，正偏财一起来，钱包鼓",
                "官禄": f"{star}禄在官禄，事业财运双旺",
                "夫妻": f"{star}禄照夫妻，感情升温好年份",
                "子女": f"{star}禄入子女，孩子好事多",
                "田宅": f"{star}禄照田宅，房产家运旺",
                "疾厄": f"{star}禄入疾厄，身体安康少病痛",
                "福德": f"{star}禄照福德，心情愉快精神好",
                "命宫": f"{star}禄入命宫，机会自己送上门",
                "迁移": f"{star}禄在迁移，越动越有机遇",
                "交友": f"{star}禄入交友，朋友带来财运",
                "兄弟": f"{star}禄照兄弟，手足合作有利",
                "父母": f"{star}禄照父母，长辈关照得力",
            }
            # 星曜组合增效
            star_combo = ""
            if hua_type == "化禄" and star in ("太阳","太阴") and p_name == "命宫":
                star_combo = "，日月之光加持，一年顺遂"
            quan_effects = {
                "官禄": f"{star}权在官禄，职场说了算，升主管当领导",
                "命宫": f"{star}权入命宫，掌控全局的一年，自己说了算",
                "财帛": f"{star}权在财帛，赚钱有话语权，投资可主动出击",
                "夫妻": f"{star}权入夫妻，家里你说了算但别太强势",
                "迁移": f"{star}权在迁移，出门在外展拳脚，往外闯有收获",
                "交友": f"{star}权入交友，朋友当中你是核心，号召力强",
            }
            ji_effects = {
                "夫妻": f"{star}忌入你的夫妻宫，感情容易翻旧账，今年少提往事",
                "财帛": f"{star}忌入财帛，花钱冲动管不住，今年守财为上",
                "官禄": f"{star}忌在官禄，工作上小人多口舌多，低调行事",
                "疾厄": f"{star}忌入疾厄，身体要注意，别熬夜，有病早查",
                "子女": f"{star}忌入子女，孩子淘气或生育需谨慎，少折腾",
                "田宅": f"{star}忌入田宅，家宅不宁或房产不顺，别买卖",
                "命宫": f"{star}忌入命宫，诸事多阻的一年，以守为攻别硬来",
                "福德": f"{star}忌入福德，心烦易怒，找方式解压别闷着",
                "迁移": f"{star}忌在迁移，外出小心意外纠纷，少管闲事",
                "交友": f"{star}忌入交友，朋友借钱别答应，别替人作保",
                "父母": f"{star}忌照父母，长辈那边多点耐心，别顶嘴",
                "兄弟": f"{star}忌入兄弟，手足之间少计较，钱的事说清楚",
            }
            if hua_type == "化禄" and p_name in lu_effects:
                return lu_effects[p_name] + star_combo
            elif hua_type == "化权" and p_name in quan_effects:
                return quan_effects[p_name]
            elif hua_type == "化忌" and p_name in ji_effects:
                return ji_effects[p_name]
            elif hua_type == "化科" and p_name:
                ke_map = {"命宫":f"{star}科入命宫，名声鹊起贵人提携",
                         "官禄":f"{star}科在官禄，专业受认可",
                         "夫妻":f"{star}科照夫妻，感情和睦名声好",
                         "财帛":f"{star}科在财帛，以名气得财",
                         "迁移":f"{star}科在迁移，外出遇贵人"}
                return ke_map.get(p_name, f"{star}科在{p_name}，名声贵人提升")
            return ""

        # 禄星应事
        if s_lu and s_lu in sihua_info:
            txt = _palace_effect(s_lu, "化禄")
            if txt: parts.append(txt)

        # 权星 / 科星
        if s_quan and s_quan in sihua_info and len(parts) < 6:
            txt = _palace_effect(s_quan, "化权")
            if txt: parts.append(txt)
        if s_ke and s_ke in sihua_info and len(parts) < 6:
            txt = _palace_effect(s_ke, "化科")
            if txt: parts.append(txt)

        # ═══ 4) 忌星警告 ── 点名忌星落宫，敲警钟 ═══
        if s_ji and s_ji in sihua_info:
            txt = _palace_effect(s_ji, "化忌")
            if txt:
                # 添加化解建议
                ji_name = sihua_info[s_ji][0]
                remedies = {"夫妻":"多沟通少翻旧账","财帛":"管住钱包别冲动","官禄":"少说多做防小人",
                           "疾厄":"早睡早起体检去","子女":"多陪孩子少说教","命宫":"凡事三思别硬闯",
                           "迁移":"出门低调莫逞能","交友":"独善其身少应酬"}
                remedy = remedies.get(ji_name, "保守行事")
                parts.append(f"{txt}，化解之道：{remedy}")

        # ═══ 5) 太岁冲合 ── 年度关键提醒 ═══
        chong_parts = {
            "冲": "太岁冲动，变动难免——搬家换工出远门都是解法，别死守",
            "值": "太岁值命，天时在你这边，大胆出击",
            "合": "太岁六合，贵人天降，躺平都有好事",
            "害": "太岁相害，暗箭需防，合同多看两遍",
        }
        for kw, tip in chong_parts.items():
            if chong_str.startswith(kw):
                if len(parts) < 7:
                    parts.append(tip)
                break
        else:
            if len(parts) < 7:
                parts.append("年支平和，不贪不急就是赢")

        # ═══ 5.5) 冲突对比 ── 最好vs最差维度的叙事张力 ═══
        if dims and len(parts) < 7:
            # 找到最高和最低维度
            sorted_dims = sorted(dims.items(), key=lambda x: x[1], reverse=True)
            best_dim, best_score = sorted_dims[0]
            worst_dim, worst_score = sorted_dims[-1]
            gap = best_score - worst_score

            if gap >= 15:  # 差距足够大才有冲突感
                dim_label = {"事业":"事业运","财富":"财运","婚姻":"感情运","子女":"子女运","健康":"健康"}
                best_label = dim_label.get(best_dim, best_dim)
                worst_label = dim_label.get(worst_dim, worst_dim)

                contrasts = {
                    ("事业","婚姻"): ["典型的事业冲刺年——但别忘了家里还有人等你", "职场上红火，感情上别交白卷"],
                    ("事业","财富"): ["事业名声在外，钱包却没跟上——今年别只赚吆喝"],
                    ("事业","健康"): ["拼事业的代价是身体——倪师提醒：留得青山在"],
                    ("财富","婚姻"): ["钱来了感情淡了——典型的'赚了钱输了家'"],
                    ("财富","健康"): ["财旺身弱之年——有钱赚也得有命花，别透支"],
                    ("婚姻","事业"): ["感情升温事业降温——今年重心偏家偏情"],
                    ("婚姻","财富"): ["桃花旺了但钱包瘪——感情用钱要节制"],
                    ("婚姻","健康"): ["情场得意，身体别得意忘形"],
                    ("子女","婚姻"): ["孩子好但夫妻间别忽略沟通"],
                    ("健康","事业"): ["身体是红灯，别硬扛——今年健康第一"],
                    ("健康","财富"): ["身体有恙则财运难聚——养好身体再赚钱"],
                }
                key = (best_dim, worst_dim)
                rev_key = (worst_dim, best_dim)
                contrast = contrasts.get(key) or contrasts.get(rev_key)
                if contrast:
                    parts.append(contrast[zhi_idx % len(contrast)])
                else:
                    # 通用冲突句式
                    parts.append(f"{best_label}正旺但{worst_label}拖后腿——倪师曰：禄忌对冲之年，得一头失一头，分清轻重")

        # ═══ 7) 行动锦囊 + 人情味收尾 ═══
        tips_pool = []
        mood = ""
        if s_ji:
            tips_pool = ["忌星之年以守为攻，倪师常言：不动如山", "稳字当头，今年最忌贪快", "熬过此年便是春天"]
            mood = ["扛住了就是蜕变的开始","今年的苦是明年甜的代价","有时候慢就是最快的速度"][zhi_idx%3]
        elif s_lu:
            tips_pool = ["禄临之年该出手时就出手", "好运不等人，大胆往前闯", "春耕秋收——今年种什么都收成"]
            mood = ["这是你该发光的一年","别忘了感恩帮你的人","旺年更要惜福"][zhi_idx%3]
        elif avg >= 75:
            tips_pool = ["顺势而为，借力打力", "守住优势，扩大战果"]
            mood = "好年景就像顺风船——别乱转舵"
        elif dims["事业"] >= 70 and dims["财富"] < 50:
            tips_pool = ["事业红火但钱包吃紧，少折腾多存粮"]
            mood = "名声是长期资产，现金是短期氧气——都重要"
        elif "冲" in chong_str:
            tips_pool = ["冲则动、动则变、变则通", "主动求变胜过被动挨打"]
            mood = "变动之年，唯一的危险是不敢动"
        elif "合" in chong_str:
            tips_pool = ["天地合气顺势而为即可", "贵人就在身边，开口就有"]
            mood = "今年的运气像顺水推舟——不用太费力"
        else:
            tips_pool = ["平平淡淡才是真", "守好本分该来的自然会来"]
            mood = ["平淡也是福","积蓄力量也是一种前进","种子在地下的时候是看不见的"][zhi_idx%3]
        parts.append(tips_pool[zhi_idx % len(tips_pool)])
        if mood:
            parts.append(mood)

        return "。".join(parts[:9]) + "。"

    def _guide(dims, age=35):
        """五维指引 + 社会百分位参照"""
        lines = []
        dmap = {"事业":"事业","财富":"财运","婚姻":"婚姻","子女":"子女","健康":"健康"}
        for k in ["事业","财富","婚姻","子女","健康"]:
            v = dims[k]
            pct = _score_to_percentile(v, k, age)
            if v >= 80:
                lines.append("%s★★★★★ 大吉(%s)" % (dmap[k], pct))
            elif v >= 70:
                lines.append("%s★★★★☆ 中吉(%s)" % (dmap[k], pct))
            elif v >= 60:
                lines.append("%s★★★☆☆ 小吉(%s)" % (dmap[k], pct))
            elif v >= 50:
                lines.append("%s★★☆☆☆ 合格(%s)" % (dmap[k], pct))
            else:
                lines.append("%s★☆☆☆☆ 偏弱(%s)" % (dmap[k], pct))
        return "；".join(lines[:5])

    # 构建宫位索引：地支索引 → 宫位数据
    _zhi_to_palace = {}
    for p in places:
        zi = p.get("宫位", -1)
        if zi >= 0:
            _zhi_to_palace[zi] = p

    # 宫名 → 评分维度映射（紫微斗数全书十二宫对应人生领域）
    PALACE_DIM_MAP = {
        "命宫": None,      # 命宫影响全局，不单独对应某维度
        "兄弟": None,
        "夫妻": "婚姻",     # 夫妻宫 → 婚姻
        "子女": "子女",     # 子女宫 → 子女
        "财帛": "财富",     # 财帛宫 → 财富
        "疾厄": "健康",     # 疾厄宫 → 健康
        "迁移": None,
        "交友": None,
        "官禄": "事业",     # 官禄宫 → 事业
        "田宅": "财富",     # 田宅宫 → 财富（不动产）
        "福德": "健康",     # 福德宫 → 健康（精神健康）
        "父母": None,
    }

    # 四化落宫对维度的加分（《天纪》原则：禄在哪个宫，哪个领域旺）
    # 四化落宫对维度的加分（《天纪》原则：禄在哪个宫，哪个领域旺）
    # v2.8 提升权重：拉开分数分布，不再50分扎堆
    SIHUA_PALACE_BONUS = {
        "化禄": {"婚姻":25,"子女":20,"财富":28,"健康":18,"事业":22},
        "化权": {"婚姻":12,"子女":12,"财富":15,"健康":12,"事业":28},
        "化科": {"婚姻":18,"子女":18,"财富":12,"健康":15,"事业":15},
        "化忌": {"婚姻":-20,"子女":-18,"财富":-25,"健康":-20,"事业":-20},
    }

    # 三方四正宫位偏移：对宫(6)，官禄(4)，财帛(8)
    SANFANG_OFFSETS = [0, 6, 4, 8]

    current_year = datetime.datetime.now().year

    items = []

    # 流年范围扩展到出生年+120岁（完整人生周期），不再截止当前年
    for y in range(solar_year, solar_year + 120):
        gan_idx = (y - 4) % 10
        zhi_idx = (y - 4) % 12
        g = GAN[gan_idx]
        z = ZHI[zhi_idx]

        # 纳音
        gz_key = "%s%s" % (g, z)
        ny = NAYIN_MAP.get(gz_key, "")

        # 十神
        ss = SHISHEN_TABLE.get(year_gan, {}).get(g, "?")
        ss_label = "比劫" if ss in ("比肩","劫财") else "印星" if ss in ("正印","偏印") else \
                    "食伤" if ss in ("食神","伤官") else "财星" if ss in ("正财","偏财") else \
                    "官杀" if ss in ("正官","七杀") else "?"

        # 流年四化
        sihua_stars = _SIHUA_TABLE.get(g, ["","","",""])

        # 太岁与命宫的冲合
        chong_type, chong_val, chong_desc = _chong_he(zhi_idx, ming_branch)
        # 0) 大运上下文 —— 三盘联动的关键桥梁
        current_age = y - solar_year
        dayun_ctx = None
        dy_palace_name = ''
        dy_dim = None
        if dayun_list:
            for dy in dayun_list:
                if dy.get('起始年龄', 0) <= current_age <= dy.get('结束年龄', 999):
                    dy_zhi_char = dy.get('宫位', '')
                    dy_zhi_i = ZHI.index(dy_zhi_char) if dy_zhi_char in ZHI else -1
                    dy_palace_data = _zhi_to_palace.get(dy_zhi_i, {})
                    dy_palace_name = dy_palace_data.get('宫名', '')
                    dy_dim = PALACE_DIM_MAP.get(dy_palace_name)
                    dy_stars = dy_palace_data.get('主星', []) + dy_palace_data.get('辅星', [])
                    dy_score = dy.get('综合评分', 50)
                    dy_quality = 1 if dy_score >= 65 else -1 if dy_score < 40 else 0
                    dayun_ctx = {
                        'age_range': f"{dy.get('起始年龄',0)}-{dy.get('结束年龄',0)}岁",
                        'gz': dayun_ctx_gz if 'dayun_ctx_gz' in dir() else '',
                        'palace_name': dy_palace_name,
                        'dim': dy_dim,
                        'rating': dy.get('综合评级', '平运'),
                        'score': dy.get('综合评分', 50),
                        'quality': dy_quality,
                        'stars': dy_stars[:3],
                        'dim_scores': dy.get('评分', {}),  # 大运五维逐分
                        'dy_sihua': {},  # will be filled below with real 大运天干四化
                    }
                    # 大运天干地支
                    dy_gan = dy.get('天干', '')
                    dy_zhi = dy.get('地支', '')
                    gz_str = f"{dy_gan}{dy_zhi}" if dy_gan and dy_zhi else ''
                    # 查找大运宫位在places中的位置
                    for p in places:
                        if p.get('宫位') == dy_zhi_i:
                            dy_gan = p.get('天干', '') or dy_gan
                    dayun_ctx['gz'] = f"{dy_gan}{dy_zhi}" if dy_gan and dy_zhi else ''
                    # 计算真正的大运天干四化（不是本命落宫四化）
                    dy_sihua_real = {}
                    if dy_gan:
                        dy_4h_stars = _SIHUA_TABLE.get(dy_gan, ["","","",""])
                        for hi, star_name in enumerate(dy_4h_stars):
                            if star_name:
                                dy_sihua_real[_SIHUA_LABELS[hi]] = star_name
                    dayun_ctx['dy_sihua'] = dy_sihua_real
                    dayun_ctx['dy_gan'] = dy_gan  # keep for reference
                    break


        # ===== 流年五维度评分 v4.0: 分析驱动 =====
        # 原则: 大运定趋势(70%), 流年四化做加减, 最终调和太岁
        # 每维度 = 大运地基 + 四化落宫分析 + 流年命宫分析 + 太岁调节

        DIMS = ["事业","财富","婚姻","子女","健康"]
        dims = {d: 50 for d in DIMS}

        # 大运→流年维度映射
        DY_TO_LN = {"财富":"财富","事业":"事业","婚姻":"婚姻","子女":"子女","健康":"健康"}

        STAR_TABLES_LN = {
            "事业": _STAR_CAREER, "财富": _STAR_WEALTH,
            "婚姻": _STAR_MARRIAGE, "子女": _STAR_CHILDREN,
            "健康": _STAR_HEALTH,
        }

        # ═══ ① 大运地基 (62%) + 大运四化叠加 (25%) ═══
        dy_dim_scores = dayun_ctx.get('dim_scores', {}) if dayun_ctx else {}
        dy_sihua = dayun_ctx.get('dy_sihua', {}) if dayun_ctx else {}
        dy_foundation = {}
        for dy_dim, ln_dim in DY_TO_LN.items():
            dy_base = dy_dim_scores.get(dy_dim, 50)
            foundation = int(dy_base * 0.62)
            dims[ln_dim] = foundation
            dy_foundation[ln_dim] = foundation
        # 《全书》：大运四化是"体"，叠加对流年的影响（权重0.30）
        for hua_type, star_name in dy_sihua.items():
            for dim in DIMS:
                dims[dim] += int(_SIHUA_DIM.get(hua_type, {}).get(dim, 0) * 0.30)

        # ═══ ①b 生年四化叠加 (12%) ═══
        # 注：本命四化已内含在大运地基中(大运评分已用1.0权重)，流年中降为点缀
        if birth_sihua:
            for hi, star_name in enumerate(birth_sihua):
                if not star_name: continue
                hua_name = ["化禄","化权","化科","化忌"][hi]
                # 找生年四化星在本命十二宫中的落宫
                for p_data in _zhi_to_palace.values():
                    if star_name in p_data.get("主星",[]) + p_data.get("辅星",[]):
                        for dim in DIMS:
                            dims[dim] += int(_SIHUA_DIM.get(hua_name, {}).get(dim, 0) * 0.12)
                        break

        # ═══ ①c 庙旺系数调节（使用模块级令东来权威表）═══

        # ④⑦层中星曜贡献应用庙旺系数（后续在四化和命宫分析中生效）
        mi_wang_cache = {}
        def _mi_wang_coeff(star):
            if star not in mi_wang_cache:
                for p_data in _zhi_to_palace.values():
                    if star in p_data.get("主星",[]) + p_data.get("辅星",[]):
                        zhi = ZHI[list(_zhi_to_palace.keys())[list(_zhi_to_palace.values()).index(p_data)]]
                        # Simplified: use the palace's own zhi
                        break
                else:
                    mi_wang_cache[star] = 1.0
                    return 1.0
            return mi_wang_cache.get(star, 1.0)
        # Rebuild: search for star and find its location
        for star in set([s for p in _zhi_to_palace.values() for s in p.get("主星",[]) + p.get("辅星",[])]):
            for zhi_v, p_data in _zhi_to_palace.items():
                if star in p_data.get("主星",[]) + p_data.get("辅星",[]):
                    mi_wang_cache[star] = _get_miaowang_coeff(star, ZHI[zhi_v])
                    break

        # ═══ ② 流年四化落宫分析 ═══
        sihua_info = {}
        for hi, hua_name in enumerate(["化禄","化权","化科","化忌"]):
            star_name = sihua_stars[hi]
            if not star_name: continue
            # 找星曜所在本命宫位
            for p_data in _zhi_to_palace.values():
                if star_name in p_data.get("主星",[]) + p_data.get("辅星",[]):
                    p_name = p_data.get("宫名","")
                    sihua_info[star_name] = (p_name, 1.0)
                    # 四化主效应（权重0.45：流年四化是"应事"层，不应压倒本命和大运）
                    for dim in DIMS:
                        dims[dim] += int(_SIHUA_DIM.get(hua_name, {}).get(dim, 0) * 0.45)
                    # 星曜自身在各维度的贡献（轻量加权+庙旺系数）
                    mw = mi_wang_cache.get(star_name, 1.0)
                    for dim, tbl in STAR_TABLES_LN.items():
                        dims[dim] += int(tbl.get(star_name, 0) * 0.15 * mw)
                    break

        # ═══ ③ 流年命宫分析 ═══
        ln_palace = _zhi_to_palace.get(zhi_idx)
        ln_palace_name = ''
        ln_palace_main = []
        if ln_palace:
            ln_palace_name = ln_palace.get("宫名", "")
            ln_palace_main = ln_palace.get("主星", [])
            # 流年命宫主星对五维的贡献（庙旺系数）
            for s in ln_palace_main:
                mw = mi_wang_cache.get(s, 1.0)
                for dim, tbl in STAR_TABLES_LN.items():
                    dims[dim] += int(tbl.get(s, 0) * 0.25 * mw)
            # 辅星贡献（含宫位情景调节）
            for a in ln_palace.get("辅星", []):
                adj = _AUX_ADJUST.get(a, {})
                for dim in DIMS:
                    bonus = adj.get(dim, 0)
                    # 凶星宫位情景调节
                    if z and a in _AUX_PALACE_MODIFIER:
                        palace_mod = _AUX_PALACE_MODIFIER[a].get(z, {})
                        if dim in palace_mod:
                            modifier = palace_mod[dim]
                            if modifier < 0:
                                bonus = int(abs(bonus) * abs(modifier))
                            else:
                                bonus = int(bonus * modifier)
                    dims[dim] += int(bonus * 0.40)

        # ═══ ④ 三方四正联动（轻量） ═══
        SANFANG_OFFSETS = [0, 6, 4, 8]
        if ln_palace:
            for offset in SANFANG_OFFSETS:
                sf_zhi = (zhi_idx - offset) % 12
                sf_palace = _zhi_to_palace.get(sf_zhi)
                if sf_palace:
                    sf_dim = PALACE_DIM_MAP.get(sf_palace.get("宫名", ""))
                    if sf_dim:
                        for s in sf_palace.get("主星", []):
                            tbl = STAR_TABLES_LN.get(sf_dim, {})
                            mw = mi_wang_cache.get(s, 1.0)
                            dims[sf_dim] += int(tbl.get(s, 0) * 0.20 * mw)

        # ═══ ⑤ 太岁冲合调节 ═══
        for dim in DIMS:
            dims[dim] += chong_val * 2

        # ═══ ⑤b 身宫触发 ═══
        # 《全书》：身宫为后天安身之所，流年命宫遇身宫时影响加倍
        shen_zhi_name = ZHI[shen_branch] if shen_branch is not None else None
        if shen_zhi_name and _zhi_to_palace.get(zhi_idx, {}).get("宫名", ""):
            shen_palace = None
            for p_data in _zhi_to_palace.values():
                if p_data.get("是否身宫"):
                    shen_palace = p_data
                    break
            if shen_palace and _zhi_to_palace.get(zhi_idx, {}) is shen_palace:
                # 流年命宫 = 身宫 → 各维度 +5
                for dim in DIMS:
                    dims[dim] += 5

        # ═══ ⑥ 夹持: 《全书》体用协调保护 ═══
        if dayun_ctx:
            for dy_dim, ln_dim in DY_TO_LN.items():
                dy_v = dy_dim_scores.get(dy_dim, 50)
                if dy_v >= 80:
                    dims[ln_dim] = max(dims[ln_dim], 58)  # 大运极强→流年至少3星
                elif dy_v >= 65:
                    dims[ln_dim] = max(dims[ln_dim], 50)  # 大运小吉→流年不低于2星
                elif dy_v < 50:
                    dims[ln_dim] = min(dims[ln_dim], 72)  # 大运弱→流年上限

        # Clamp（全书：忌虽凶不致死，禄虽喜不逆天）
        for dim in DIMS:
            dims[dim] = max(32, min(92, dims[dim]))

        # ═══ ⑦ 大运天花板：流年围绕大运波动，±20为合理区间 ═══
        if dayun_ctx:
            for dy_dim, ln_dim in DY_TO_LN.items():
                dy_v = dy_dim_scores.get(dy_dim, 50)
                # 流年维分上限 = min(92, 大运维分 + 22)
                # 大运50→上限72, 大运70→上限92, 大运90→上限92
                ceiling = min(92, dy_v + 15)
                dims[ln_dim] = min(dims[ln_dim], ceiling)

        avg = int(sum(dims.values()) / 5)

        # 组装简评所需上下文
        brief_ctx = (y, g, z, ny, ss, sihua_stars, chong_desc, sihua_info, dayun_ctx,
                     ln_palace_name, ln_palace_main, dy_foundation, dims)

        brief = _brief(*brief_ctx)

        # ----- 本命格局在流年中的激活分析 -----
        if natal_patterns and ln_palace:
            # 收集流年命宫及其三方四正的星曜和四化
            ln_zhi = ln_palace.get("宫位", -1)
            if ln_zhi >= 0:
                ln_active_stars = set(ln_palace_main)
                ln_active_stars.update(ln_palace.get("辅星", []))
                # 加入流年迁移宫（对宫）的星曜
                dup_idx = (ln_zhi - 6) % 12
                dup_palace = _zhi_to_palace.get(dup_idx, {})
                ln_active_stars.update(dup_palace.get("主星", []))
                ln_active_stars.update(dup_palace.get("辅星", []))
                
                ln_active_sihua = ln_palace.get("四化", {})
                # 也合并迁移宫四化
                dup_sihua = dup_palace.get("四化", {})
                if dup_sihua:
                    ln_active_sihua = {**ln_active_sihua, **dup_sihua}
                
                ln_activations = _get_active_patterns(natal_patterns, list(ln_active_stars), ln_active_sihua)
                if ln_activations:
                    # 取最高优先级的充分激活good格局
                    fully_good = [n for n, l, d in ln_activations if l == "good" and d == "充分激活"]
                    fully_warn = [n for n, l, d in ln_activations if l == "warn" and d == "充分激活"]
                    if fully_good:
                        brief = brief[:-1] + "。本命" + "、".join(fully_good[:1]) + "流年引动，格局之光加持" + "。"
                    elif fully_warn:
                        brief = brief[:-1] + "。本命" + "、".join(fully_warn[:1]) + "流年引动，宜谨慎行事" + "。"
            else:
                ln_activations = []

        # 五维指引
        guide = _guide(dims, age=y - solar_year)

        items.append({
            "年份": y,
            "流年干支": gz_key,
            "纳音": ny,
            "十神": ss,
            "十神类": ss_label,
            "评分": avg,
            "简评": brief,
            "事业": _score_to_stars(dims["事业"]),
            "财富": _score_to_stars(dims["财富"]),
            "婚姻": _score_to_stars(dims["婚姻"]),
            "子女": _score_to_stars(dims["子女"]),
            "健康": _score_to_stars(dims["健康"]),
            "事业分": dims["事业"],
            "财富分": dims["财富"],
            "婚姻分": dims["婚姻"],
            "子女分": dims["子女"],
            "健康分": dims["健康"],
            "四维指引": guide,
        })

    return items


# ===== 各宫位飞化分析 =====
def _calc_feihua(year_gan, places):
    """各宫位飞化分析——按年干四化，分析化曜飞入何宫"""
    GAN  = list("甲乙丙丁戊己庚辛壬癸")
    ZHI  = list("子丑寅卯辰巳午未申酉戌亥")

    hua_list = _SIHUA_TABLE.get(year_gan, ["", "", "", ""])
    feihua = []

    for i in range(4):
        star_name = hua_list[i]
        if not star_name:
            continue
        label = _SIHUA_LABELS[i]
        # 找化曜所在宫位
        from_palace = ""
        for p in places:
            if star_name in p.get("主星", []) or star_name in p.get("辅星", []):
                from_palace = p["宫名"]
                break
        if not from_palace:
            from_palace = "命宫"  # 默认

        feihua.append({
            "四化":   label,
            "星曜":   star_name,
            "来源宫": from_palace,
            "解读":   "%s：%s%s，由%s飞出，影响该宫运势。" % (label, star_name, label[1:], from_palace)
        })

    return feihua


# ===== 财富级别评估 =====
def _assess_wealth_level(places, patterns):
    score = 50; details = []; caibo = tianzhai = None
    for p in places:
        if p.get("宫名") == "财帛": caibo = p
        if p.get("宫名") == "田宅": tianzhai = p
    if caibo:
        cb_stars = caibo.get("主星", []); cb_aux = caibo.get("辅星", []); cb_sihua = caibo.get("四化", {})
        ws = {"天府":18,"武曲":15,"太阴":12,"禄存":15,"紫微":10,"贪狼":8}
        for s in cb_stars:
            if s in ws: score += ws[s]; details.append(f"{s}坐财帛")
        if "化禄" in cb_sihua: score += 20; details.append(f"{cb_sihua['化禄']}化禄入财帛")
        for s in cb_aux + cb_stars:
            if s in {"陀罗":-10,"地空":-12,"地劫":-12,"擎羊":-8}: score += {"陀罗":-10,"地空":-12,"地劫":-12,"擎羊":-8}[s]; details.append(f"{s}耗财")
    if tianzhai:
        for s in tianzhai.get("主星", []):
            if s in {"贪狼":12,"天府":15,"太阴":10,"武曲":10,"紫微":8}:
                score += {"贪狼":12,"天府":15,"太阴":10,"武曲":10,"紫微":8}[s]; details.append(f"{s}守田宅")
    gn = [p["name"] for p in patterns if p.get("level")=="good"]
    if "三奇嘉会" in gn: score += 15; details.append("三奇嘉会")
    if "禄马交驰" in gn: score += 12; details.append("禄马交驰")
    riyue_names = ["丹墀桂墀格","日月并明格","日月交辉"]
    if any(n in gn for n in riyue_names): score += 10
    if score>=100: level,icon = "大富之命","💎"
    elif score>=80: level,icon = "上富","🏆"
    elif score>=65: level,icon = "中富","💰"
    elif score>=50: level,icon = "小富","🪙"
    else: level,icon = "小康","📊"
    return {"级别":level,"分数":score,"细节":details,"图标":icon}

# ===== 来因宫（月柱地支定位法 — 与文墨天机/钦天四化一致）=====
# 算法: 五虎遁月 → 农历月柱地支 → 对应本命十二宫
# 例: 丁壬年五虎遁起壬寅, 六月=丁未, 地支未→夫妻宫
def _find_laiyin_palace(places, year_gan, year_zhi, lunar_month):
    """来因宫 = 生年年干所在的宫位（文墨天机/梁派飞星标准算法）
    
    原理: 五虎遁给十二宫分配天干, 年干匹配的宫位即为来因宫。
    当10天干配12地支产生重复时, 优先选与年支相同的那个。
    例: 壬寅年→年干壬在兄弟(壬子)和父母(壬寅), 年支寅→选父母
    """
    candidates = []
    for p in places:
        if p.get("天干") == year_gan:
            candidates.append(p)
    
    if len(candidates) == 1:
        p = candidates[0]
    elif len(candidates) > 1:
        # 破平: 优先选与年支匹配的
        p = next((p for p in candidates if p.get("地支") == year_zhi), candidates[0])
    else:
        return {"宫名":"未找到","释义":"来因宫定位异常"}
    
    stars = "、".join(p.get("主星", [])) or "空宫"
    return {"宫名":p["宫名"],"地支":p.get("地支",""),"主星":p.get("主星",[]),"辅星":p.get("辅星",[]),
            "四化":p.get("四化",{}),
            "释义":f"来因宫在{p['宫名']}(年干{year_gan}落{p.get('天干','')}{p.get('地支','')})——一生课题在于{p['宫名']}领域"}


# ========== 以下是原 __main__ 测试代码 ==========

if __name__ == "__main__":
    # 测试: 1987年7月8日戌时男命
    r = full_ziwei_analysis(1987, 7, 8, 19, "男")
    if "error" in r:
        print(f"错误: {r['error']}")
    else:
        print(f"命宫地支: {r['命宫地支']}")
        print(f"身宫地支: {r['身宫地支']}")
        print(f"五行局: {r['五行局']}{r['五行局数']}")
        print(f"紫微在: {r['紫微在']}")
        print(f"命主: {r['命主']}")
        print(f"身主: {r['身主']}")
        print()
        for p in r["十二宫"]:
            print(f"{p['宫名']}: {p['天干']}{p['地支']}  主星:{p['主星']}  辅星:{p['辅星']}")
