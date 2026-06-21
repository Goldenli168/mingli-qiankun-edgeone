"""
命理乾坤 · 紫微斗数核心计算引擎 v4.0
基于 iztro-py 排盘库，确保排盘结果正确
"""

import datetime

# ===== 天干地支 =====
GAN = list("甲乙丙丁戊己庚辛壬癸")
ZHI = list("子丑寅卯辰巳午未申酉戌亥")
GAN_I = {g: i for i, g in enumerate(GAN)}
ZHI_I = {z: i for i, z in enumerate(ZHI)}

# ===== 十二宫名(按固定顺序，从命宫起顺时针) =====
PALACE_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
                "迁移", "交友", "官禄", "田宅", "福德", "父母"]

# ===== 五行局 =====
JU_NUM = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
JU_NAME = {2: "水", 3: "木", 4: "金", 5: "土", 6: "火"}

# ===== iztro-py 英文→中文星名映射 =====
STAR_EN2CN = {
    "ziweiMaj": "紫微", "tianjiMaj": "天机", "taiyangMaj": "太阳",
    "wuquMaj": "武曲", "tiantongMaj": "天同", "lianzhenMaj": "廉贞",
    "tianfuMaj": "天府", "taiyinMaj": "太阴", "tanlangMaj": "贪狼",
    "jumenMaj": "巨门", "tianxiangMaj": "天相", "tianliangMaj": "天梁",
    "qishaMaj": "七杀", "pojunMaj": "破军",
    "zuofuMin": "左辅", "youbiMin": "右弼",
    "wenchangMin": "文昌", "wenquMin": "文曲",
    "lucunMin": "禄存", "tianmaMin": "天马",
    "qingyangMin": "擎羊", "tuoluoMin": "陀罗",
    "huoxingMin": "火星", "lingxingMin": "铃星",
    "tiankuiMin": "天魁", "tianyueMin": "天钺",
    "dikongMin": "地空", "dijieMin": "地劫",
    "tianxingMin": "天刑", "tianyaoMin": "天姚",
    "jiejuMin": "解神", "tianwuMin": "天巫",
    "tianyue2Min": "天月", "tiankui2Min": "天官",
    "tianfu2Min": "天福", "hongluanMin": "红鸾",
    "tianxiMin": "天喜", "guchenMin": "孤辰",
    "guasuMin": "寡宿", "tiankuMin": "天哭",
    "tianxuMin": "天虚", "longchiMin": "龙池",
    "fenggeMin": "凤阁", "tianshangMin": "天伤",
    "tianshiMin": "天使", "feilianMin": "蜚廉",
    "posuiMin": "破碎", "taifuMin": "台辅",
    "fenggaoMin": "封诰", "enkouMin": "恩光",
    "tianguiMin": "天贵", "tiancaiMin": "天才",
    "tianshouMin": "天寿", "santaiMin": "三台",
    "bazuoMin": "八座", "tianchuMin": "天厨",
    "huagaiMin": "华盖", "xianchiMin": "咸池",
    "tiankongMin": "天空", "xunkongMin": "旬空",
    "jieluMin": "截路", "dahaoMin": "大耗",
}

# iztro 宫名英文→中文映射
PALACE_EN2CN = {
    "soulPalace": "命宫", "siblingsPalace": "兄弟宫", "spousePalace": "夫妻宫",
    "childrenPalace": "子女宫", "wealthPalace": "财帛宫", "healthPalace": "疾厄宫",
    "surfacePalace": "迁移宫", "friendsPalace": "交友宫", "careerPalace": "官禄宫",
    "propertyPalace": "田宅宫", "spiritPalace": "福德宫", "parentsPalace": "父母宫",
}

# 五行局英文→中文映射
JU_EN2CN = {
    "水二局": "水", "木三局": "木", "金四局": "金", "土五局": "土", "火六局": "火",
}

# 四化英文→中文映射
SIHUA_EN2CN = {
    "禄": "化禄", "权": "化权", "科": "化科", "忌": "化忌",
    "lu": "化禄", "quan": "化权", "ke": "化科", "ji": "化忌",
}


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
    _dayun_scored = _dayun_deep_analysis(_dayun_extracted, places, year_gan)

    return {
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
        "命主": MINGZHU.get(ming_branch, ""),
        "身主": SHENZHU.get(year_zhi_i, ""),
        "十二宫": places,
        "四化": {"年干": year_gan, "化禄": sihua[0], "化权": sihua[1],
                 "化科": sihua[2], "化忌": sihua[3]},
        "大限信息": {"起运年龄": ju_num, "顺逆": "顺行" if daxian_forward else "逆行"},
        # 大运分析（含深度评分，同时传给流年做三盘联动）
        "大运": _dayun_scored,
        # 流年分析（使用已评分的大运，确保地基有效）
        "流年": _calc_liunian(solar_year, year_gan, year_zhi_i, places, ming_branch, _dayun_scored, ln_weights=ln_weights),
        # 各宫位飞化分析
        "飞化分析": _calc_feihua(year_gan, places),
    }


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

_STAR_WEALTH = {
    # 财星系
    "天府": 30, "武曲": 25, "太阴": 22, "禄存": 28,
    "贪狼": 12, "天相": 15, "紫微": 18,
    # 耗财系
    "破军": -15, "七杀": -10, "廉贞": -8,
    "巨门": -12, "天机": 5, "天同": 8,
    "太阳": 10, "天梁": 5,
}
_STAR_CAREER = {
    "紫微": 35, "天府": 28, "太阳": 25, "天相": 22,
    "武曲": 20, "天机": 15, "廉贞": 12,
    "天梁": 10, "七杀": 8, "破军": 5,
    "贪狼": 10, "巨门": 5, "太阴": 12, "天同": 8,
}
_STAR_MARRIAGE = {
    "太阴": 25, "天同": 22, "天府": 20, "天相": 18,
    "天梁": 15, "贪狼": -10, "七杀": -18, "破军": -20,
    "廉贞": -12, "巨门": -15, "紫微": 10, "太阳": 12,
    "武曲": -8, "天机": 5,
}
_STAR_CHILDREN = {
    "天同": 22, "天府": 20, "天相": 18, "太阴": 15,
    "天梁": 12, "紫微": 10, "太阳": 8,
    "破军": -15, "七杀": -12, "廉贞": -10, "贪狼": -8,
    "巨门": -5, "武曲": -5, "天机": 5,
}
_STAR_PARENTS = {
    "天府": 22, "天相": 20, "天梁": 18, "太阴": 15,
    "天同": 12, "紫微": 10, "太阳": 15,
    "破军": -12, "七杀": -15, "廉贞": -8, "巨门": -10,
    "贪狼": -5, "武曲": -3, "天机": 5,
}

# 辅星调节分
_AUX_ADJUST = {
    "左辅": {"财富": 8, "事业": 10, "婚姻": 12, "子女": 10, "父母": 10},
    "右弼": {"财富": 8, "事业": 10, "婚姻": 12, "子女": 10, "父母": 10},
    "文昌": {"财富": 5, "事业": 12, "婚姻": 6, "子女": 8, "父母": 6},
    "文曲": {"财富": 5, "事业": 10, "婚姻": 8, "子女": 6, "父母": 6},
    "天魁": {"财富": 10, "事业": 12, "婚姻": 8, "子女": 6, "父母": 8},
    "天钺": {"财富": 10, "事业": 12, "婚姻": 8, "子女": 6, "父母": 8},
    "禄存": {"财富": 18, "事业": 10, "婚姻": 5, "子女": 5, "父母": 5},
    "天马": {"财富": 8, "事业": 8, "婚姻": 3, "子女": 2, "父母": 2},
    "擎羊": {"财富": -12, "事业": -5, "婚姻": -15, "子女": -10, "父母": -10},
    "陀罗": {"财富": -10, "事业": -8, "婚姻": -12, "子女": -8, "父母": -8},
    "火星": {"财富": -8, "事业": -5, "婚姻": -12, "子女": -8, "父母": -6},
    "铃星": {"财富": -8, "事业": -5, "婚姻": -10, "子女": -6, "父母": -6},
    "地空": {"财富": -18, "事业": -10, "婚姻": -5, "子女": -3, "父母": -3},
    "地劫": {"财富": -18, "事业": -10, "婚姻": -5, "子女": -3, "父母": -3},
}

# 四化对维度的影响
_SIHUA_DIM = {
    "化禄": {"财富": 20, "事业": 12, "婚姻": 10, "子女": 8, "父母": 8, "健康": 10},
    "化权": {"财富": 10, "事业": 22, "婚姻": 5, "子女": 5, "父母": 5, "健康": 5},
    "化科": {"财富": 8, "事业": 10, "婚姻": 8, "子女": 10, "父母": 10, "健康": 12},
    "化忌": {"财富": -12, "事业": -10, "婚姻": -10, "子女": -8, "父母": -8, "健康": -10},
}

# ----- 大运三方四正对应维度 -----
# 大运命宫三方：命宫-财帛-官禄 为核心三角
# 对宫迁移影响外务
# 大运夫妻宫、子女宫、父母宫、福德宫 分别影响对应维度

def _score_dayun(dayun_palace_stars, dayun_sihua, sanfang_stars, dim_palaces, start_age=None):
    """
    计算单个大运的五维评分

    参数:
      dayun_palace_stars: 大运命宫的主星+辅星列表
      dayun_sihua: 大运命宫的四化状态 dict
      sanfang_stars: 三方四正星曜汇总 {宫名: [主星列表]}
      dim_palaces: 各维度对应宫位星曜 {维度: {主星:[], 辅星:[], 四化:{}}}

    返回:
      {维度: 分数} 和 {维度: 解读文本}
    """
    DIMS = ["财富", "事业", "婚姻", "子女", "父母"]
    # 少年大运（起始年龄<20）跳过婚姻和子女维度
    youth_skip = start_age is not None and start_age < 20
    if youth_skip:
        DIMS = ["财富", "事业", "父母"]  # 少年只评财富、事业、父母
    DIM_PALACE_MAP = {
        "财富": "财帛宫",
        "事业": "官禄宫",
        "婚姻": "夫妻宫",
        "子女": "子女宫",
        "父母": "父母宫",
    }
    STAR_TABLES = {
        "财富": _STAR_WEALTH, "事业": _STAR_CAREER,
        "婚姻": _STAR_MARRIAGE, "子女": _STAR_CHILDREN,
        "父母": _STAR_PARENTS,
    }

    scores = {}
    descs = {}

    for dim in DIMS:
        base = 45  # 基准分（v3.0: 60合格线，45底+15加成≈60）

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

        # 3) 辅星调节
        aux_bonus = 0
        for a in aux_stars + dp_aux:
            adj = _AUX_ADJUST.get(a, {})
            aux_bonus += adj.get(dim, 0)

        # 4) 四化影响
        sihua_bonus = 0
        all_sihua = {}
        all_sihua.update(dayun_sihua)
        all_sihua.update(dp_sihua)

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
        level = "大吉" if total >= 85 else "中吉" if total >= 75 else "小吉" if total >= 60 else "偏弱" if total >= 45 else "凶"
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


def _dayun_deep_analysis(dayun_list, places, year_gan):
    """
    对每个大运进行深度五维评分分析

    参数:
      dayun_list: _extract_dayun() 返回的大运列表
      places: 十二宫完整数据
      year_gan: 年干

    返回:
      在每个大运数据中增加 "评分" 和 "深度解读" 字段
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

    # 四化表
    SIHUA_TABLE = {
        "甲": ["廉贞","破军","武曲","太阳"],
        "乙": ["天机","天梁","紫微","太阴"],
        "丙": ["天同","天机","文昌","廉贞"],
        "丁": ["太阴","天同","天机","巨门"],
        "戊": ["贪狼","太阴","右弼","天机"],
        "己": ["武曲","贪狼","天梁","文曲"],
        "庚": ["太阳","武曲","太阴","天同"],
        "辛": ["巨门","太阳","文曲","文昌"],
        "壬": ["天梁","紫微","左辅","武曲"],
        "癸": ["破军","巨门","太阴","贪狼"],
    }
    SIHUA_LABELS = ["化禄","化权","化科","化忌"]
    hua_stars = SIHUA_TABLE.get(year_gan, ["","","",""])

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
        scores, descs = _score_dayun(dayun_palace_stars, dayun_sihua, sanfang_stars, dim_palaces, start_age)

        # 综合评分 (加权平均)；少年大运自动调节权重
        if start_age < 20:
            weights = {"财富": 0.35, "事业": 0.35, "父母": 0.30}
        else:
            weights = {"财富": 0.25, "事业": 0.25, "婚姻": 0.20, "子女": 0.15, "父母": 0.15}
        total_score = 0
        for dim, w in weights.items():
            total_score += scores.get(dim, 50) * w
        total_score = int(round(total_score))

        # 综合评级
        if total_score >= 85:
            overall = "大吉"
            overall_desc = "此运极佳，诸事顺遂，宜积极进取。陆斌兆云：「大运得令，十年风光」."
        elif total_score >= 75:
            overall = "中吉"
            overall_desc = "此运良好，虽有波折不碍大局，稳中求进。倪海厦云：「三方会吉，不失为佳运」."
        elif total_score >= 60:
            overall = "小吉"
            overall_desc = "此运合格，无大起大落，宜守成待时。王亭之云：「平运宜守，勿贪急进」."
        elif total_score >= 45:
            overall = "偏弱"
            overall_desc = "此运偏弱，需防破耗是非，退守自保，不宜冒进."
        else:
            overall = "大凶"
            overall_desc = "此运整体运势凶险，诸事多阻，宜韬光养晦，避凶趋吉。倪海厦云：「大运逢煞，十年坎坷，唯忍字可渡」."

        # 追加命宫主星对大运的影响
        ming_main = dayun_palace_stars.get("主星", [])
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

        dy["评分"] = scores
        dy["综合评分"] = total_score
        dy["综合评级"] = overall
        dy["综合解读"] = overall_desc
        dy["深度解读"] = descs

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
def _calc_liunian(solar_year, year_gan, year_zhi_i, places, ming_branch, dayun_list=None, ln_weights=None):
    """
    计算流年分析，包含四化评分、白话简评、四维指引。

    参数:
      solar_year: 出生公历年
      year_gan: 年干
      year_zhi_i: 年支索引 (0-11)
      places: 十二宫数据列表
      ming_branch: 命宫地支索引

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

    # 流年四化表（天干→[化禄,化权,化科,化忌]）
    SIHUA_LN = {
        "甲":["廉贞","破军","武曲","太阳"],
        "乙":["天机","天梁","紫微","太阴"],
        "丙":["天同","天机","文昌","廉贞"],
        "丁":["太阴","天同","天机","巨门"],
        "戊":["贪狼","太阴","右弼","天机"],
        "己":["武曲","贪狼","天梁","文曲"],
        "庚":["太阳","武曲","太阴","天同"],
        "辛":["巨门","太阳","文曲","文昌"],
        "壬":["天梁","紫微","左辅","武曲"],
        "癸":["破军","巨门","太阴","贪狼"],
    }

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

        # ═══ 1) 大运基调 ── 首位，因大运定大局 ═══
        if dayun_ctx and dayun_ctx.get('palace_name'):
            dy_rating = dayun_ctx.get('rating', '平运')
            rating_desc = {"大吉":"大运极盛，诸事可期","中吉":"运势上扬，稳中求进",
                          "小吉":"平稳十年，守成为上","偏弱":"此运偏弱，宜退守",
                          "凶":"运势凶险，韬光养晦"}
            dy_desc = rating_desc.get(dy_rating, "运势平稳")
            parts.append(f"你正行{dayun_ctx.get('age_range','')}{dayun_ctx['palace_name']}大运，{dy_desc}")
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

        # ═══ 7) 行动锦囊 ── 倪海厦风格一句话 ═══
        tips_pool = []
        if s_ji:
            tips_pool = ["忌星之年以守为攻，倪师常言：不动如山", "稳字当头今年最忌贪快", "熬过此年便是春天"]
        elif s_lu:
            tips_pool = ["禄临之年该出手时就出手", "好运不等人，大胆往前闯", "春耕秋收——今年种什么都收成"]
        elif "冲" in chong_str:
            tips_pool = ["冲则动、动则变、变则通", "主动求变胜过被动挨打"]
        elif "合" in chong_str:
            tips_pool = ["天地合气顺势而为即可", "贵人就在身边，开口就有"]
        else:
            tips_pool = ["平平淡淡才是真，稳扎稳打", "守好本分，该来的自然会来"]
        parts.append(tips_pool[zhi_idx % len(tips_pool)])

        return "。".join(parts[:8]) + "。"

    def _guide(dims):
        """五维指引"""
        lines = []
        dmap = {"事业":"事业","财富":"财运","婚姻":"婚姻","子女":"子女","健康":"健康"}
        for k in ["事业","财富","婚姻","子女","健康"]:
            v = dims[k]
            if v >= 80:
                lines.append("%s★★★★★ 大吉，全力出击" % dmap[k])
            elif v >= 70:
                lines.append("%s★★★★☆ 中吉，把握良机" % dmap[k])
            elif v >= 60:
                lines.append("%s★★★☆☆ 小吉，稳中向好" % dmap[k])
            elif v >= 50:
                lines.append("%s★★☆☆☆ 合格，宜守不宜攻" % dmap[k])
            else:
                lines.append("%s★☆☆☆☆ 偏弱，需格外谨慎" % dmap[k])
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
        sihua_stars = SIHUA_LN.get(g, ["","","",""])

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
                        'dy_sihua': _zhi_to_palace.get(dy_zhi_i, {}).get('四化', {}),  # 大运四化
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
                    break


        # ===== 流年五维度评分 v4.0: 分析驱动 =====
        # 原则: 大运定趋势(70%), 流年四化做加减, 最终调和太岁
        # 每维度 = 大运地基 + 四化落宫分析 + 流年命宫分析 + 太岁调节

        DIMS = ["事业","财富","婚姻","子女","健康"]
        dims = {d: 50 for d in DIMS}

        # 大运→流年维度映射
        DY_TO_LN = {"财富":"财富","事业":"事业","婚姻":"婚姻","子女":"子女","父母":"健康"}

        _STAR_HEALTH = {
            "天梁":25,"天同":22,"天府":18,"天相":15,"紫微":12,"太阳":10,"太阴":10,
            "破军":-15,"七杀":-12,"廉贞":-10,"巨门":-8,"贪狼":-8,"武曲":-5,"天机":3,
        }
        STAR_TABLES_LN = {
            "事业": _STAR_CAREER, "财富": _STAR_WEALTH,
            "婚姻": _STAR_MARRIAGE, "子女": _STAR_CHILDREN,
            "健康": _STAR_HEALTH,
        }

        # ═══ ① 大运地基 (70%) + 大运四化叠加 (25%) ═══
        dy_dim_scores = dayun_ctx.get('dim_scores', {}) if dayun_ctx else {}
        dy_sihua = dayun_ctx.get('dy_sihua', {}) if dayun_ctx else {}
        dy_foundation = {}
        for dy_dim, ln_dim in DY_TO_LN.items():
            dy_base = dy_dim_scores.get(dy_dim, 50)
            foundation = int(dy_base * 0.70)
            dims[ln_dim] = foundation
            dy_foundation[ln_dim] = foundation
        # 《全书》：大运四化是"体"，叠加对流年的影响（权重0.25）
        for hua_type, star_name in dy_sihua.items():
            for dim in DIMS:
                dims[dim] += int(_SIHUA_DIM.get(hua_type, {}).get(dim, 0) * 0.25)

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
                    # 四化主效应
                    for dim in DIMS:
                        dims[dim] += _SIHUA_DIM.get(hua_name, {}).get(dim, 0)
                    # 星曜自身在各维度的贡献（轻量加权）
                    for dim, tbl in STAR_TABLES_LN.items():
                        dims[dim] += int(tbl.get(star_name, 0) * 0.15)
                    break

        # ═══ ③ 流年命宫分析 ═══
        ln_palace = _zhi_to_palace.get(zhi_idx)
        ln_palace_name = ''
        ln_palace_main = []
        if ln_palace:
            ln_palace_name = ln_palace.get("宫名", "")
            ln_palace_main = ln_palace.get("主星", [])
            # 流年命宫主星对五维的贡献
            for s in ln_palace_main:
                for dim, tbl in STAR_TABLES_LN.items():
                    dims[dim] += int(tbl.get(s, 0) * 0.25)
            # 辅星贡献
            for a in ln_palace.get("辅星", []):
                adj = _AUX_ADJUST.get(a, {})
                for dim in DIMS:
                    dims[dim] += int(adj.get(dim, 0) * 0.40)

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
                            dims[sf_dim] += int(tbl.get(s, 0) * 0.20)

        # ═══ ⑤ 太岁冲合调节 ═══
        for dim in DIMS:
            dims[dim] += chong_val * 2

        # ═══ ⑥ 夹持: 《全书》体用协调保护 ═══
        if dayun_ctx:
            for dy_dim, ln_dim in DY_TO_LN.items():
                dy_v = dy_dim_scores.get(dy_dim, 50)
                if dy_v >= 75:
                    dims[ln_dim] = max(dims[ln_dim], 53)  # 大运中吉→流年至少2星
                elif dy_v >= 60:
                    dims[ln_dim] = max(dims[ln_dim], 48)  # 大运小吉→流年不低于1星高区
                elif dy_v < 45:
                    dims[ln_dim] = min(dims[ln_dim], 72)  # 大运弱→流年上限

        # Clamp（全书：忌虽凶不致死，禄虽喜不逆天）
        for dim in DIMS:
            dims[dim] = max(32, min(95, dims[dim]))

        avg = int(sum(dims.values()) / 5)

        # 组装简评所需上下文
        brief_ctx = (y, g, z, ny, ss, sihua_stars, chong_desc, sihua_info, dayun_ctx,
                     ln_palace_name, ln_palace_main, dy_foundation, dims)

        brief = _brief(*brief_ctx)

        # 五维指引
        guide = _guide(dims)

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

    # 年干四化表
    SIHUA_TABLE = {
        "甲": ["廉贞","破军","武曲","太阳"],
        "乙": ["天机","天梁","紫微","太阴"],
        "丙": ["天同","天机","文昌","廉贞"],
        "丁": ["太阴","天同","天机","巨门"],
        "戊": ["贪狼","太阴","右弼","天机"],
        "己": ["武曲","贪狼","天梁","文曲"],
        "庚": ["太阳","武曲","太阴","天同"],
        "辛": ["巨门","太阳","文曲","文昌"],
        "壬": ["天梁","紫微","左辅","武曲"],
        "癸": ["破军","巨门","太阴","贪狼"],
    }
    SIHUA_LABELS = ["化禄","化权","化科","化忌"]

    hua_list = SIHUA_TABLE.get(year_gan, ["", "", "", ""])
    feihua = []

    for i in range(4):
        star_name = hua_list[i]
        if not star_name:
            continue
        label = SIHUA_LABELS[i]
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
