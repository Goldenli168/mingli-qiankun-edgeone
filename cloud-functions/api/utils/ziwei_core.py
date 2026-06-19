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


def full_ziwei_analysis(solar_year, solar_month, solar_day, hour, sex, is_solar=True):
    """
    紫微斗数全盘分析
    输入: 公历日期 + 时辰(0-23) + 性别
    返回: 完整紫微命盘数据
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
        # 大运分析（从iztro提取，并深度评分）
        "大运": _dayun_deep_analysis(
            _extract_dayun(chart, ming_branch, daxian_forward, ju_num, solar_year),
            places, year_gan),
        # 流年分析（增强版：含四化、评分、简评、四维指引）
        "流年": _calc_liunian(solar_year, year_gan, year_zhi_i, places, ming_branch),
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
    "化禄": {"财富": 20, "事业": 12, "婚姻": 10, "子女": 8, "父母": 8},
    "化权": {"财富": 10, "事业": 22, "婚姻": 5, "子女": 5, "父母": 5},
    "化科": {"财富": 8, "事业": 10, "婚姻": 8, "子女": 10, "父母": 10},
    "化忌": {"财富": -18, "事业": -15, "婚姻": -15, "子女": -12, "父母": -12},
}

# ----- 大运三方四正对应维度 -----
# 大运命宫三方：命宫-财帛-官禄 为核心三角
# 对宫迁移影响外务
# 大运夫妻宫、子女宫、父母宫、福德宫 分别影响对应维度

def _score_dayun(dayun_palace_stars, dayun_sihua, sanfang_stars, dim_palaces):
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
        base = 50  # 基准分

        # 1) 大运命宫主星对该维度的贡献
        main_stars = dayun_palace_stars.get("主星", [])
        aux_stars = dayun_palace_stars.get("辅星", [])
        star_table = STAR_TABLES[dim]

        dim_detail_parts = []
        star_bonus = 0
        for s in main_stars:
            v = star_table.get(s, 0)
            star_bonus += v
            if abs(v) >= 15:
                sign = "+" if v > 0 else ""
                dim_detail_parts.append("%s%s(%s%d)" % (s, "主星" if v > 0 else "耗泄", sign, v))

        # 2) 三方四正中对应维度宫位的星曜贡献（权重0.7）
        dp = dim_palaces.get(dim, {})
        dp_main = dp.get("主星", [])
        dp_aux = dp.get("辅星", [])
        dp_sihua = dp.get("四化", {})
        dp_bonus = 0
        for s in dp_main:
            v = star_table.get(s, 0)
            dp_bonus += int(v * 0.7)
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
        for hua_type, star_name in all_sihua.items():
            hua_adj = _SIHUA_DIM.get(hua_type, {})
            sihua_bonus += hua_adj.get(dim, 0)
            if abs(hua_adj.get(dim, 0)) >= 10:
                dim_detail_parts.append("%s%s(%s%d)" % (star_name, hua_type, "+" if hua_adj.get(dim, 0) > 0 else "", hua_adj.get(dim, 0)))

        # 汇总
        total = base + star_bonus + dp_bonus + aux_bonus + sihua_bonus
        total = max(20, min(100, total))  # clamp
        scores[dim] = total

        # 解读文本
        level = "优" if total >= 80 else "良" if total >= 65 else "中" if total >= 50 else "差" if total >= 35 else "凶"
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
    if score >= 80:
        base = {
            "财富": "此运财源广进，宜把握投资机遇，天府武曲太阴等财星得力，陆斌兆云：「财星守命，十年丰足」.",
            "事业": "此运事业通达，贵人扶助，紫微天府太阳坐镇，倪海厦云：「命宫得令，三方会吉，十年宏图可展」.",
            "婚姻": "此运婚姻和美，感情顺遂，太阴天同主柔顺，陆斌兆云：「夫妻宫吉，鸾凤和鸣」.",
            "子女": "此运子女有成，亲子融洽，天同天府主福泽，子女宫吉庆有余.",
            "父母": "此运与长辈缘分深厚，得荫庇助力，天梁太阳主尊长，父母宫安稳.",
        }
    elif score >= 65:
        base = {
            "财富": "此运财运平稳，量入为出，不宜冒进投机，守成为上策.",
            "事业": "此运事业渐进，踏实经营可获提升，宜稳中求变.",
            "婚姻": "此运婚姻平稳，偶有磨擦但可化解，宜多包容沟通.",
            "子女": "此运子女运中等，需多关心教育引导，不可放任.",
            "父母": "此运与父母关系尚可，宜多尽孝道，注意长辈健康.",
        }
    elif score >= 50:
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

        # 计算评分
        scores, descs = _score_dayun(dayun_palace_stars, dayun_sihua, sanfang_stars, dim_palaces)

        # 综合评分 (加权平均)
        weights = {"财富": 0.25, "事业": 0.25, "婚姻": 0.20, "子女": 0.15, "父母": 0.15}
        total_score = 0
        for dim, w in weights.items():
            total_score += scores.get(dim, 50) * w
        total_score = int(round(total_score))

        # 综合评级
        if total_score >= 80:
            overall = "上吉"
            overall_desc = "此运整体运势极佳，诸事顺遂，宜积极进取，把握良机。陆斌兆云：「大运得令，十年风光」."
        elif total_score >= 65:
            overall = "中吉"
            overall_desc = "此运整体运势良好，虽有波折但不碍大局，宜稳中求进。倪海厦云：「三方会吉，虽有小疵，不失为佳运」."
        elif total_score >= 50:
            overall = "平运"
            overall_desc = "此运整体运势平稳，无大起大落，宜守成待时，王亭之云：「平运宜守，勿贪急进」."
        elif total_score >= 35:
            overall = "偏凶"
            overall_desc = "此运整体运势偏弱，需防破耗与是非，宜退守自保，不宜冒进."
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
def _calc_liunian(solar_year, year_gan, year_zhi_i, places, ming_branch):
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
        if s >= 85: return 5
        if s >= 70: return 4
        if s >= 55: return 3
        if s >= 40: return 2
        return 1

    def _brief(y, g, z, ny, ss, sihua_stars, chong_str):
        """倪海厦《天纪》风格简评（50-70字）"""
        s_lu = sihua_stars[0]; s_quan = sihua_stars[1]; s_ke = sihua_stars[2]; s_ji = sihua_stars[3]
        gz = g + z

        # 倪海厦风格短语库
        NH = {
            "tai_sui_chong": [
                f"太岁冲命宫，今年变动大过坐过山车，宜动不宜静",
                f"冲太岁，搬家换工作换环境都是好事，别死守",
                f"命宫被太岁冲，这一年稳不住的，顺势而为就对了",
            ],
            "tai_sui_zhi": [
                f"太岁值命，新的一页翻开了，有什么想法就去做",
                f"太岁临命，天命在你这儿，大胆冲",
            ],
            "tai_sui_he": [
                f"太岁合命，贵人自己会来找你，躺着都有好事",
                f"六合之年，天时地利人和，结婚合伙都是上选",
            ],
            "tai_sui_hai": [
                f"太岁害命宫，暗箭难防，合同签字要多看两眼",
                f"害太岁，小人躲在暗处，少管闲事少惹是非",
            ],
            "tai_sui_ping": [
                f"平稳一年，不贪不急就是赢",
                f"风平浪静的一年，守好本分就好",
            ],
            "lu": {
                "廉贞": "廉贞化禄，桃花财旺得不得了，但情债要还",
                "破军": "破军化禄，破旧立新财运开，敢闯就有",
                "武曲": "武曲化禄，正财运来得猛，存得住才是你的",
                "太阳": "太阳化禄，光明正大地赚钱，名气带财来",
                "天机": "天机化禄，脑子转得快钱就来，别想太多",
                "天梁": "天梁化禄，福星高照，偏财比正财还旺",
                "紫微": "紫微化禄，帝王星加持，这一年你可以横着走",
                "太阴": "太阴化禄，田宅财旺，买房置产好时机",
                "天同": "天同化禄，福气满满，躺着也有钱进来",
                "贪狼": "贪狼化禄，偏财桃花一起来，但要懂得收",
                "巨门": "巨门化禄，口才变钱，说话就能赚",
            },
            "quan": {
                "廉贞": "廉贞化权，掌控力爆表，说了算的一年",
                "破军": "破军化权，破局的力量在你手里，敢干就赢",
                "武曲": "武曲化权，执行力拉满，该出手时别犹豫",
                "太阳": "太阳化权，光芒万丈，升职加薪看你表演",
                "天机": "天机化权，策略对了就是王，谋定而后动",
                "天梁": "天梁化权，权威加身，说了就算",
                "紫微": "紫微化权，这一年的主角就是你",
                "太阴": "太阴化权，暗中掌握大局，不动声色赢",
                "天同": "天同化权，以柔克刚，不争就是最大的争",
                "贪狼": "贪狼化权，人脉资源一把抓，社交就是生产力",
                "巨门": "巨门化权，一开口就镇住全场",
                "文昌": "文昌化权，文星当道，考试面试发挥好",
                "文曲": "文曲化权，才艺变现，靠本事吃饭",
                "右弼": "右弼化权，左右逢源，贵人主动来",
            },
            "ke": {
                "文昌": "文昌化科，学业考试如有神助",
                "文曲": "文曲化科，才艺名声双丰收",
                "天梁": "天梁化科，好人好事传千里",
                "太阴": "太阴化科，暗中有贵人提携",
                "左辅": "左辅化科，助力不断，事事顺",
                "右弼": "右弼化科，人缘好得不得了",
                "天机": "天机化科，智慧闪光，一鸣惊人",
            },
            "ji": {
                "太阳": "太阳化忌，男人缘差，跟老板同事别较劲",
                "太阴": "太阴化忌，女人小人多，家务事别闹大",
                "廉贞": "廉贞化忌，感情官司缠身，别提旧账",
                "巨门": "巨门化忌，口舌是非多如牛毛，闭嘴是金",
                "天同": "天同化忌，懒散误事，别拖别等",
                "武曲": "武曲化忌，破财之年，投资三个字：不要碰",
                "文曲": "文曲化忌，文书合同出问题，白纸黑字盯紧",
                "文昌": "文昌化忌，考试面试有坎，加倍准备",
                "天机": "天机化忌，想太多反而坏事，简单点",
                "贪狼": "贪狼化忌，桃花劫来了，色字头上一把刀",
            },
            "ss_boost": {
                "比肩": "自食其力之年，别指望别人",
                "劫财": "小心合伙分财不均，亲兄弟明算账",
                "食神": "创意变现的好年份，灵感变金子",
                "伤官": "才华横溢但易得罪人，注意说话分寸",
                "偏财": "意外之财来敲门，投资可以小试",
                "正财": "稳扎稳打赚钱，正业收入稳中有升",
                "七杀": "压力大到爆但升得也快，撑住就是赢家",
                "正官": "按规矩办事就对了，别走捷径",
                "偏印": "学习进修的好年，考个证拿个学位",
                "正印": "长辈贵人关照，听老人家的话",
            },
            "ny_boost": {
                "海中金": "金子埋在海里，今年财运暗藏机会",
                "炉中火": "炉火烧得旺，事业升温，但别烧过头",
                "大林木": "大树底下好乘凉，靠团队别单干",
                "路旁土": "脚踏实地的一年，一步一脚印",
                "剑锋金": "锋芒毕露，但树大招风",
                "山头火": "火焰山的一年，急不来的",
                "涧下水": "细水长流，别指望一夜暴富",
                "城头土": "稳如城墙，根基扎实",
                "白蜡金": "小财不断，大财别想",
                "杨柳木": "随风飘的一年，顺势别硬撑",
                "泉中水": "灵感如泉涌，创作爆发年",
                "屋上土": "家宅相关，买房修屋好时机",
                "霹雳火": "惊雷一响机遇来，要抓得住",
                "松柏木": "松柏长青，越老越值钱的一年",
                "长流水": "源源不断，积累之年",
                "沙中金": "大浪淘沙见真金，坚持就有",
                "山下火": "小火慢炖，别急",
                "平地木": "根基年，打基础最重要",
                "壁上土": "别太高调，墙上的土易掉",
                "金箔金": "表面风光，内里要踏实",
                "覆灯火": "灯下黑，看清身边人",
                "天河水": "天降甘霖，贵人运旺",
                "大驿土": "奔波劳碌但值得，在路上就有机会",
                "钗钏金": "小饰品值钱，小生意也有大赚头",
                "桑柘木": "养蚕吐丝，劳动换回报",
                "大溪水": "溪水汇流，众人拾柴火焰高",
                "沙中土": "沙里淘金，要有耐心",
                "天上火": "火从天上来，名利双收的好年",
                "石榴木": "多子多福，家庭喜事多",
                "大海水": "海纳百川，格局要大",
            },
        }

        # 1) 太岁冲合 — 决定年度基调
        if chong_str.startswith("冲"):
            base = NH["tai_sui_chong"][zhi_idx % 3]
        elif chong_str.startswith("值"):
            base = NH["tai_sui_zhi"][zhi_idx % 2]
        elif chong_str.startswith("合"):
            base = NH["tai_sui_he"][zhi_idx % 2]
        elif chong_str.startswith("害"):
            base = NH["tai_sui_hai"][zhi_idx % 2]
        else:
            base = NH["tai_sui_ping"][zhi_idx % 2]

        # 2) 化忌 — 点名警告，必须说
        parts = [base]
        if s_ji and s_ji in NH["ji"]:
            parts.append(NH["ji"][s_ji])

        # 3) 化禄 — 好事要夸
        if s_lu and s_lu in NH["lu"]:
            parts.append(NH["lu"][s_lu])

        # 4) 化权 — 主动权
        if s_quan and s_quan in NH["quan"] and len(parts) < 3:
            parts.append(NH["quan"][s_quan])

        # 5) 十神补充
        if ss in NH["ss_boost"] and len(parts) < 3:
            parts.append(NH["ss_boost"][ss])

        # 6) 纳音点睛
        if ny in NH["ny_boost"] and len(parts) < 3:
            parts.append(NH["ny_boost"][ny])

        return "。".join(parts[:3]) + "。"

    def _guide(dims):
        """五维指引"""
        lines = []
        dmap = {"事业":"事业","财富":"财运","婚姻":"婚姻","子女":"子女","健康":"健康"}
        for k in ["事业","财富","婚姻","子女","健康"]:
            v = dims[k]
            if v >= 70:
                lines.append("%s★★★★★ 黄金期，全力出击" % dmap[k])
            elif v >= 55:
                lines.append("%s★★★☆☆ 稳中向好" % dmap[k])
            elif v >= 40:
                lines.append("%s★★☆☆☆ 宜守不宜攻" % dmap[k])
            else:
                lines.append("%s★☆☆☆☆ 需格外谨慎" % dmap[k])
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
    SIHUA_PALACE_BONUS = {
        "化禄": {"婚姻":18,"子女":15,"财富":20,"健康":12,"事业":15},
        "化权": {"婚姻":8,"子女":8,"财富":10,"健康":8,"事业":20},
        "化科": {"婚姻":12,"子女":12,"财富":8,"健康":12,"事业":10},
        "化忌": {"婚姻":-15,"子女":-12,"财富":-18,"健康":-15,"事业":-15},
    }

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

        # 五维度评分 —— 基于出生命盘的四化落宫（《天纪》《紫微斗数全书》核心法）
        # 倪海厦：「禄在哪儿钱在哪儿，忌在哪儿问题在哪儿」
        # 关键：四化星落在命盘的哪个宫位，决定哪个人生领域受影响
        dims = {"事业":50, "财富":50, "婚姻":50, "子女":50, "健康":50}
        hua_labels = ["化禄","化权","化科","化忌"]

        # 1) 四化落宫 —— 核心评分逻辑（因人而异的关键）
        for hi, hua_name in enumerate(hua_labels):
            star_name = sihua_stars[hi]
            if not star_name:
                continue

            # 在命盘中查找该星曜所在的宫位
            for p_idx, p_data in _zhi_to_palace.items():
                p_main = p_data.get("主星", [])
                p_aux = p_data.get("辅星", [])
                all_stars = p_main + p_aux
                if star_name in all_stars:
                    p_name = p_data.get("宫名", "")
                    dim = PALACE_DIM_MAP.get(p_name)
                    if dim:
                        # 四化落在对应维度宫位 → 强效应
                        bonus = SIHUA_PALACE_BONUS.get(hua_name, {}).get(dim, 0)
                        dims[dim] += bonus
                    else:
                        # 四化落在非核心宫位 → 弱效应
                        if hua_name == "化禄":
                            dims["财富"] += 5; dims["事业"] += 3
                        elif hua_name == "化权":
                            dims["事业"] += 5
                        elif hua_name == "化科":
                            dims["婚姻"] += 3; dims["子女"] += 3
                        elif hua_name == "化忌":
                            dims["健康"] -= 5
                    break  # 每颗星只在一个宫位

        # 2) 流年命宫定位 —— 太岁地支落在命盘的哪个宫位
        ln_palace = _zhi_to_palace.get(zhi_idx)
        if ln_palace:
            ln_name = ln_palace.get("宫名", "")
            ln_dim = PALACE_DIM_MAP.get(ln_name)
            if ln_dim:
                if chong_val > 0:
                    dims[ln_dim] += 5
                elif chong_val < 0:
                    dims[ln_dim] -= 5

        # 3) 太岁冲合全局调节
        for dim in dims:
            dims[dim] += chong_val * 2
            dims[dim] = max(20, min(100, dims[dim]))

        # 综合评分
        avg = int(sum(dims.values()) / 5)

        # 简评
        brief = _brief(y, g, z, ny, ss, sihua_stars, chong_desc)

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
