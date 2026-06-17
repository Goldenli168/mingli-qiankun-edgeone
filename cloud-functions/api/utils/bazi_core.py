"""
命理乾坤 · 八字核心计算引擎 v5.0
新增: 神煞系统、大运四书分析、多维度评分
修正: 日柱基准、十神映射、节气月支、大运起运、喜用神通关
"""
import datetime
import ephem

# ===== 天干地支 =====
GAN = list("甲乙丙丁戊己庚辛壬癸")
ZHI = list("子丑寅卯辰巳午未申酉戌亥")
GAN_I = {g: i for i, g in enumerate(GAN)}
ZHI_I = {z: i for i, z in enumerate(ZHI)}

# ===== 天干五行 / 地支五行 =====
WXG = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土",
       "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
WXZ = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
       "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}

# ===== 地支藏干 =====
ZHICANG = {
    "子": ["癸"],       "丑": ["己", "辛", "癸"],
    "寅": ["甲", "丙", "戊"], "卯": ["乙"],
    "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"],       "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"], "酉": ["辛"],
    "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"]
}

# ===== 十神 =====
# 阳干和阴干的offset映射不同
# 阳干(甲丙戊庚壬): 比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印
# 阴干(乙丁己辛癸): 比肩 伤官 食神 正财 偏财 正官 七杀 正印 偏印 劫财
SS_YANG = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
SS_YIN  = ["比肩", "伤官", "食神", "正财", "偏财", "正官", "七杀", "正印", "偏印", "劫财"]
SHISHEN = {}
for i, g in enumerate(GAN):
    SHISHEN[g] = {}
    order = SS_YANG if i % 2 == 0 else SS_YIN
    for j, h in enumerate(GAN):
        d = (j - i) % 10
        SHISHEN[g][h] = order[d]

# ===== 纳音60甲子 =====
NY = ["海中金", "海中金", "炉中火", "炉中火", "大林木", "大林木",
      "路旁土", "路旁土", "剑锋金", "剑锋金", "山头火", "山头火",
      "涧下水", "涧下水", "城头土", "城头土", "白蜡金", "白蜡金",
      "杨柳木", "杨柳木", "泉中水", "泉中水", "屋上土", "屋上土",
      "霹雳火", "霹雳火", "松柏木", "松柏木", "长流水", "长流水",
      "砂石金", "砂石金", "山下火", "山下火", "平地木", "平地木",
      "壁上土", "壁上土", "金箔金", "金箔金", "覆灯火", "覆灯火",
      "天河水", "天河水", "大驿土", "大驿土", "钗钏金", "钗钏金",
      "桑柘木", "桑柘木", "大溪水", "大溪水", "沙中土", "沙中土",
      "天上火", "天上火", "石榴木", "石榴木", "大海水", "大海水"]
NAYIN = {}
for i in range(60):
    NAYIN[(GAN[i % 10], ZHI[i % 12])] = NY[i]


def nayin(g, z):
    return NAYIN.get((g, z), "未知")


# ===== 神煞系统 =====
# 天乙贵人(以日干查)
_TIANYI = {
    "甲": ["丑", "未"], "乙": ["子", "申"], "丙": ["亥", "酉"],
    "丁": ["亥", "酉"], "戊": ["丑", "未"], "己": ["子", "申"],
    "庚": ["丑", "未"], "辛": ["午", "寅"], "壬": ["卯", "巳"],
    "癸": ["卯", "巳"]
}
# 驿马(以年支查, 日支查)
_YIMA = {"申": "寅", "子": "寅", "辰": "寅",  # 申子辰马在寅
         "寅": "申", "午": "申", "戌": "申",  # 寅午戌马在申
         "巳": "亥", "酉": "亥", "丑": "亥",  # 巳酉丑马在亥
         "亥": "巳", "卯": "巳", "未": "巳"}   # 亥卯未马在巳
# 文昌(以日干查)
_WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
             "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
# 桃花(以年支、日支查)
_TAOHUA = {"申": "酉", "子": "酉", "辰": "酉",  # 申子辰桃花在酉
           "寅": "卯", "午": "卯", "戌": "卯",  # 寅午戌桃花在卯
           "巳": "午", "酉": "午", "丑": "午",  # 巳酉丑桃花在午
           "亥": "子", "卯": "子", "未": "子"}   # 亥卯未桃花在子
# 华盖(以年支查)
_HUAGAI = {"申": "辰", "子": "辰", "辰": "辰",  # 申子辰华盖在辰
           "寅": "戌", "午": "戌", "戌": "戌",  # 寅午戌华盖在戌
           "巳": "丑", "酉": "丑", "丑": "丑",  # 巳酉丑华盖在丑
           "亥": "未", "卯": "未", "未": "未"}   # 亥卯未华盖在未
# 将星(以年支查)
_JIANGXING = {"申": "子", "子": "子", "辰": "子",  # 申子辰将在子
              "寅": "午", "午": "午", "戌": "午",  # 寅午戌将在午
              "巳": "酉", "酉": "酉", "丑": "酉",  # 巳酉丑将在酉
              "亥": "卯", "卯": "卯", "未": "卯"}   # 亥卯未将在卯
# 禄神(以日干查)
_LUSHEN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
           "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
# 羊刃(以日干查, 禄神后一位)
_YANGREN = {"甲": "卯", "乙": "辰", "丙": "午", "丁": "未", "戊": "午",
            "己": "未", "庚": "酉", "辛": "戌", "壬": "子", "癸": "丑"}
# 天德贵人(以月支查)
_TIANDE = {"寅": "丁", "卯": "申", "辰": "壬", "巳": "辛",
           "午": "亥", "未": "甲", "申": "癸", "酉": "寅",
           "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚"}
# 月德贵人(以月支查)
_YUEDE = {"寅": "丙", "卯": "甲", "辰": "壬", "巳": "庚",
          "午": "丙", "未": "甲", "申": "壬", "酉": "庚",
          "戌": "丙", "亥": "甲", "子": "壬", "丑": "庚"}
# 亡神(以年支查)
_WANGSHEN = {"申": "亥", "子": "亥", "辰": "亥",  # 申子辰亡在亥
             "寅": "巳", "午": "巳", "戌": "巳",  # 寅午戌亡在巳
             "巳": "申", "酉": "申", "丑": "申",  # 巳酉丑亡在申
             "亥": "寅", "卯": "寅", "未": "寅"}   # 亥卯未亡在寅
# 劫煞(以年支查)
_JIESHA = {"申": "巳", "子": "巳", "辰": "巳",  # 申子辰劫在巳
           "寅": "亥", "午": "亥", "戌": "亥",  # 寅午戌劫在亥
           "巳": "寅", "酉": "寅", "丑": "寅",  # 巳酉丑劫在寅
           "亥": "申", "卯": "申", "未": "申"}   # 亥卯未劫在申
# 孤辰(以年支查)
_GUCHEN = {"子": "寅", "丑": "寅", "寅": "巳", "卯": "巳", "辰": "巳",
           "巳": "申", "午": "申", "未": "申", "申": "亥", "酉": "亥",
           "戌": "亥", "亥": "寅"}
# 寡宿(以年支查)
_GUAXIU = {"子": "戌", "丑": "戌", "寅": "丑", "卯": "丑", "辰": "丑",
           "巳": "辰", "午": "辰", "未": "辰", "申": "未", "酉": "未",
           "戌": "未", "亥": "戌"}


def calc_shensha(fp, sex="男"):
    """
    计算命局中的神煞
    fp: 四柱 {"year":(g,z), "month":(g,z), "day":(g,z), "hour":(g,z)}
    返回: 神煞列表 [{"名称":..., "位置":..., "含义":..., "性质":...}, ...]
          位置标注为"年柱"/"月柱"/"日柱"/"时柱"中文柱名
    """
    dg = fp["day"][0]
    nz = fp["year"][1]  # 年支
    dz = fp["day"][1]   # 日支
    mz = fp["month"][1] # 月支
    all_zhi = [fp[p][1] for p in POS]
    all_gan = [fp[p][0] for p in POS]
    pos_cn = {"year": "年柱", "month": "月柱", "day": "日柱", "hour": "时柱"}

    result = []

    def _zhi_pos(target_zhi):
        """返回目标地支出现在哪些柱，以中文柱名列表返回"""
        return [pos_cn[POS[i]] for i in range(4) if all_zhi[i] == target_zhi]

    def _add(name, positions, meaning, nature="吉"):
        result.append({"名称": name, "位置": "、".join(positions), "含义": meaning, "性质": nature})

    # 天乙贵人
    for z in _TIANYI.get(dg, []):
        if z in all_zhi:
            _add("天乙贵人", _zhi_pos(z), "逢凶化吉，遇事有人相助，一生贵人运旺", "吉")

    # 驿马
    yz = _YIMA.get(nz, "")
    dz_yz = _YIMA.get(dz, "")
    if yz and yz in all_zhi:
        _add("驿马", _zhi_pos(yz), "主奔波走动，出外发展、旅行搬迁频繁", "中")
    elif dz_yz and dz_yz in all_zhi and dz_yz != yz:
        _add("驿马", _zhi_pos(dz_yz), "主奔波走动，出外发展、旅行搬迁频繁", "中")

    # 文昌
    wc = _WENCHANG.get(dg, "")
    if wc and wc in all_zhi:
        _add("文昌", _zhi_pos(wc), "聪明好学，利读书考试，文采出众", "吉")

    # 桃花
    th_nz = _TAOHUA.get(nz, "")
    th_dz = _TAOHUA.get(dz, "")
    th_set = set()
    if th_nz: th_set.add(th_nz)
    if th_dz: th_set.add(th_dz)
    for th in th_set:
        if th in all_zhi:
            _add("桃花", _zhi_pos(th), "异性缘佳，人缘好，有艺术才华", "中")

    # 华盖
    hg = _HUAGAI.get(nz, "")
    if hg and hg in all_zhi:
        _add("华盖", _zhi_pos(hg), "聪明孤高，喜宗教哲学艺术，有独特见解", "中")

    # 将星
    jx = _JIANGXING.get(nz, "")
    if jx and jx in all_zhi:
        _add("将星", _zhi_pos(jx), "有领导才能，遇事果断，可掌权", "吉")

    # 禄神
    ls = _LUSHEN.get(dg, "")
    if ls and ls in all_zhi:
        _add("禄神", _zhi_pos(ls), "衣禄丰厚，福气绵长，一生衣食无忧", "吉")

    # 羊刃(神煞意义的羊刃，与格局羊刃格不同)
    yr = _YANGREN.get(dg, "")
    if yr and yr in all_zhi:
        _add("羊刃", _zhi_pos(yr), "性格刚烈，血气方刚，需防刑伤灾祸", "凶")

    # 天德贵人 — 精确标注出现在哪个柱
    td = _TIANDE.get(mz, "")
    if td:
        td_pos = []
        for i in range(4):
            if all_gan[i] == td or td in ZHICANG[all_zhi[i]]:
                td_pos.append(pos_cn[POS[i]])
        if td_pos:
            _add("天德贵人", td_pos, "逢凶化吉，德行高尚，遇事有转机", "吉")

    # 月德贵人 — 精确标注出现在哪个柱
    yd = _YUEDE.get(mz, "")
    if yd:
        yd_pos = []
        for i in range(4):
            if all_gan[i] == yd or yd in ZHICANG[all_zhi[i]]:
                yd_pos.append(pos_cn[POS[i]])
        if yd_pos:
            _add("月德贵人", yd_pos, "化解灾厄，心地善良，福泽深厚", "吉")

    # 亡神
    ws = _WANGSHEN.get(nz, "")
    if ws and ws in all_zhi:
        _add("亡神", _zhi_pos(ws), "心机较深，需防口舌是非及官非", "凶")

    # 劫煞
    js = _JIESHA.get(nz, "")
    if js and js in all_zhi:
        _add("劫煞", _zhi_pos(js), "需防破财伤灾，行事宜谨慎", "凶")

    # 孤辰寡宿
    gc = _GUCHEN.get(nz, "")
    gx = _GUAXIU.get(nz, "")
    if gc and gc in all_zhi:
        _add("孤辰", _zhi_pos(gc), "性格偏孤，独立性较强，婚姻宜晚", "凶")
    if gx and gx in all_zhi:
        _add("寡宿", _zhi_pos(gx), "感情独立，不依赖他人，婚姻宜晚", "凶")

    return result


# ===== 精确节气计算 =====
# 12个"节"(非"气")对应月支切换
# 黄经角度 -> 节名 -> 月支
JIE_LON = [
    (315, "立春", "寅"), (345, "惊蛰", "卯"), (15,  "清明", "辰"),
    (45,  "立夏", "巳"), (75,  "芒种", "午"), (105, "小暑", "未"),
    (135, "立秋", "申"), (165, "白露", "酉"), (195, "寒露", "戌"),
    (225, "立冬", "亥"), (255, "大雪", "子"), (285, "小寒", "丑"),
]

# 节气搜索的大约起始月份
_JIE_MONTH = {
    315: (2, 1), 345: (3, 1), 15: (4, 1), 45: (5, 1),
    75: (6, 1), 105: (7, 1), 135: (8, 1), 165: (9, 1),
    195: (10, 1), 225: (11, 1), 255: (12, 1), 285: (1, 1),
}


def _calc_jieqi_date(year, target_lon_deg):
    """用ephem精确计算指定年份指定黄经角度的节气时间(北京时间)"""
    observer = ephem.Observer()
    observer.pressure = 0

    m, d_start = _JIE_MONTH[target_lon_deg]
    start_date = ephem.Date(f'{year}/{m}/{d_start}')

    # 逐步搜索找到跨越点
    d_current = start_date
    prev_lon = None
    found_range = None

    for _ in range(60):
        observer.date = d_current
        sun = ephem.Sun(observer)
        eq = ephem.Equatorial(sun.ra, sun.dec, epoch=observer.date)
        ec = ephem.Ecliptic(eq)
        lon_deg = float(ec.lon) * 180 / ephem.pi

        if prev_lon is not None:
            # 正常跨越
            if prev_lon < target_lon_deg and lon_deg >= target_lon_deg:
                found_range = (d_current - 1, d_current)
                break
            # 跨越0度(从359跳到0+)
            if prev_lon > 350 and target_lon_deg < 10 and lon_deg < 10 and lon_deg >= target_lon_deg:
                found_range = (d_current - 1, d_current)
                break

        prev_lon = lon_deg
        d_current = d_current + 1

    if found_range is None:
        return None

    # 二分法精确定位
    lo, hi = found_range
    for _ in range(60):
        mid = (lo + hi) / 2
        observer.date = mid
        sun = ephem.Sun(observer)
        eq = ephem.Equatorial(sun.ra, sun.dec, epoch=observer.date)
        ec = ephem.Ecliptic(eq)
        lon_deg = float(ec.lon) * 180 / ephem.pi

        if lon_deg < target_lon_deg:
            lo = mid
        else:
            hi = mid

        if (hi - lo) < 0.00001:
            break

    result_date = ephem.Date((lo + hi) / 2)
    dt = result_date.datetime() + datetime.timedelta(hours=8)
    return dt


# 节气日期缓存，避免重复计算
_jieqi_cache = {}


def get_jieqi_date(year, lon_deg):
    """获取节气日期(带缓存)"""
    key = (year, lon_deg)
    if key not in _jieqi_cache:
        _jieqi_cache[key] = _calc_jieqi_date(year, lon_deg)
    return _jieqi_cache[key]


def get_month_zhi_and_jieqi(year, month, day):
    """
    根据精确节气确定月支
    返回: (月支, 节气名)
    """
    # 构建本年度及前一年年末的节气日期列表
    # 需要前一年年末的节气来覆盖1月份
    jie_list = []
    for y in [year - 1, year]:
        for lon, name, zhi in JIE_LON:
            dt = get_jieqi_date(y, lon)
            if dt:
                jie_list.append((dt, name, zhi))

    # 按日期排序
    jie_list.sort(key=lambda x: x[0])

    # 找出当前日期所在的月支
    current_date = datetime.datetime(year, month, day)
    best_zhi = "子"  # 默认(大雪后子月)
    best_name = "大雪"

    for dt, name, zhi in jie_list:
        if current_date >= dt:
            best_zhi = zhi
            best_name = name
        else:
            break

    return best_zhi, best_name


# ===== 四柱 =====
# 日柱基准: 1900年1月1日 = 甲戌日 (甲=0, 戌=10)
_DAY_BASE = datetime.date(1900, 1, 1)
_DAY_BASE_GAN = 0  # 甲
_DAY_BASE_ZHI = 10  # 戌


def year_pillar(year, month, day):
    """年柱（以立春为界）"""
    lichun = get_jieqi_date(year, 315)  # 立春
    if lichun:
        lichun_date = lichun.date()
        if datetime.date(year, month, day) < lichun_date:
            year -= 1
    else:
        # fallback: 近似判断
        if month < 2 or (month == 2 and day < 4):
            year -= 1
    return GAN[(year - 4) % 10], ZHI[(year - 4) % 12]


def month_pillar(year_gan, month, day, year=None):
    """月柱（五虎遁 + 精确节气）"""
    if year is None:
        year = datetime.date.today().year

    zhi, _ = get_month_zhi_and_jieqi(year, month, day)

    # 五虎遁: 年干 -> 寅月天干
    wuhu = {"甲": 2, "己": 2, "乙": 4, "庚": 4,
            "丙": 6, "辛": 6, "丁": 8, "壬": 8,
            "戊": 0, "癸": 0}
    base = wuhu[year_gan]
    zi = ZHI_I[zhi]
    offset = (zi - 2) % 12  # 以寅(2)为0起点
    return GAN[(base + offset) % 10], zhi


def day_pillar(year, month, day):
    """日柱（基准日1900-01-01甲戌日）"""
    delta = (datetime.date(year, month, day) - _DAY_BASE).days
    return GAN[(_DAY_BASE_GAN + delta) % 10], ZHI[(_DAY_BASE_ZHI + delta) % 12]


def hour_pillar(day_gan, hour):
    """时柱（五鼠遁）"""
    if hour >= 23 or hour < 1:    z = "子"
    elif hour < 3:                z = "丑"
    elif hour < 5:                z = "寅"
    elif hour < 7:                z = "卯"
    elif hour < 9:                z = "辰"
    elif hour < 11:               z = "巳"
    elif hour < 13:               z = "午"
    elif hour < 15:               z = "未"
    elif hour < 17:               z = "申"
    elif hour < 19:               z = "酉"
    elif hour < 21:               z = "戌"
    else:                         z = "亥"

    # 五鼠遁: 日干 -> 子时天干
    wushu = {"甲": 0, "己": 0, "乙": 2, "庚": 2,
             "丙": 4, "辛": 4, "丁": 6, "壬": 6,
             "戊": 8, "癸": 8}
    base = wushu[day_gan]
    zi = ZHI_I[z]
    return GAN[(base + zi) % 10], z


def get_four_pillars(year, month, day, hour):
    """获取四柱"""
    y = year_pillar(year, month, day)
    m = month_pillar(y[0], month, day, year)
    d = day_pillar(year, month, day)
    h = hour_pillar(d[0], hour)
    return {"year": y, "month": m, "day": d, "hour": h}


# ===== 大运 =====
def _get_nearest_jieqi(year, month, day, forward=True):
    """
    获取距离出生日最近的节气日期
    forward=True: 找之后的节气(顺排)
    forward=False: 找之前的节气(逆排)
    """
    current = datetime.datetime(year, month, day)

    # 收集当年及前后一年的节气
    jie_list = []
    for y in [year - 1, year, year + 1]:
        for lon, name, zhi in JIE_LON:
            dt = get_jieqi_date(y, lon)
            if dt:
                jie_list.append(dt)

    jie_list.sort()

    if forward:
        for dt in jie_list:
            if dt > current:
                return dt
    else:
        for dt in reversed(jie_list):
            if dt <= current:
                return dt
    return None


def calc_dayun(sex, year_gan, month_tuple, birth_year, birth_month, birth_day):
    """计算大运（起运年龄基于节气天数）"""
    yang = year_gan in ["甲", "丙", "戊", "庚", "壬"]
    forward = (sex == "男" and yang) or (sex == "女" and not yang)
    direction = 1 if forward else -1

    # 计算起运年龄
    nearest_jq = _get_nearest_jieqi(birth_year, birth_month, birth_day, forward=forward)
    if nearest_jq:
        birth_dt = datetime.datetime(birth_year, birth_month, birth_day)
        days_diff = abs((nearest_jq - birth_dt).days)
        qi_yun = round(days_diff / 3)  # 三天折一年
        qi_yun = max(1, min(qi_yun, 10))  # 限制在1-10岁之间
    else:
        qi_yun = 5  # 默认5岁

    mg, mz = month_tuple
    mgi = GAN_I[mg]
    mzi = ZHI_I[mz]

    result = []
    for i in range(1, 9):  # 8步大运
        gi = (mgi + direction * i) % 10
        zi = (mzi + direction * i) % 12
        g = GAN[gi]
        z = ZHI[zi]
        age_start = qi_yun + (i - 1) * 10
        age_end = age_start + 9
        result.append({
            "step": i, "gan": g, "zhi": z,
            "age_start": age_start, "age_end": age_end
        })

    return qi_yun, result


# ===== 命盘分析 =====
POS = ["year", "month", "day", "hour"]


def analyze_bazi(fp, sex="男"):
    dg = fp["day"][0]
    dz = fp["day"][1]
    dwx = WXG[dg]

    # 十神(天干十神 + 地支本气十神 + 藏干十神列表)
    ss = {}
    for p in POS:
        g, z = fp[p]
        cang = ZHICANG[z]
        ss[p] = {
            "干": SHISHEN[dg][g],
            "支": SHISHEN[dg][cang[0]],   # 地支本气十神
            "支藏": cang,                    # 地支藏干
            "支藏十神": [SHISHEN[dg][c] for c in cang]  # 各藏干对应的十神
        }

    # 五行统计
    wx = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
    for p in POS:
        g, z = fp[p]
        wx[WXG[g]] += 1
        wx[WXZ[z]] += 1

    # 日主旺衰判断
    mz = fp["month"][1]
    # 月支当令五行: 辰戌丑未属土(四季月土旺)
    # 寅卯属木, 巳午属火, 申酉属金, 亥子属水
    sw = {"寅": "木", "卯": "木", "辰": "土", "巳": "火", "午": "火", "未": "土",
          "申": "金", "酉": "金", "戌": "土", "亥": "水", "子": "水", "丑": "土"}
    deling = sw.get(mz) == dwx

    # 得地: 日支藏干中有与日主同五行的天干
    dc_list = ZHICANG[dz]
    dedi = any(WXG.get(c, "") == dwx for c in dc_list)

    # 得势: 其他三柱天干中有比劫或印绶
    others = [fp[p][0] for p in POS if p != "day"]
    bj = {"比肩", "劫财"}
    yn = {"正印", "偏印"}
    deshi = any(SHISHEN[dg][g] in bj or SHISHEN[dg][g] in yn for g in others)

    # 综合旺衰评分(考虑藏干力量)
    # 得令(月令): 3分
    # 得地(日支有根): 2分
    # 得势(有比劫/印绶): 2分
    # 月支藏干中有生扶: +1分
    # 年支/时支藏干有生扶: 各+0.5分
    # 生我者(印绶五行): 金->土, 木->水, 水->金, 火->木, 土->火
    sheng_wo = {"金": "土", "木": "水", "水": "金", "火": "木", "土": "火"}
    score = (3 if deling else 0) + (2 if dedi else 0) + (2 if deshi else 0)
    # 月支藏干生扶加分(与日主同五行或生我者)
    mz_cang = ZHICANG[mz]
    if any(WXG.get(c, "") == dwx or WXG.get(c, "") == sheng_wo.get(dwx, "") for c in mz_cang):
        score += 1
    # 年支/时支藏干生扶加分
    for pos_zhi in [fp["year"][1], fp["hour"][1]]:
        cang = ZHICANG[pos_zhi]
        if any(WXG.get(c, "") == dwx or WXG.get(c, "") == sheng_wo.get(dwx, "") for c in cang):
            score += 0.5
    rst = "身强" if score >= 5 else ("中和" if score >= 3 else "身弱")

    # 喜用神
    # 五行生克关系
    kem = {"金": "火", "木": "金", "水": "土", "火": "水", "土": "木"}   # 克我者(官杀)
    wok = {"金": "木", "木": "土", "水": "火", "火": "金", "土": "水"}   # 我克者(财星/耗)
    wos = {"金": "水", "木": "火", "水": "木", "火": "土", "土": "金"}   # 我生者(食伤/泄)
    sw2 = {"金": "土", "木": "水", "水": "金", "火": "木", "土": "火"}   # 生我者(印绶)
    tb  = {"金": "木", "木": "土", "水": "火", "火": "金", "土": "水"}   # 同我者(比劫)

    # 统计命局中各十神的力量(用于通关判断)
    yin_force = 0  # 印绶力量(天干2分, 地支本气1分)
    bi_force  = 0    # 比劫力量
    for p in POS:
        g, z = fp[p]
        sk = SHISHEN[dg][g]
        if sk in ("正印", "偏印"):
            yin_force += 2
        if sk in ("比肩", "劫财"):
            bi_force += 2
        cz = ZHICANG[z][0]
        skz = SHISHEN[dg][cz]
        if skz in ("正印", "偏印"):
            yin_force += 1
        if skz in ("比肩", "劫财"):
            bi_force += 1

    if rst == "身强":
        # 身强喜克泄耗
        # 用神选取(按优先级):
        #   1. 克我(官杀) - 制约身强, 第一优先
        #      需通关检查: 如果印绶旺, 官杀生印通关 -> 官杀不是好用神, 不加
        #   2. 我生(食伤) - 泄秀, 第二优先, 永远有利
        #   3. 我克(财星) - 耗身, 第三优先, 需财星有根才真有利
        xy = []
        # 1. 克我(官杀) - 第一用神(需通关检查)
        w = kem[dwx]
        if w not in xy and yin_force < 4:
            xy.append(w)
        # 2. 我生(食伤) - 第二用神(永远有利)
        w = wos[dwx]
        if w not in xy:
            xy.append(w)
        # 3. 我克(财星) - 第三用神(需财星有根)
        wx_wok = wok[dwx]
        cai_you_gen = False
        for p in POS:
            z = fp[p][1]
            for c in ZHICANG[z]:
                if WXG.get(c, "") == wok[dwx]:
                    cai_you_gen = True
        if wx_wok not in xy and cai_you_gen:
            xy.append(wx_wok)
    elif rst == "身弱":
        # 身弱喜生扶
        #   1. 生我(印绶) - 第一用神
        #   2. 同我(比劫) - 第二用神
        xy = []
        w = sw2[dwx]
        if w not in xy:
            xy.append(w)
        w = tb[dwx]
        if w not in xy:
            xy.append(w)
    else:
        # 中和: 喜用神兼顾生扶和克泄, 取调候用神
        # 简化: 取"生我"(印绶)和"我生"(食伤)为用神
        xy = []
        w = sw2[dwx]
        if w not in xy:
            xy.append(w)
        w = wos[dwx]
        if w not in xy:
            xy.append(w)

    # 格局(基于月支本气透干论格)
    mc2 = ZHICANG[fp["month"][1]][0]
    gjss = SHISHEN[dg].get(mc2, "")
    gjmap = {"正官": "正官格", "七杀": "七杀格", "正财": "正财格", "偏财": "偏财格",
             "食神": "食神格", "伤官": "伤官格", "正印": "正印格", "偏印": "偏印格",
             "比肩": "建禄格", "劫财": "羊刃格"}
    gj = gjmap.get(gjss, "杂格")

    return {
        "日主": dg, "日主五行": dwx, "日主状态": rst,
        "得令": deling, "得地": dedi, "得势": deshi,
        "五行统计": wx, "十神": ss, "喜用神": xy, "格局": gj,
        "神煞": calc_shensha(fp, sex),
        "纳音": {
            "年": nayin(fp["year"][0], fp["year"][1]),
            "月": nayin(fp["month"][0], fp["month"][1]),
            "日": nayin(fp["day"][0], fp["day"][1]),
            "时": nayin(fp["hour"][0], fp["hour"][1]),
        }
    }


# ===== 分类分析 =====
def _cnt(ss, ss2):
    n = 0
    for p in POS:
        if ss[p]["干"] in ss2:
            n += 1
        if ss[p]["支"] in ss2:
            n += 1
    return n


def ana_wealth(bz):
    n = _cnt(bz["十神"], {"正财", "偏财"})
    rst = bz["日主状态"]
    if n >= 3:
        return {"等级": "财旺", "详情": "命盘中财星多见，天生具有赚钱能力。"}
    elif n >= 1 and rst == "身强":
        return {"等级": "财运中上", "详情": "命中有财星且身强能担财。"}
    elif n >= 1:
        return {"等级": "财运中等", "详情": "命中有财星但身弱，宜稳妥理财。"}
    else:
        return {"等级": "以技生财", "详情": "命盘财星不显，适合凭专业技能谋生。"}


def ana_career(bz):
    gj = bz["格局"]
    wx = bz["日主五行"]
    indu = {"金": ["金融", "法律", "机械"], "木": ["教育", "文化", "医疗"],
            "水": ["贸易", "物流", "旅游"], "火": ["能源", "餐饮", "影视"],
            "土": ["房地产", "建筑", "农业"]}
    ss = bz["十神"]
    hg = any(ss[p]["干"] in ("正官", "七杀") or ss[p]["支"] in ("正官", "七杀") for p in POS)
    if "正官" in gj or "七杀" in gj:
        return {"等级": "官贵之命", "详情": "命带官杀，适合公职管理岗位。", "适合行业": indu.get(wx, [])}
    elif "食神" in gj or "伤官" in gj:
        return {"等级": "才华之命", "详情": "食伤吐秀，聪明有才华。", "适合行业": indu.get(wx, [])}
    elif "正财" in gj or "偏财" in gj:
        return {"等级": "经商之才", "详情": "财星为用，有经济头脑。", "适合行业": indu.get(wx, [])}
    elif hg:
        return {"等级": "事业有成", "详情": "官星有现，事业心强。", "适合行业": indu.get(wx, [])}
    else:
        return {"等级": "专业人才", "详情": "适合走专业技术路线。", "适合行业": indu.get(wx, [])}


def ana_marriage(bz, sex):
    star = {"正财", "偏财"} if sex == "男" else {"正官", "七杀"}
    ss = bz["十神"]
    hg = any(ss[p]["干"] in star for p in POS)
    hz = any(ss[p]["支"] in star for p in POS)
    if hg and hz:
        lv, q = "婚姻美满", "夫妻宫有配偶星坐守。"
    elif hg or hz:
        lv, q = "婚姻平顺", "配偶星有现，婚姻可成。"
    else:
        lv, q = "晚婚为宜", "配偶星不显，宜晚婚。"
    dss = ss["day"]["支"]
    if dss in ("正官", "正财", "正印"):
        sc = "配偶品行端正，婚姻和谐。"
    elif dss in ("七杀", "偏财", "伤官"):
        sc = "配偶性格较强，需注意磨合。"
    else:
        sc = "夫妻宫需用心经营。"
    return {"等级": lv, "婚姻质量": q, "配偶特征": sc,
            "配偶星": "妻星（财星）" if sex == "男" else "夫星（官星）"}


def ana_children(bz, sex):
    star = {"正官", "七杀"} if sex == "男" else {"食神", "伤官"}
    n = _cnt(bz["十神"], star)
    if n >= 2:
        return {"等级": "子女缘厚", "详情": "子女缘深厚。"}
    elif n >= 1:
        return {"等级": "子女缘中等", "详情": "有子女缘，子女可成才。"}
    else:
        return {"等级": "子女缘薄", "详情": "子女星不显，宜晚育。"}


def ana_siblings(bz):
    n = _cnt(bz["十神"], {"比肩", "劫财"})
    if n >= 2:
        return {"等级": "兄弟有助", "详情": "兄弟姐妹多，手足情深。"}
    elif n >= 1:
        return {"等级": "兄弟缘中等", "详情": "有兄弟姐妹，助力有限。"}
    else:
        return {"等级": "独立发展", "详情": "兄弟姐妹较少，宜自立自强。"}


def ana_parents(bz):
    ss = bz["十神"]
    mp = [p for p in POS if ss[p]["干"] in ("正印", "偏印") or ss[p]["支"] in ("正印", "偏印")]
    fp2 = [p for p in POS if ss[p]["干"] in ("正财", "偏财") or ss[p]["支"] in ("正财", "偏财")]
    pos_name = {"year": "年柱", "month": "月柱", "day": "日柱", "hour": "时柱"}
    mp_str = "、".join([pos_name.get(p, p) for p in mp]) if mp else "命盘不显"
    fp_str = "、".join([pos_name.get(p, p) for p in fp2]) if fp2 else "命盘不显"
    return {
        "母亲": f"印星现于「{mp_str}」，母亲{'助力大。' if mp else '缘分稍薄。'}",
        "父亲": f"财星现于「{fp_str}」，父亲{'有能力。' if fp2 else '缘分稍薄。'}"
    }


def ana_health(wx):
    hm = {"金": "呼吸系统、肺部", "木": "肝胆、四肢", "水": "肾脏、泌尿系统",
          "火": "心脏、血液循环", "土": "脾胃、消化系统"}
    iss = []
    for w, c in wx.items():
        if c == 0 or c >= 4:
            if w in hm:
                iss.append(hm[w])
    iss = list(set(iss))
    if not iss:
        return {"等级": "身体健康", "详情": "五行相对平衡。"}
    return {"等级": "注意保养", "详情": "需注意：" + "；".join(iss) + "。建议定期体检。"}


# ===== 大运分析(结合命理四书) =====

# 命理四书经典引用
_DTS = {  # 滴天髓
    "正官": "《滴天髓》云：「正官配印，名利双收。」官星得用，仕途通达。",
    "七杀": "《滴天髓》云：「杀无制则为小人，杀有制则为君子。」七杀需制化方吉。",
    "正财": "《滴天髓》云：「财旺生官，富贵双全。」财星得地，家境殷实。",
    "偏财": "《滴天髓》云：「偏财慷慨，交际通达。」偏财运中有人缘助力。",
    "食神": "《滴天髓》云：「食神吐秀，才华盖世。」食神泄秀，学业有成。",
    "伤官": "《滴天髓》云：「伤官见官，其祸百端。」伤官需配印制化方安。",
    "正印": "《滴天髓》云：「印绶相生，文华盖世。」印绶护身，贵人扶持。",
    "偏印": "《滴天髓》云：「枭神夺食，贫寒孤苦。」偏印需防夺食之患。",
    "比肩": "《滴天髓》云：「比肩争财，竞争多端。」比肩运中需防争夺。",
    "劫财": "《滴天髓》云：「劫财争财，破耗不宁。」劫财运中须防灾耗。",
}
_ZPZQ = {  # 子平真诠
    "正官": "《子平真诠》：「正官之格，最为清贵。」行正官运宜守正求稳。",
    "七杀": "《子平真诠》：「七杀喜制，制之太过反凶。」行杀运需有制方吉。",
    "正财": "《子平真诠》：「财为养命之源，不可无。」正财运中宜勤恳理财。",
    "偏财": "《子平真诠》：「偏财众则忌比劫。」行偏财运须防争夺破财。",
    "食神": "《子平真诠》：「食神最忌枭印夺之。」食神运中需防偏印夺食。",
    "伤官": "《子平真诠》：「伤官用印，贵在印星。」伤官运中配印方吉。",
    "正印": "《子平真诠》：「印绶喜官煞生之。」印运中遇官则贵。",
    "偏印": "《子平真诠》：「偏印见食神，须防灾祸。」偏印运宜谨慎行事。",
    "比肩": "《子平真诠》：「比肩帮身，身旺则忌。」比肩运需审身之强弱。",
    "劫财": "《子平真诠》：「劫财阳刃，切忌财旺。」劫财运中须守财防破。",
}


def _dayun_score(ssg, ssz, bz, xy, dy_gan, dy_zhi, age_start=0, age_end=9):
    """
    计算大运评分(1-100)
    基于: 十神吉凶 + 喜用神契合度 + 旺衰配合 + 年龄阶段权重
    """
    score = 60  # 基础分
    dg = bz["日主"]
    rst = bz["日主状态"]
    avg_age = (age_start + age_end) / 2

    # 1. 喜用神契合(+/- 15分)
    if WXG.get(dy_gan, "") in xy:
        score += 8
    if WXZ.get(dy_zhi, "") in xy:
        score += 7

    # 2. 十神吉凶调整(+/- 15分) — 结合年龄阶段
    ji_shen = {"正官", "正财", "正印", "食神"}
    xiong_shen = {"七杀", "伤官", "劫财", "偏印"}
    if ssg in ji_shen:
        score += 10
    elif ssg in xiong_shen:
        if rst == "身强" and ssg in ("七杀", "伤官"):
            score += 5
        else:
            # 少年期间偏印不一定是坏事（聪明好学）
            if ssg == "偏印" and avg_age <= 20:
                score -= 2
            else:
                score -= 8
    elif ssg == "比肩":
        if rst == "身弱":
            score += 5
        else:
            score -= 3
    elif ssg == "偏财":
        score += 3

    # 3. 地支十神调整(+/- 8分)
    if ssz in ji_shen:
        score += 5
    elif ssz in xiong_shen:
        score -= 4

    # 4. 格局配合(+/- 5分)
    gj = bz.get("格局", "")
    if "正官" in gj and ssg in ("正官", "正印"):
        score += 3
    if "食神" in gj and ssg == "偏印":
        score -= 5
    if "七杀" in gj and ssg in ("食神", "正印"):
        score += 3

    return max(10, min(95, score))


def _age_stage(age_start, age_end):
    """返回年龄阶段信息"""
    avg = (age_start + age_end) / 2
    if avg <= 10:
        return "少年", "此为少年时期，重在学业与成长，受父母庇护"
    elif avg <= 20:
        return "青春", "此为青春时期，学业为重，初涉人际与感情"
    elif avg <= 30:
        return "青年", "此为青年时期，事业起步，婚姻大事提上日程"
    elif avg <= 50:
        return "壮年", "此为壮年时期，事业家庭双肩挑，财富积累关键期"
    elif avg <= 70:
        return "中年", "此为中年时期，重在健康养生，子女成长，收获人生果实"
    else:
        return "晚年", "此为晚年时期，福泽安康为要，颐养天年"


def _dayun_detail(ssg, ssz, bz, sex, score, age_start=0, age_end=9):
    """
    生成大运各维度详细分析(结合命理四书 + 年龄阶段)
    返回: {"财富":..., "事业":..., "婚姻":..., "健康":..., "学业":..., "人际":...}
    """
    rst = bz["日主状态"]
    dg = bz["日主"]
    xy = bz.get("喜用神", [])
    dwx = bz["日主五行"]

    # 各维度分析模板
    wealth_desc = {
        "正财": "正财运主正当财源，工薪收入稳定增长。《穷通宝鉴》言：「财星得地，家业可兴。」宜稳健投资。",
        "偏财": "偏财运主意外之财、投资收益。《穷通宝鉴》言：「偏财旺相，横财可期。」但须防贪多必失。",
        "正官": "官星护财，有贵人助理财。官星当权，正当收入有保障，可争取加薪升职。",
        "七杀": "杀星克身，财运压力增大。需谨慎理财，不宜冒险投资，宜守不宜攻。",
        "食神": "食神生财，财源广进。《滴天髓》言：「食神吐秀，财运亨通。」适合以才华技艺生财。",
        "伤官": "伤官生财，有赚钱机会但需防破耗。宜凭技艺谋财，不宜投机取巧。",
        "正印": "印绶护身，财运平稳。印旺则身旺，可担大财，但不宜急进。",
        "偏印": "偏印运中财路受限，需防偏印夺食影响收入。宜稳中求进。",
        "比肩": "比肩分财，财运有竞争。需防同辈争夺财源，宜独立经营。",
        "劫财": "劫财争财，易有破耗。《子平真诠》言：「劫财阳刃，切忌财旺。」须防灾耗破财。",
    }
    career_desc = {
        "正官": "正官运主仕途通达、职场晋升。《子平真诠》言：「正官之格，最为清贵。」此运宜守正谋事，仕途可期。",
        "七杀": "七杀运主压力与权力并存。《滴天髓》言：「杀有制则为君子。」此运有魄力但需制衡，事业可有大突破。",
        "正财": "正财运中事业稳健，适合经营实业。《穷通宝鉴》言：「财旺生官，事业有成。」脚踏实地可获成就。",
        "偏财": "偏财运中有人缘助力，适合商务交际。善用人脉可开拓事业新版图。",
        "食神": "食神运中才华展露，适合文化创意。《滴天髓》言：「食神吐秀，才华盖世。」此运可凭才华立业。",
        "伤官": "伤官运中思想活跃，有创新但易叛逆。《子平真诠》言：「伤官用印，贵在印星。」需配印星方可成事。",
        "正印": "印运主学业晋升、贵人扶持。《滴天髓》言：「印绶相生，文华盖世。」此运利考试、升职。",
        "偏印": "偏印运中思维独特，适合研究创新。但需防枭神夺食，不宜贪多。",
        "比肩": "比肩运中同行竞争激烈，宜独立创业或强化自身优势。合作需谨慎。",
        "劫财": "劫财运中事业竞争大，须防合伙纠纷。《子平真诠》言：「劫财争财，破耗不宁。」宜守不宜进。",
    }
    marriage_desc = {
        "正官": "正官运中感情正缘显现，利婚嫁。《三命通会》言：「官星得力，夫荣妻贵。」此运婚姻和美。",
        "七杀": "七杀运中感情波折，异性缘强但需防烂桃花。已婚者需多沟通，未婚者宜审慎选择。",
        "正财": "正财运中男命利婚，妻缘佳。《穷通宝鉴》言：「财星为妻，得地则妻贤。」此运婚姻稳固。",
        "偏财": "偏财运中异性缘旺，男命需防外遇。宜洁身自好，珍惜眼前人。",
        "食神": "食神运中感情温和，家庭氛围融洽。利添丁之喜，子女缘厚。",
        "伤官": "伤官运中感情易生变故。《滴天髓》言：「伤官见官，其祸百端。」已婚者防口角，未婚者防错配。",
        "正印": "印运中家庭温馨，长辈助力大。利添丁、置业，家和万事兴。",
        "偏印": "偏印运中感情偏冷，需防疏离。宜多关心伴侣，增进感情。",
        "比肩": "比肩运中感情有竞争对手。须防第三者介入，宜坦诚相待。",
        "劫财": "劫财运中感情不稳，男命须防夺妻之象。宜谨慎处理感情纠纷。",
    }
    health_desc = {
        "正官": "官星运中身体尚可，但需防过度劳累。注意作息规律，劳逸结合。",
        "七杀": "杀运中须防意外伤灾。《三命通会》言：「杀重身轻，灾祸难免。」注意安全，定期体检。",
        "正财": "财运中身体状况平稳。但财多身弱者需防脾胃不适，注意饮食。",
        "偏财": "偏财运中需防纵欲伤身。注意节制，保持规律生活。",
        "食神": "食神运中饮食丰厚，但需防贪食伤脾。《滴天髓》言：「食神吐秀，福禄双全。」注意饮食健康。",
        "伤官": "伤官运中需防呼吸系统、肺部问题。注意保暖防感，避免过劳。",
        "正印": "印运中身体得养，恢复力强。但仍需注意五行偏旺对应器官。",
        "偏印": "偏印运中精神压力大，需防失眠焦虑。宜放松心情，适当运动。",
        "比肩": "比肩运中体质尚可，但竞争压力需调节。注意心理健康。",
        "劫财": "劫财运中需防血光之灾、手术伤灾。注意安全，远离危险。",
    }
    study_desc = {
        "正官": "官运中利考公务员、职称考试。守正求学，功名可期。",
        "七杀": "杀运中有压力但亦有动力，利突破性学习。化压力为动力可有成就。",
        "正财": "财运中学习偏实用，利财务、经商类进修。宜学以致用。",
        "偏财": "偏财运中学习面广但不够专注。宜集中精力深耕一域。",
        "食神": "食神运中利文学艺术创作，才华横溢。《滴天髓》言：「食神吐秀，文华盖世。」",
        "伤官": "伤官运中思维活跃，利创新研究。但需防恃才傲物，宜谦逊求学。",
        "正印": "印运大利学业！《滴天髓》言：「印绶相生，文华盖世。」利考试、升学、进修。",
        "偏印": "偏印运中利非主流学科研究、玄学、技术专研。思维独特但需坚持。",
        "比肩": "比肩运中利团队学习、竞赛。与同辈切磋可进步，但需避免攀比。",
        "劫财": "劫财运中学习不够专注，易分心。宜静心修学，戒骄戒躁。",
    }
    social_desc = {
        "正官": "官运中人缘正直，有领导缘。易得上级赏识，社会地位提升。",
        "七杀": "杀运中人际关系有张力，需以德服人。有魄力但须防树敌。",
        "正财": "财运中人缘随和，和气生财。社交以利合，注意分辨真伪。",
        "偏财": "偏财运中人缘极佳，交际广泛。善用人脉可成大事，但需防酒肉朋友。",
        "食神": "食神运中人人亲近，口碑好。利公关、服务类社交，人见人爱。",
        "伤官": "伤官运中口才出众但易得罪人。《子平真诠》言：「伤官傲物。」宜谨言慎行。",
        "正印": "印运中长辈缘佳，有贵人提携。利与年长者、师辈交往。",
        "偏印": "偏印运中人际偏冷，喜独处。宜适度社交，避免孤立。",
        "比肩": "比肩运中同辈缘佳，但竞争也多。宜合作共赢，避免内耗。",
        "劫财": "劫财运中须防被夺、被骗。社交需谨慎，不宜借贷担保。",
    }

    def _pick(d, k1, k2=None):
        return d.get(k1, "此运平稳，宜安分守己。")

    # 根据天干十神为主分析
    detail = {
        "财富": _pick(wealth_desc, ssg),
        "事业": _pick(career_desc, ssg),
        "婚姻": _pick(marriage_desc, ssg),
        "健康": _pick(health_desc, ssg),
        "学业": _pick(study_desc, ssg),
        "人际": _pick(social_desc, ssg),
    }

    # 如果地支十神与天干十神不同，补充说明
    if ssz != ssg:
        if ssz == "偏财" and ssg not in ("偏财", "正财"):
            detail["财富"] += " 地支偏财暗藏，有隐性财路。"
        elif ssz == "正印" and ssg not in ("正印", "偏印"):
            detail["学业"] += " 地支印星暗助，学业有暗中贵人。"
        elif ssz == "七杀" and ssg != "七杀":
            detail["健康"] += " 地支暗藏杀星，需防意外。"

    # 年龄阶段特殊补充
    stage, stage_desc = _age_stage(age_start, age_end)
    avg_age = (age_start + age_end) / 2
    if stage == "少年":
        # 少年期: 学业和健康最重要，偏印=聪明好学而非凶
        if ssg == "偏印":
            detail["学业"] = detail["学业"].replace("偏印运中思维独特，适合研究创新。但需防枭神夺食，不宜贪多。",
                "少年行偏印运，思维独特，领悟力极强，利读书学习。宜专心学业，可脱颖而出。")
        detail["婚姻"] = "少年时期婚姻尚早，此运主要影响家庭氛围和父母关系。"
    elif stage == "青春":
        # 青春期: 学业+人际+感情萌芽
        if ssg in ("正财", "偏财") and sex == "男":
            detail["婚姻"] = "青春时期感情萌芽，异性缘初现。宜以学业为重，不可过早沉溺。"
    elif stage == "青年":
        # 青年期: 事业+婚姻
        pass  # 默认描述已经很适合
    elif stage == "壮年":
        # 壮年期: 财富+事业+子女
        pass
    elif stage == "中年":
        # 中年期: 健康+子女
        if ssg == "伤官":
            detail["健康"] += " 中年需特别注意身体信号，不宜过劳。"
    elif stage == "晚年":
        # 晚年期: 健康+福泽
        detail["学业"] = "晚年宜修身养性，含饴弄孙，享受人生智慧。"

    return detail


def ana_dayun_list(dl, bz, sex="男"):
    """大运分析(结合命理四书，多维度评分，年龄阶段)"""
    dg = bz["日主"]
    xy = bz.get("喜用神", [])
    res = []
    for dy in dl:
        g, z = dy["gan"], dy["zhi"]
        ssg = SHISHEN[dg][g]        # 天干十神
        ssz = SHISHEN[dg][ZHICANG[z][0]]  # 地支本气十神
        age_start = dy.get("age_start", 0)
        age_end = dy.get("age_end", 9)

        # 计算评分
        score = _dayun_score(ssg, ssz, bz, xy, g, z, age_start, age_end)

        # 各维度分析
        detail = _dayun_detail(ssg, ssz, bz, sex, score, age_start, age_end)

        # 年龄阶段
        stage, stage_desc = _age_stage(age_start, age_end)

        # 吉凶判断
        if score >= 75:
            luck = "大吉"
        elif score >= 60:
            luck = "吉"
        elif score >= 45:
            luck = "平"
        elif score >= 30:
            luck = "小凶"
        else:
            luck = "凶"

        # 四书引用
        dts_quote = _DTS.get(ssg, "")
        zpzq_quote = _ZPZQ.get(ssg, "")

        # 综合概述(结合年龄阶段)
        summary = f"【{stage}】{stage_desc}。行{ssg}运，"
        if score >= 70:
            summary += "运势顺遂，宜积极进取。"
        elif score >= 55:
            summary += "运势平稳，宜守成待时。"
        elif score >= 40:
            summary += "运势欠佳，需审慎行事。"
        else:
            summary += "运势低迷，宜韬光养晦。"

        res.append({
            "步数": dy["step"], "大运": f"{g}{z}",
            "年龄": f"{dy['age_start']}-{dy['age_end']}岁",
            "天干十神": ssg, "地支十神": ssz,
            "评分": score, "吉凶": luck,
            "概述": summary,
            "各维度": detail,
            "滴天髓": dts_quote,
            "子平真诠": zpzq_quote,
        })
    return res


# ===== 流年分析 =====
# 六合
_LIUHE = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
          "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}
# 六冲
_LIUCHONG = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
             "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}
# 三合
_SANHE = {"申": "水", "子": "水", "辰": "水", "寅": "木", "午": "木", "戌": "木",
          "巳": "金", "酉": "金", "丑": "金", "亥": "火", "卯": "火", "未": "火"}


def calc_liunian_list(birth_year, fp, bz, dy_step_info=None):
    """
    计算当前大运下所有流年的详细分析
    birth_year: 出生公历年
    fp: 四柱
    bz: 八字分析结果
    dy_step_info: 当前大运信息 {"age_start":..., "age_end":..., "gan":..., "zhi":...}
    """
    dg = bz["日主"]
    xy = bz.get("喜用神", [])
    result = []

    if not dy_step_info:
        return result

    start_y = birth_year + dy_step_info["age_start"]
    end_y = birth_year + dy_step_info["age_end"]

    # 大运天干十神
    dy_ssg = SHISHEN[dg][dy_step_info["gan"]]

    for y in range(start_y, end_y + 1):
        gi = (y - 4) % 10
        zi = (y - 4) % 12
        g, z = GAN[gi], ZHI[zi]
        ssg = SHISHEN[dg][g]        # 流年天干十神
        ssz = SHISHEN[dg][ZHICANG[z][0]]  # 流年地支本气十神

        # 流年与命局的冲合关系
        chong = []  # 冲
        he = []     # 合
        for p in POS:
            pz = fp[p][1]
            if _LIUCHONG.get(z) == pz:
                chong.append(f"流年{z}冲{p}柱{pz}")
            if _LIUHE.get(z) == pz:
                he.append(f"流年{z}合{p}柱{pz}")

        # 流年吉凶评分
        score = 55
        if WXG.get(g, "") in xy:
            score += 10
        if WXZ.get(z, "") in xy:
            score += 8
        if ssg in ("正官", "正财", "正印", "食神"):
            score += 8
        elif ssg in ("七杀", "伤官", "劫财"):
            if bz["日主状态"] == "身强" and ssg in ("七杀", "伤官"):
                score += 4
            else:
                score -= 8
        if chong:
            score -= 5
        if he:
            score += 3
        # 大运+流年组合加分
        if dy_ssg in ("正官", "正财", "正印", "食神") and ssg in ("正官", "正财", "正印", "食神"):
            score += 5
        score = max(10, min(95, score))

        # 简评
        if score >= 70:
            brief = "流年吉利"
        elif score >= 55:
            brief = "流年平稳"
        elif score >= 40:
            brief = "流年欠佳"
        else:
            brief = "流年不利"

        # 重点提示
        tips = []
        if chong:
            tips.append("⚠️" + "；".join(chong))
        if he:
            tips.append("✅" + "；".join(he))
        if ssg == "正财" or ssg == "偏财":
            tips.append("💰利财运")
        if ssg == "正官" or ssg == "七杀":
            tips.append("💼事业变动")
        if ssg == "正印":
            tips.append("📚利学业")
        if ssg == "伤官":
            tips.append("⚡防口舌")

        result.append({
            "年份": y, "干支": f"{g}{z}",
            "天干十神": ssg, "地支十神": ssz,
            "评分": score, "简评": brief,
            "冲合": tips,
            "五行": f"{WXG[g]}/{WXZ[z]}",
        })

    return result


# ===== 命理总论 =====
def gen_overview(bz, sex):
    dg = bz["日主"]
    dwx = bz["日主五行"]
    rst = bz["日主状态"]
    gj = bz["格局"]
    xy = bz.get("喜用神", [])
    xg = {"甲": "如参天大树，性格正直刚毅。", "乙": "如柔韧花草，性格温和灵活。",
          "丙": "如烈日当空，性格热情开朗。", "丁": "如烛火灯明，性格内秀含蓄。",
          "戊": "如广袤大地，性格沉稳厚重。", "己": "如沃土良田，性格谦和务实。",
          "庚": "如精钢利刃，性格刚强果决。", "辛": "如珠玉宝石，性格精致内敛。",
          "壬": "如大海江河，性格豁达包容。", "癸": "如溪流雨露，性格温润细腻。"}
    gjtx = {"正官格": "为人端正，有管理才能。", "七杀格": "性格刚烈，有魄力有野心。",
            "正财格": "为人勤恳踏实，善于理财经营。", "偏财格": "善于交际，有经济头脑。",
            "食神格": "性格温和善良，才华出众。", "伤官格": "聪明绝顶，才华横溢。",
            "正印格": "为人仁慈宽厚，学识渊博。", "偏印格": "思维独特，善于钻研。",
            "建禄格": "自立自强，有独立创业能力。", "羊刃格": "性格刚强好胜，有冲劲。",
            "杂格": "格局复杂，命主多才多艺。"}
    if rst == "身强":
        zs = f"命主身强，宜行克泄耗之运（{'、'.join(xy)}）。"
    elif rst == "身弱":
        zs = f"命主身弱，宜行印比之运（{'、'.join(xy)}）。"
    else:
        zs = "命主中和，五行较为平衡，一生运势平稳。"
    wc = {"金": "白色、银色", "木": "绿色、青色", "水": "黑色、蓝色", "火": "红色、紫色", "土": "黄色、棕色"}
    wf = {"金": "西方", "木": "东方", "水": "北方", "火": "南方", "土": "中央"}
    ws = {"金": "4、9", "木": "3、8", "水": "1、6", "火": "2、7", "土": "5、0"}
    x1 = xy[0] if xy else dwx
    x2 = xy[1] if len(xy) > 1 else x1
    adv = f"【开运建议】喜用神为{x1}、{x2}，宜穿{wc.get(x1, '')}衣物，居室宜朝{wf.get(x1, '')}，幸运数字为{ws.get(x1, '')}。"
    parts = [f"【日主性格】{xg.get(dg, '')}", f"【格局论命】{gjtx.get(gj, '')}", f"【命运走势】{zs}", adv]
    yn = bz.get("纳音", {})
    if yn.get("年"):
        parts.append(f"【年柱纳音】{yn['年']}")
    if yn.get("日"):
        parts.append(f"【日柱纳音】{yn['日']}")
    return "\n\n".join(parts)


# ===== 主入口 =====
def full_analysis(year, month, day, hour, sex, birthplace=""):
    fp = get_four_pillars(year, month, day, hour)
    fp2 = {k: list(v) for k, v in fp.items()}
    bz = analyze_bazi(fp, sex)
    qi, dl = calc_dayun(sex, fp["year"][0], tuple(fp["month"]), year, month, day)
    bz["起运年龄"] = qi
    bz["大运"] = dl
    bz["四柱"] = fp2
    bz["各方面分析"] = {
        "财富": ana_wealth(bz), "事业": ana_career(bz),
        "婚姻": ana_marriage(bz, sex), "子女": ana_children(bz, sex),
        "兄弟": ana_siblings(bz), "父母": ana_parents(bz),
        "健康": ana_health(bz["五行统计"]),
    }
    bz["大运分析"] = ana_dayun_list(dl, bz, sex)
    # 每步大运下的流年分析
    bz["流年"] = {}
    for dy in dl:
        step = dy["step"]
        bz["流年"][str(step)] = calc_liunian_list(year, fp, bz, dy)
    bz["命理总论"] = gen_overview(bz, sex)
    bz["基本信息"] = {"性别": sex, "出生地": birthplace,
                         "公历": f"{year}年{month}月{day}日{hour}时"}
    return bz


if __name__ == "__main__":
    r = full_analysis(1990, 6, 15, 12, "男", "北京")
    import json
    print(json.dumps(r, ensure_ascii=False, indent=2))
