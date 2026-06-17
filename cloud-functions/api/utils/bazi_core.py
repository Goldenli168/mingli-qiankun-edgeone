"""
命理乾坤 · 八字核心计算引擎 v5.0
新增: 神煞系统、大运四书分析、多维度评分
修正: 日柱基准、十神映射、节气月支、大运起运、喜用神通关
"""
import datetime
import ephem

# ===== 中国主要城市经纬度数据库（用于真太阳时校正） =====
# 格式: 城市名 → (经度, 纬度)
CITY_COORDS = {
    "北京": (116.4, 39.9),   "上海": (121.5, 31.2),  "广州": (113.3, 23.1),
    "深圳": (114.1, 22.5),   "成都": (104.1, 30.7),  "重庆": (106.6, 29.5),
    "西安": (108.9, 34.3),   "武汉": (114.3, 30.6),  "杭州": (120.2, 30.3),
    "南京": (118.8, 32.1),   "天津": (117.2, 39.1),  "沈阳": (123.4, 41.8),
    "哈尔滨": (126.6, 45.8), "长春": (125.3, 43.9), "大连": (121.6, 38.9),
    "济南": (117.0, 36.7),   "青岛": (120.4, 36.1),  "郑州": (113.7, 34.8),
    "长沙": (113.0, 28.2),   "南昌": (115.9, 28.7),  "福州": (119.3, 26.1),
    "厦门": (118.1, 24.5),   "昆明": (102.7, 25.0),  "贵阳": (106.7, 26.6),
    "南宁": (108.3, 22.8),   "海口": (110.3, 20.0),  "三亚": (109.5, 18.3),
    "兰州": (103.8, 36.1),   "西宁": (101.8, 36.6),  "银川": (106.3, 38.5),
    "乌鲁木齐": (87.6, 43.8), "呼和浩特": (111.7, 40.8), "拉萨": (91.1, 29.7),
    "石家庄": (114.5, 38.0), "太原": (112.5, 37.9),  "合肥": (117.2, 31.8),
    "苏州": (120.6, 31.3),   "无锡": (120.3, 31.6),  "宁波": (121.5, 29.9),
    "温州": (120.7, 28.0),   "东莞": (113.8, 23.0),  "佛山": (113.1, 23.0),
    "珠海": (113.6, 22.3),   "香港": (114.2, 22.3),  "澳门": (113.5, 22.2),
    "台北": (121.5, 25.0),   "高雄": (120.3, 22.6),  "台中": (120.7, 24.1),
    "洛阳": (112.5, 34.6),   "开封": (114.3, 34.8),  "南京": (118.8, 32.1),
    "扬州": (119.4, 32.4),   "绍兴": (120.6, 30.0),  "泉州": (118.6, 24.9),
    "桂林": (110.3, 25.3),   "大理": (100.2, 25.6),  "丽江": (100.2, 26.9),
}

def lookup_coords(birthplace):
    """根据出生地名称查找经纬度，支持模糊匹配"""
    if not birthplace or not birthplace.strip():
        return None, None
    bp = birthplace.strip()
    # 精确匹配
    if bp in CITY_COORDS:
        return CITY_COORDS[bp]
    # 去掉"市" "省" 后缀再匹配
    for suffix in ["市", "省", "县", "区", "镇"]:
        if bp.endswith(suffix) and bp[:-len(suffix)] in CITY_COORDS:
            return CITY_COORDS[bp[:-len(suffix)]]
    # 前缀匹配（如输入"北京朝阳"匹配"北京"）
    for city in CITY_COORDS:
        if bp.startswith(city):
            return CITY_COORDS[city]
    return None, None

def adjust_to_solar_time(beijing_hour, longitude, birth_year, birth_month, birth_day):
    """
    根据出生地经度，将北京时间调整为当地真太阳时
    返回: (调整后的小时数, 是否跨日调整, 跨日偏移天数)
    北京时间的基准经度为东经120°
    每差1度，时间差4分钟
    公式: 真太阳时 ≈ 北京时间 + (经度 - 120) × 4分钟
    """
    if longitude is None:
        return beijing_hour, False, 0  # 无出生地信息，默认北京时间

    # 时间偏移（小时）
    time_offset = (longitude - 120.0) * 4.0 / 60.0
    true_hour = beijing_hour + time_offset

    day_offset = 0
    # 处理跨日
    if true_hour >= 24:
        true_hour -= 24
        day_offset = 1
    elif true_hour < 0:
        true_hour += 24
        day_offset = -1

    return true_hour, (day_offset != 0), day_offset


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


def get_four_pillars(year, month, day, hour, birthplace=""):
    """
    获取四柱，支持出生地真太阳时校正。
    birthplace: 出生城市名称，为空则默认北京时间（东八区标准时）
    """
    # 真太阳时校正
    lon, lat = lookup_coords(birthplace)
    true_hour, crossed_day, day_offset = adjust_to_solar_time(hour, lon, year, month, day)

    # 如果跨日，调整日期
    actual_year, actual_month, actual_day = year, month, day
    if day_offset != 0:
        try:
            orig_date = datetime.date(year, month, day)
            adjusted_date = orig_date + datetime.timedelta(days=day_offset)
            actual_year = adjusted_date.year
            actual_month = adjusted_date.month
            actual_day = adjusted_date.day
        except (ValueError, OverflowError):
            pass

    y = year_pillar(actual_year, actual_month, actual_day)
    m = month_pillar(y[0], actual_month, actual_day, actual_year)
    d = day_pillar(actual_year, actual_month, actual_day)
    h = hour_pillar(d[0], int(round(true_hour)))

    result = {"year": y, "month": m, "day": d, "hour": h}

    # 附上真太阳时校正信息
    if lon is not None:
        result["_solar_info"] = {
            "出生地经度": round(lon, 2),
            "北京时间": f"{hour}:00",
            "真太阳时": f"{int(true_hour):02d}:{int(round((true_hour % 1) * 60)):02d}",
            "时差分钟": round((lon - 120) * 4, 1),
            "是否跨日": crossed_day
        }

    return result


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

    # 喜用神 — 子平命理核心算法
    # 《滴天髓》云：「刚柔之道，可顺不可逆。」身强者宜克泄耗，身弱者宜生扶
    # 五行生克关系
    kem = {"金": "火", "木": "金", "水": "土", "火": "水", "土": "木"}   # 克我者(官杀/约束)
    wok = {"金": "木", "木": "土", "水": "火", "火": "金", "土": "水"}   # 我克者(财星/消耗)
    wos = {"金": "水", "木": "火", "水": "木", "火": "土", "土": "金"}   # 我生者(食伤/泄秀)
    sw2 = {"金": "土", "木": "水", "水": "金", "火": "木", "土": "火"}   # 生我者(印绶/补益)
    tb  = {"金": "木", "木": "土", "水": "火", "火": "金", "土": "水"}   # 同我者(比劫/帮扶)

    # 统计命局中各十神的力量(用于通关判断)
    yin_force = 0  # 印绶力量(天干2分, 地支本气1分)
    bi_force  = 0  # 比劫力量
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
        xy = []
        # 1. 克我(官杀) - 第一用神(需通关检查：印旺则官杀生印，减效)
        w = kem[dwx]
        if w not in xy and yin_force < 4:
            xy.append(w)
        # 2. 我生(食伤) - 第二用神(泄秀，永远有利)
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
        xy = []
        # 1. 生我(印绶) - 第一用神
        w = sw2[dwx]
        if w not in xy:
            xy.append(w)
        # 2. 同我(比劫) - 第二用神
        w = tb[dwx]
        if w not in xy:
            xy.append(w)
    else:
        # 中和: 兼顾生扶和克泄, 以调候为优先
        xy = []
        w = sw2[dwx]
        if w not in xy:
            xy.append(w)
        w = wos[dwx]
        if w not in xy:
            xy.append(w)

    # ---- 调候用神（《穷通宝鉴》体系） ----
    # 根据月支判断寒暖燥湿，补充调候建议
    mz = fp["month"][1]
    tiaohou = []
    # 夏季(巳午未) → 喜水调候
    if mz in ["巳", "午", "未"]:
        if "水" not in xy:
            tiaohou.append("水")
    # 冬季(亥子丑) → 喜火调候
    elif mz in ["亥", "子", "丑"]:
        if "火" not in xy:
            tiaohou.append("火")
    # 春秋看日主五行细分
    # 春木(寅卯) → 木旺，庚金劈木引丁火
    elif mz in ["寅", "卯"] and dwx == "木":
        if "金" not in xy:
            tiaohou.append("金")
    # 秋金(申酉) → 金旺，火炼秋金
    elif mz in ["申", "酉"] and dwx == "金":
        if "火" not in xy:
            tiaohou.append("火")

    # 如果调候用神不在喜用神中，追加说明
    tiaohou_extra = [t for t in tiaohou if t not in xy]

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
        "调候用神": tiaohou_extra,  # 调候建议（五行）
        "神煞": calc_shensha(fp, sex),
        "纳音": {
            "年": nayin(fp["year"][0], fp["year"][1]),
            "月": nayin(fp["month"][0], fp["month"][1]),
            "日": nayin(fp["day"][0], fp["day"][1]),
            "时": nayin(fp["hour"][0], fp["hour"][1]),
        }
    }


# ===== 分析函数 — 结合经典命理书籍与当代中国社会现实 =====

def _cnt(ss, ss2):
    """辅助函数：统计十神在四柱天干+地支本气中出现的次数"""
    n = 0
    for p in POS:
        if ss[p]["干"] in ss2:
            n += 1
        if ss[p]["支"] in ss2:
            n += 1
    return n


def _ss_at(pillar_ss, pos=None):
    """辅助：获取某柱天干与地支本气的十神元组"""
    if pos:
        return pillar_ss[pos]["干"], pillar_ss[pos]["支"]
    return None

def _has_ss(bz, names, check_gan=True, check_zhi=True):
    """检查命局中是否存在指定的十神"""
    ss = bz["十神"]
    for p in POS:
        if check_gan and ss[p]["干"] in names:
            return True, p
        if check_zhi and ss[p]["支"] in names:
            return True, p
    return False, None

def ana_wealth(bz):
    """
    财富分析 — 结合《滴天髓》《穷通宝鉴》财星理论，映射当代中国收入水平
    """
    ss = bz["十神"]
    dg = bz["日主"]
    dwx = bz["日主五行"]
    rst = bz["日主状态"]
    xy = bz.get("喜用神", [])
    gj = bz.get("格局", "")

    # 财星统计（天干1分 => 明财，地支本气1分 => 暗财）
    ming_cai = 0  # 天干透财
    an_cai = 0   # 地支藏财
    cai_positions = []
    for p in POS:
        if ss[p]["干"] in ("正财", "偏财"):
            ming_cai += 1
            cai_positions.append(f"{'年月日时'[POS.index(p)]}柱透{ss[p]['干']}")
        if ss[p]["支"] in ("正财", "偏财"):
            an_cai += 1
    total_cai = ming_cai + an_cai

    # 财星有根（地支藏干中含财星五行）
    cai_wx = {"正财": {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"},
              "偏财": {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}}
    has_root = False

    # 层级判定
    if "正财" in gj or "偏财" in gj:
        # 财格
        if rst == "身强":
            level = "财旺"
            detail_head = f"命局{''.join(cai_positions)}，月令财星当权，日主身强能担大财，格局上乘。"
            income_level = "资产千万级以上，具备企业家格局"
        else:
            level = "财多身弱"
            detail_head = f"命局财星多见（{total_cai}处），但日主身弱，如《滴天髓》所言「财多身弱，富屋贫人」。虽有赚钱机会，却难积累大财。"
            income_level = "宜通过团队合作或借力平台变现，年收入50-200万级别"
    elif ming_cai >= 1:
        level = "财运中上"
        detail_head = f"天干透财（{ming_cai}处），财星明现有根，《穷通宝鉴》言：「财星得地，家业可兴。」"
        income_level = "中产阶级上层，年收入30-100万可期"
    elif an_cai >= 1:
        level = "财运中等"
        detail_head = "财星藏于地支而不露，暗财有根但需要机遇触发。宜以专业技艺为根基，待时而动。"
        income_level = "小康到中产，年收入15-50万，稳定增长型"
    else:
        level = "以技生财"
        detail_head = "命局财星不显，不宜直接经商求财，应以专业技能或才华技艺为立身之本。《千里命稿》云：「财为养命之源，不可无也。无财者，以食伤为财。」"
        income_level = "靠技术吃饭，年收入10-30万稳步上升"

    # 现代解读
    if rst == "身强" and "火" in xy:
        modern_tip = "当前中国互联网/新能源/餐饮行业高速发展，五行属火的领域正是你的财路。把握行业风口，可大幅提升收入层级。"
    elif rst == "身强" and "水" in xy:
        modern_tip = "贸易、物流、跨境电商、文旅等属水行业正迎来红利期。建议关注「一带一路」相关的跨境贸易机会。"
    elif rst == "身弱":
        modern_tip = "身弱不建议单打独斗创业，更适合加入成熟的平台型公司（如大厂、国企），利用平台资源弥补自身不足。理财上以稳健为主，公募基金+银行理财的「固收+」策略最适合你。"
    else:
        modern_tip = "当前中国经济从高速增长转向高质量发展阶段，靠「信息差」赚钱的时代已经过去。建议深耕一个细分领域，打造个人IP或技术壁垒。理财方面，定投沪深300指数基金是不错的选择。"

    # 建议
    if rst == "身强":
        advice = f"① 适合在{'、'.join([x for x in xy if x != dwx][:2])}的行业深耕 ② 可尝试副业或投资 ③ 35岁前后是财富积累黄金期"
    else:
        advice = f"① 优先加入大平台获取稳定收入 ② 利用{'、'.join([x for x in xy][:2])}五行的伙伴或工具补益自身 ③ 理财以稳健为主"

    return {
        "等级": level,
        "详情": detail_head,
        "现代解读": modern_tip,
        "收入层级": income_level,
        "建议": advice
    }


def ana_career(bz):
    """
    事业分析 — 格局定方向，结合当代中国就业市场
    """
    gj = bz["格局"]
    wx = bz["日主五行"]
    dg = bz["日主"]
    rst = bz["日主状态"]
    xy = bz.get("喜用神", [])
    ss = bz["十神"]

    # 行业映射（五行 → 现代行业）
    indu_map = {
        "金": ["金融证券", "法律法务", "机械制造", "精密仪器", "汽车工业", "公务员/体制内"],
        "木": ["教育培训", "文化传媒", "医疗健康", "设计创意", "环保绿化", "出版印刷"],
        "水": ["国际贸易", "物流运输", "旅游酒店", "跨境电商", "水产渔业", "心理咨询"],
        "火": ["互联网/IT", "能源电力", "餐饮食品", "影视娱乐", "市场营销", "电子科技"],
        "土": ["房地产", "建筑工程", "农业矿业", "珠宝古玩", "物业管理", "城市管理"],
    }

    # 格局判断
    if "正官" in gj or "七杀" in gj:
        level = "官贵之命"
        career_type = "管理型"
        detail = f"命带{'正官' if '正官' in gj else '七杀'}格，《子平真诠》云：「正官之格，最为清贵。」天生具备管理才能与责任心，如松柏挺立于风雨而不折。"
        modern = "适合体制内公务员、国企管理岗、大型企业中层以上职位。当前中国强调「高质量发展」和「治理现代化」，管理型人才在政府、央企、互联网大厂都有广阔空间。建议30岁前积累一线经验，35岁后向管理岗转型。"
    elif "食神" in gj or "伤官" in gj:
        level = "才华之命"
        career_type = "技术/创意型"
        detail = f"{'食神' if '食神' in gj else '伤官'}格吐秀，《滴天髓》言：「食神吐秀，才华盖世。」思维活跃，创意无限，如江河奔涌不息。"
        modern = "适合互联网产品经理、软件工程师、设计师、自媒体/内容创作者、科研人员。当前中国数字经济规模超50万亿，技术型人才的薪资天花板远高于传统行业。建议深耕一个垂直领域，打造不可替代的专业壁垒。"
    elif "正财" in gj or "偏财" in gj:
        level = "经商之才"
        career_type = "商业型"
        detail = "月令财星为格，《三命通会》云：「财为养命之源。」天生具备商业嗅觉和资源整合能力，如良贾深藏若虚。"
        modern = "适合自主创业、电商运营、投资管理、销售管理。中国拥有全球最大的消费市场和最完善的供应链体系，消费品、跨境电商、新能源等领域商机无限。建议从细分赛道切入，做精做深后再拓展。"
    elif "正印" in gj or "偏印" in gj:
        level = "学者之风"
        career_type = "研究/教育型"
        detail = "印星为格，《滴天髓》云：「印绶相生，文华盖世。」学识渊博，温润如玉，如大地厚德载物。"
        modern = "适合学术研究、教育行业、出版编辑、政策研究、企业文化。中国正大力推动「科技自立自强」，科研岗位的待遇和社会地位持续提升。高校、研究院所、科技企业的R&D部门都是理想选择。"
    else:
        level = "专业人才"
        career_type = "综合型"
        detail = "格局为杂格或建禄/羊刃，不拘一格，如百炼钢化为绕指柔。"
        modern = "因格局灵活，适合「斜杠青年」模式——主业+副业并行。当前灵活就业人口已超2亿，多重职业身份是未来趋势。建议以一项硬技能为核心，辅以兴趣驱动的副业。"

    # 发展建议
    if rst == "身强":
        advice = f"八字身强，适合在竞争激烈的环境中搏杀。建议选择{'、'.join(indu_map.get(xy[0] if xy else wx, ['专业领域'])[:3])}等领域大展拳脚。"
    else:
        advice = f"八字身弱，宜顺势而为，依托大平台发展。{'、'.join(indu_map.get(xy[0] if xy else wx, ['稳定行业'])[:3])}等行业中寻找有实力的大企业入职。"

    return {
        "等级": level,
        "事业类型": career_type,
        "详情": detail,
        "现代解读": modern,
        "适合行业": indu_map.get(xy[0] if xy else wx, ["综合领域"]),
        "建议": advice
    }


def ana_marriage(bz, sex):
    """
    婚姻分析 — 结合《三命通会》《渊海子平》配偶星理论
    """
    ss = bz["十神"]
    dg = bz["日主"]
    dz = bz["日主五行"]
    rst = bz["日主状态"]
    day_zhi = bz.get("四柱", {}).get("day", [dg, ""])[1] if "四柱" in bz else ""

    star_name = "妻星（财星）" if sex == "男" else "夫星（官星）"
    star_set = {"正财", "偏财"} if sex == "男" else {"正官", "七杀"}

    # 配偶星出现情况
    has_star_gan, star_gan_pos = _has_ss(bz, star_set, check_gan=True, check_zhi=False)
    has_star_zhi, star_zhi_pos = _has_ss(bz, star_set, check_gan=False, check_zhi=True)

    star_gan = bz["十神"][star_gan_pos]["干"] if has_star_gan else None
    star_zhi = bz["十神"][star_zhi_pos]["支"] if has_star_zhi else None

    # 日支（夫妻宫）十神
    rizhi_ss = ss["day"]["支"]

    # 层级判断
    if has_star_gan and rizhi_ss in star_set:
        level = "婚姻美满"
        quality = f"配偶星透于天干且坐夫妻宫，《三命通会》云：「夫星得位，妻星得所。」缘分深厚，婚姻和美。"
        spouse = f"配偶品行端正，{'有管理能力或事业心强' if sex == '女' else '善于理财持家'}"
    elif has_star_gan or has_star_zhi:
        level = "婚姻平顺"
        loc = "天干" if has_star_gan else "地支"
        quality = f"配偶星现于{loc}，《渊海子平》言：「妻星现于旺地，夫星居于生方。」"
        spouse = "配偶性格实在，虽不浪漫但可靠。宜在30岁前后成婚，婚姻稳定性较高。"
    else:
        level = "晚婚为宜"
        quality = "配偶星不显于命局，《千里命稿》云：「夫星不显，妻星不露，婚姻宜晚。」不必焦虑，大运流年引发配偶星之时，正缘自会出现。"
        spouse = "晚婚者的婚姻质量往往更高——经过充分的自我成长和社会历练后，更懂得选择与经营。"

    # 夫妻宫十神分析
    rizhi_desc = {
        "正官": "配偶正直有责任心，如白杨挺拔。",
        "七杀": "配偶性格刚烈有魄力，婚姻中需要互相尊重、给对方空间。",
        "正财": "配偶务实顾家，经济观念强，是过日子的好伴侣。",
        "偏财": "配偶慷慨大方、人缘好，但消费观念可能偏随意，需要沟通理财方式。",
        "正印": "配偶温柔体贴，有包容心，婚姻氛围温暖。",
        "偏印": "配偶思维独特，可能有小众爱好，婚姻中需要精神共鸣。",
        "食神": "配偶温和善良，家庭氛围轻松。",
        "伤官": "配偶聪明有才华但性格独立，婚姻中需要保持各自的独立空间。",
        "比肩": "配偶如最好的朋友，精神共鸣强。",
        "劫财": "配偶个性突出，婚姻中可能因小事争执，但感情深厚。",
    }

    # 现代解读
    if sex == "男":
        modern = "当前中国男性面临较大的婚恋压力（性别比失衡），但命理显示你的正缘在适当的大运中会出现。建议：① 提升自身综合素质（经济基础+情商）② 拓展社交圈 ③ 30-35岁是理想的成婚窗口期。"
    else:
        modern = "当代女性经济独立是大势所趋，命理中的「官星」已不限于传统意义上的「丈夫」，更代表事业上的贵人和合作伙伴。建议同时关注事业发展和婚姻经营，两者并非对立。"

    return {
        "等级": level,
        "婚姻质量": quality,
        "配偶特征": spouse + rizhi_desc.get(rizhi_ss, "夫妻宫需用心经营，可借流年良机增进感情。"),
        "配偶星": star_name,
        "现代解读": modern
    }


def ana_children(bz, sex):
    """子女分析 — 时柱子女宫为主，结合《三命通会》"""
    ss = bz["十神"]
    star_name = "子女星（官杀）" if sex == "男" else "子女星（食伤）"
    star_set = {"正官", "七杀"} if sex == "男" else {"食神", "伤官"}
    n = _cnt(ss, star_set)
    hour_ss = ss["hour"]["干"]

    if n >= 2:
        level = "子女缘厚"
        detail = f"子女星在命局中出现{n}次，《三命通会》言：「官杀为子，食伤为女。」时柱为子女宫，{star_name}有力，预示着子女数量不少于两个，且子女聪明伶俐。"
    elif n == 1:
        level = "子女缘中等"
        detail = "命中有一位明显的子女星，子女与你的缘分适中。现代家庭普遍生育1-2个孩子，命理显示你至少有一个子女能成才。时柱子女宫的状态是决定子女成就的关键。"
    else:
        level = "子女缘薄"
        detail = "命局中子女星不显，可能意味着生育年龄偏晚或子女来得不易。《渊海子平》云：「时上一位贵」，时柱若有贵人星，子女仍有出息。建议30岁后计划生育，借助现代医学手段辅助。"
    modern = "当前中国生育率走低，养育成本高企，很多家庭选择只生一个或晚育。命理显示的「子女缘」更应理解为：你是否准备好为人父母、能否给予子女高质量的陪伴和教育，而非简单的数量。"
    return {"等级": level, "详情": detail, "现代解读": modern}


def ana_siblings(bz):
    """兄弟/手足分析 — 比劫为兄弟姐妹"""
    ss = bz["十神"]
    n = _cnt(ss, {"比肩", "劫财"})
    rst = bz["日主状态"]

    if n >= 2:
        level = "兄弟有助"
        if rst == "身弱":
            detail = "命局比劫多见且日主身弱，手足情深，如《滴天髓》所言「比肩帮身」。兄弟姐妹是你人生中重要的支持力量，在你困难时他们会伸出援手。"
        else:
            detail = "命局比劫多见但日主身强，手足之间有暗中较劲的意味。建议在合作中保持一定边界，亲兄弟明算账，反能长久和睦。"
        modern = "当代独生子女比例高，「比劫」对应的已不限于血缘兄弟姐妹，更包括关系紧密的同事、同学、创业伙伴。你的「手足缘」意味着你在团队合作中容易找到志同道合的伙伴。"
    elif n == 1:
        level = "兄弟缘中等"
        detail = "命中有比劫一位，有一位能交心的兄弟或挚友。"
        modern = "现代社会人际关系网络化，朋友圈子就是你的「兄弟姐妹」。建议维护好3-5个核心人脉，他们是你事业的助力。"
    else:
        level = "独立发展"
        detail = "命局比劫不显，更倾向独立发展。《三命通会》云：「孤则不群。」但独立并非坏事——独生子女时代，很多人都是靠自己在社会上打拼。"
        modern = "独立发展意味着你的成就不依赖他人，完全靠自己打拼。这在当代反而是难得的品质。建议在关键节点（如创业、换工作）寻找专业顾问而非依赖熟人。"
    return {"等级": level, "详情": detail, "现代解读": modern}


def ana_parents(bz):
    """父母分析 — 年月为父母宫，印星为母，财星为父"""
    ss = bz["十神"]
    year_ss = ss.get("year", {})
    month_ss = ss.get("month", {})

    # 母亲（印星）
    yin_in_year = year_ss.get("干") in ("正印", "偏印") or year_ss.get("支") in ("正印", "偏印")
    yin_in_month = month_ss.get("干") in ("正印", "偏印") or month_ss.get("支") in ("正印", "偏印")
    # 父亲（财星）
    cai_in_year = year_ss.get("干") in ("正财", "偏财") or year_ss.get("支") in ("正财", "偏财")
    cai_in_month = month_ss.get("干") in ("正财", "偏财") or month_ss.get("支") in ("正财", "偏财")

    # 母亲
    if yin_in_year:
        mom = "印星现于年柱（父母宫），母亲对你的成长影响深远——她可能是你价值观的奠基人，从小言传身教塑造了你的品格。母亲持家有道，身体健康状况总体良好。"
    elif yin_in_month:
        mom = "印星现于月柱，母亲性格坚韧，是你事业上的暗中助力。《渊海子平》云：「印绶在月，父母双全。」"
    else:
        mom = "印星不显于年月柱，母亲在命局中的信息较为隐性。可能母亲忙于工作或由其他长辈抚养长大，但这不影响母子/母女之间的感情。"

    # 父亲
    if cai_in_year:
        dad = "财星坐年柱父母宫，父亲有经济头脑，事业能力较强。《三命通会》云：「年上财官，祖上兴隆。」父亲对家庭物质基础贡献大。"
    elif cai_in_month:
        dad = "财星现于月柱，父亲务实肯干，是典型的中国传统父亲形象——话不多但责任扛在肩上。"
    else:
        dad = "财星不显，父亲信息较为隐性。可能父亲性格温和低调，或是与你的相处时间因工作等原因相对较少。这不代表父亲不关心你。"

    modern = "当代中国正在经历人口老龄化加速阶段。无论命理如何显示，作为子女，关心父母的身体健康、定期安排体检、帮助他们建立科学养生观念，是最实在的「孝道」。建议为父母购买一份商业医疗保险作为补充。"

    return {
        "母亲": mom,
        "父亲": dad,
        "现代解读": modern
    }


def ana_health(wx_stat):
    """健康分析 — 五行配五脏，结合现代医学常识"""
    organ_map = {
        "金": ("呼吸系统", "肺、气管、皮肤、大肠"),
        "木": ("肝胆系统", "肝、胆、四肢、筋骨、甲状腺"),
        "水": ("泌尿生殖系统", "肾、膀胱、生殖系统、内分泌"),
        "火": ("心血管系统", "心脏、小肠、血液循环、神经系统"),
        "土": ("消化系统", "脾胃、胰腺、肌肉、免疫系统"),
    }

    issues = []
    for w, c in wx_stat.items():
        if c == 0:
            issues.append((w, "缺", f"五行缺{w}，{organ_map[w][0]}（{organ_map[w][1]}）先天偏弱，需特别注意保养。"))
        elif c >= 4:
            issues.append((w, "旺", f"五行{w}过旺，{organ_map[w][0]}（{organ_map[w][1]}）容易因「过用」而产生问题，如炎症、功能亢进等。"))

    if not issues:
        return {
            "等级": "身体健康",
            "详情": "命局五行相对平衡，《滴天髓》云：「五行和，则百病不生。」先天体质较好，只需保持良好的生活习惯即可。",
            "现代解读": "当代社会最大的健康杀手是久坐、熬夜和精神压力。即使八字五行平衡，也需要每年做一次全面体检，重点监控血压、血糖、血脂「三高」指标。",
            "注意事项": []
        }

    detail_parts = []
    notes = []
    for w, typ, desc in issues:
        detail_parts.append(desc)
        if w == "金": notes.append("秋冬季节注意保暖防感冒，雾霾天佩戴口罩")
        if w == "木": notes.append("少饮酒，定期检查肝功能；保持情绪舒畅，避免生闷气")
        if w == "水": notes.append("不憋尿、多喝水，控制盐分摄入；秋冬注意腰部保暖")
        if w == "火": notes.append("控制血压血脂，避免过度劳累和情绪激动")
        if w == "土": notes.append("饮食规律、少食多餐，避免生冷刺激食物")

    return {
        "等级": "注意保养",
        "详情": "；".join(detail_parts) + "。建议定期体检，早发现早干预。",
        "现代解读": "中医五行对应五脏的理论已被现代心身医学部分验证——情绪确实会影响对应的脏器功能。建议：① 每年一次全面体检 ② 结合自己的五行短板选择适合的运动方式 ③ 不要等到有症状才就医。",
        "注意事项": notes
    }


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

    # 各维度分析模板 - 结合经典命理与现代社会
    wealth_desc = {
        "正财": f"正财运主稳定工薪收入，适合在公司或体制内稳步升职加薪。《穷通宝鉴》言：「财星得地，家业可兴。」此运中工资性收入增长可期，建议：① 积极争取升职或跳槽到更高薪岗位 ② 考虑考证/进修提升含金量 ③ 避免高风险投资，以银行理财和指数基金为主。当前中国一线城市白领年薪中位数约15-25万，此运有望突破30-50万级别。",
        "偏财": f"偏财运主意外之财和投资收益，人脉变现在此运会显著提升。《穷通宝鉴》言：「偏财旺相，横财可期。」此运适合：① 开拓副业或兼职收入 ② 关注股票/基金等资本市场机会 ③ 利用信息差和人脉资源对接商机。注意《滴天髓》的忠告：贪多必失——偏财运来得快去得也快，赚钱后要及时落袋为安，配置稳健资产。",
        "正官": "官星护财，有贵人助理财。在当前社会环境中，这意味着你的上级或行业前辈会给予实质性支持——可能是推荐升职、介绍资源或提供投资建议。此运适合在现有组织中向上发展，不宜轻易跳槽。收入以「工资+绩效奖金」为主，稳中有升。",
        "七杀": "杀星克身，财运压力与机遇并存。《滴天髓》言：「杀有制则为君子。」此运中可能面临：① 业绩压力增大但奖金也更高 ② 被迫创业或转型但成功后收益可观 ③ 需要比别人付出更多才能获得同等回报。建议做好至少6个月的应急储蓄，不宜加杠杆投资。",
        "食神": "食神生财，以才华技艺变现。《滴天髓》言：「食神吐秀，财运亨通。」此运非常适合：① 内容创作者、设计师、程序员等技术型人才变现 ② 通过知识付费、在线课程等方式建立被动收入 ③ 餐饮/文化/艺术相关领域的创业者。在「个人IP」时代，食神运是打造影响力的黄金期。",
        "伤官": "伤官生财但伴有波动，《滴天髓》提醒「伤官见官，其祸百端」。此运中赚钱机会多但风险也大，适合：① 自由职业者/独立顾问模式 ② 科技创新类创业 ③ 短线交易（但务必设止损）。建议将收入的30%强制储蓄，余下再投资——伤官运最忌ALL IN。",
        "正印": "印绶护身，财运稳健增长。此运适合深耕专业领域，以知识和技术提升收入天花板。《滴天髓》云：「印绶相生，文华盖世。」建议通过学历提升、职业资格认证等方式，从「执行层」向「专家层」跃迁。在当前知识经济时代，一个高级工程师/医生/律师的年收入可达50-100万。",
        "偏印": "偏印运中思维活跃，财路独特但需要耐心。适合：① 科研、学术等长线回报领域 ② 小众赛道创业（如古玩鉴定、玄学咨询） ③ 专利/版权等知识产权变现。《子平真诠》提醒偏印需防「夺食」——不要因为追逐短期利益而放弃主业根基。",
        "比肩": "比肩运中同辈竞争激烈，财运需靠自己打拼。《滴天髓》言：「比肩争财，竞争多端。」此运：① 不宜与人合伙投资 ② 适合靠体力和执行力赚钱（销售、工程等） ③ 要提防同事或朋友以「合作」之名借机分利。建议保持独立财务，亲兄弟明算账。",
        "劫财": "劫财运中需严防破财，《子平真诠》直言：「劫财阳刃，切忌财旺。」此运中：① 不宜借贷或做担保人 ② 需防投资理财骗局 ③ 消费欲望增强但收入未必同步增长——务必记账控支出。建议此运期间以守财为主，将钱放在流动性好、风险低的渠道。",
    }
    career_desc = {
        "正官": "正官运主职场晋升，适合在体制内或大企业中向上发展。《子平真诠》言：「正官之格，最为清贵。」当前中国正推动干部年轻化和管理升级，此运中你的管理才能会被上级注意到。建议：① 主动承担跨部门项目增加曝光 ② 考取PMP/CPA等行业资质 ③ 35岁前是关键晋升窗口。",
        "七杀": "七杀运压力大但成长也快，《滴天髓》言：「杀有制则为君子。」此运如同互联网大厂的「高压锅」环境——扛住了就是蜕变。适合：① 挑战高难度岗位（销售管理、项目负责人） ② 创业（杀运最有创业者精神） ③ 从技术岗转向管理岗。提醒：压力管理很重要，定期运动释放。",
        "正财": "正财星运中事业稳定务实，适合深耕一个行业做精做透。《穷通宝鉴》云：「财旺生官，事业有成。」在当前社会，这意味着在某领域积累5-10年经验后，成为行业中坚力量。建议在制造业、金融业、教育等稳定性强的行业中建立长期职业规划。",
        "偏财": "偏财运中人缘助力大，适合商务拓展和市场类岗位。《穷通宝鉴》云：「偏财慷慨，交际通达。」此运适合：① 销售/BD/客户经理等与人打交道的工作 ② 利用社交网络拓展商业机会 ③ 在「平台经济」中寻找价值——如成为行业KOL。",
        "食神": "食神运中才华展露，适合文化创意、设计、教育领域。《滴天髓》言：「食神吐秀，才华盖世。」此运非常适合成为细分领域的专家型人才。在知识付费时代，一个优秀的课程创作者年收入可达七位数。",
        "伤官": "伤官运思想前卫但容易得罪人，《子平真诠》言：「伤官用印，贵在印星。」适合：① 科技创新（程序员、AI工程师） ② 自由创作（作家、导演） ③ 不走寻常路的创业。提醒：才华要用在正道上，避免与上级正面冲突——伤官最大的敌人是自己的傲气。",
        "正印": "印运大利学业和考证，《滴天髓》言：「印绶相生，文华盖世。」此运适合：① 读研/读博深造 ② 考公务员或事业编 ③ 在教育/研究/咨询行业中扎根。学历红利虽然不如20年前，但硕士以上学历在一线城市仍能溢价30%以上。",
        "偏印": "偏印运思维独特，适合研究型、技术型岗位。《三命通会》云：「偏印见食神，须防灾祸。」适合：① 科研/学术/专利开发 ② AI/大数据等前沿技术 ③ 小众领域的独立工作室。提醒偏印运容易「想得多做得少」——必须制定具体执行计划并按周复盘。",
        "比肩": "比肩运中同行竞争激烈，《滴天髓》言：「比肩帮身，身旺则忌。」此运：① 适合独立负责项目而非团队合作 ② 可以在竞争中打磨自己的核心竞争力 ③ 不适合与朋友合伙创业。建议：把同行的成功视为对标和激励，而非嫉妒对象。",
        "劫财": "劫财运中事业波折较多，《子平真诠》言：「劫财争财，破耗不宁。」此运：① 宜守不宜攻，不建议跳槽或创业 ② 警惕职场小人 ③ 在现有岗位上深耕，等待下一个好运。中国职场35岁危机在此运中可能被放大——建议提前储备「第二技能」。",
    }
    marriage_desc = {
        "正官": "正官运中正缘显现，感情关系正式化。《三命通会》言：「官星得力，夫荣妻贵。」此运非常适合：① 确定恋爱关系或步入婚姻 ② 已婚者家庭地位提升 ③ 通过配偶获得社会资源。在当前晚婚趋势下，28-35岁遇正官运是理想的婚嫁窗口。",
        "七杀": "七杀运中感情激烈但易有波折。未婚者可能邂逅「虐恋」型对象——爱得深但也吵得凶；已婚者需多沟通、少猜疑。《滴天髓》言：「杀重身轻，灾祸难免。」提醒：① 不要闪婚 ② 已婚者避免与异性保持暧昧 ③ 感情问题是此运的主要压力源之一。",
        "正财": "正财运中（男命）妻缘佳，适合成家。《穷通宝鉴》云：「财星为妻，得地则妻贤。」此运家庭经济状况改善，有利于：① 购房置业 ② 生育计划 ③ 配偶事业发展。对于女命而言，此运意味着自身经济独立，在婚姻中更有底气。",
        "偏财": "偏财运中异性缘旺，男命需防桃花劫。《渊海子平》云：「偏财为妾，正财为妻。」已婚者需洁身自好，未婚者享受恋爱但不要同时多处暧昧。在这个社交软件泛滥的时代，偏财运更容易导致「情感消费主义」——追求新鲜感而非深度关系。",
        "食神": "食神运中感情温和舒适，家庭氛围融洽。《滴天髓》言：「食神吐秀，福禄双全。」此运适合：① 备孕生育 ② 改善夫妻关系 ③ 家庭聚会增多。食神运的人更容易在家庭生活中找到幸福感，「老婆孩子热炕头」是此运的真实写照。",
        "伤官": "伤官运中感情容易起波澜。《滴天髓》直指：「伤官见官，其祸百端。」此运：① 已婚者容易因小事争执 ② 未婚者对伴侣要求变高 ③ 女性需要平衡事业和家庭。建议：不要把工作情绪带回家，学会「对事不对人」的沟通方式。",
        "正印": "印运中家庭温馨，长辈助力大。《滴天髓》云：「印绶相生，家和万事兴。」此运适合：① 与父母同住或增加互动 ② 添丁进口 ③ 置业安家。印运中的感情像冬日里的一杯热茶——不轰轰烈烈但温暖踏实。",
        "偏印": "偏印运中感情偏冷，《三命通会》云：「枭神夺食，贫寒孤苦。」需要特别注意：① 不要因为工作忽略了伴侣 ② 避免冷战——偏印运的人习惯把事情放在心里 ③ 主动表达爱意。既然不善言辞，就用行动证明。",
        "比肩": "比肩运中感情有竞争压力。《滴天髓》言：「比肩争财，竞争多端。」此运可能出现：① 第三者介入风险 ② 在感情中感到「被比较」 ③ 单身者在多角关系中徘徊。建议：加强自身魅力建设，比盯住竞争对手更有意义。",
        "劫财": "劫财运中感情不稳，男命注意「夺妻」之象。《子平真诠》云：「劫财争财，破耗不宁。」此运：① 避免因金钱问题引发争吵 ② 已婚者防范感情危机 ③ 单身者需擦亮眼睛，谨防遇到别有用心的追求者。",
    }
    health_desc = {
        "正官": f"官运中身体状态尚可，但工作压力可能导致亚健康。《三命通会》云：「官星得地，身心康泰。」建议：① 定期体检，关注血压/血脂 ② 避免长期加班导致的慢性疲劳 ③ 每周至少3次有氧运动。",
        "七杀": f"杀运中需特别注意意外伤害和安全事故。《滴天髓》直言：「杀重身轻，灾祸难免。」此运：① 避免高风险运动 ② 驾车需格外小心 ③ 从事体力劳动/工地/化工等行业者需严守安全规程。同时关注心理健康——杀运压力大，焦虑和失眠是高发问题。",
        "正财": f"财运中身体状况平稳，但久坐办公可能导致颈椎/腰椎问题。建议：① 每天坚持30分钟中低强度运动 ② 控制饮食防止「过劳肥」 ③ 每年做一次全面体检。",
        "偏财": f"偏财运中生活节奏快、应酬多，需防「富贵病」——高血脂、脂肪肝。《上医治未病》，此运：① 应酬时少喝酒多吃菜 ② 周末补充睡眠 ③ 不要因为忙碌忽视身体信号。",
        "食神": f"食神运中口福好但需节制饮食。《滴天髓》言：「食神吐秀，福禄双全。」提醒：① 美食虽好但八分饱为宜 ② 重点监控血糖和体重 ③ 食神运的快乐源于吃，但健康源于克制——两者需要平衡。",
        "伤官": f"伤官运中注意呼吸系统和口腔健康。《滴天髓》云：「伤官见官，其祸百端。」此运：① 戒烟限酒 ② 注意牙齿保健 ③ 哮喘/慢性咽炎患者需加强防护。另外，伤官运容易「思虑过度」导致失眠——睡前冥想是有效方法。",
        "正印": f"印运中身体恢复能力增强，是调养的好时机。《滴天髓》言：「印绶相生，文华盖世。」此运：① 适合中医调理 ② 身体小毛病会自然好转 ③ 可以尝试养生功法如太极、八段锦。",
        "偏印": f"偏印运中精神压力较大，容易失眠焦虑。《三命通会》云：「枭神夺食。」此运：① 关注心理健康 ② 不要把事情想得太复杂 ③ 必要时寻求心理咨询。中国职场人心理健康问题日益严重，偏印运的人尤其需要学会「放下」。",
        "比肩": f"比肩运中体质不错，但竞争压力需调节。《滴天髓》言：「比肩帮身，身旺则忌。」建议：① 通过运动释放竞争焦虑 ② 团队运动（篮球、足球）有助于舒缓压力 ③ 避免因为攀比而过度训练导致运动损伤。",
        "劫财": f"劫财运中需防血光之灾和手术风险。《子平真诠》云：「劫财阳刃。」此运：① 远离危险场所 ② 如果不幸需要手术，选择口碑好的医院 ③ 购买意外险和医疗险作为保障。",
    }
    study_desc = {
        "正官": "官运中利考试、考编、公考。《滴天髓》云：「正官配印，名利双收。」适合：① 公务员/事业编考试 ② 行业资格认证 ③ 进修管理类课程。重点：守正笃学，不走捷径。",
        "七杀": "杀运中学习压力大但效率高，适合「高压集训」式学习。化压力为动力，可在短时间内突破瓶颈。适合：① 突击考证 ② 考研/考博 ③ 攻克技术难题。",
        "正财": "财星运中学习偏实用导向，适合财务、金融、商业类进修。学以致用是此运的关键——学什么就要立刻在实践中检验。",
        "偏财": "偏财运中学习面广但深度可能不足。建议集中精力在1-2个核心技能上，辅以广泛的兴趣阅读。",
        "食神": "食神运中才思泉涌，是学习艺术、文学等创意类学科的最佳时机。《滴天髓》言：「食神吐秀，文华盖世。」适合：① 写作/设计/音乐 ② 语言学习 ③ 任何需要创造力的领域。",
        "伤官": "伤官运中思维活跃，适合创新性强的研究领域。但需注意：① 避免偏执——多听不同意见 ② 从「独行侠」模式切换到「团队协作」 ③ 伤官的才华需要印星的指引才能产生真正有价值的研究。",
        "正印": "印运大利学业！《滴天髓》云：「印绶相生，文华盖世。」此运是考学的黄金期——无论是高考、考研还是留学，印运加持下事半功倍。即便已经工作，此运也非常适合读MBA、EMBA等在职学位。",
        "偏印": "偏印运中适合非主流学科和跨领域研究。适合：① AI/大数据等前沿技术 ② 哲学/心理学 ③ 任一需要深度思考的领域。提醒偏印运容易「三分钟热度」——选定方向后至少坚持6个月再评价。",
        "比肩": "比肩运中适合与同学组队学习、参加竞赛。《学记》云：「独学而无友，则孤陋而寡闻。」此运中学习小组或读书会是最高效的方式。",
        "劫财": "劫财运中学习容易分心，需强制专注。《劝学》云：「锲而不舍，金石可镂。」此运：① 关闭手机通知 ② 使用番茄钟工作法 ③ 每天固定时段学习。戒骄戒躁，稳扎稳打。",
    }
    social_desc = {
        "正官": "官运中人缘正直，易得上级/领导的赏识。《论语》云：「君子周而不比。」此运：① 不要刻意讨好上级，用业绩说话 ② 在正式场合（会议、报告）展现能力 ③ 官运中的贵人往往是比你年长或有职级的前辈。",
        "七杀": "杀运中人际关系有张力。《道德经》云：「刚强者死之徒。」建议：① 原则要硬但态度要软 ② 不要处处树敌——杀运中得罪的人日后可能成为阻碍 ③ 学会委婉表达不同意见。",
        "正财": "财运中人际随和、和气生财。《史记》云：「天下熙熙，皆为利来。」此运：① 商业社交是主线 ② 把80%的精力放在维护20%的高价值人脉上 ③ 合作时先小人后君子，合同要合法合规。",
        "偏财": "偏财运中人缘极佳，社交圈快速扩大。《增广贤文》云：「在家靠父母，出门靠朋友。」此运：① 非常适合做市场/公关/销售类工作 ② 积极参加行业会议和社交活动 ③ 但需分辨「朋友」和「利益伙伴」——偏财运中的酒肉朋友不在少数。",
        "食神": "食神运中人人亲近，口碑好。《孟子》云：「爱人者人恒爱之。」此运：① 天生的「好人缘」让你在职场中一路绿灯 ② 适合做客户服务/HR/教育等需要高情商的工作 ③ 朋友聚会往往由你张罗。",
        "伤官": "伤官运中口才出众但容易得罪人。《礼记》云：「傲不可长。」建议：① 「三思而后言」——说之前想一下对方感受 ② 批评时对事不对人 ③ 社交平台发言务必谨慎，伤官运最容易被「社死」。",
        "正印": "印运中有长辈缘和师长缘。《师说》云：「师者，所以传道受业解惑也。」此运：① 多拜访行业前辈 ② 参加行业协会或学术组织 ③ 印运中的贵人往往能给你最有价值的建议。",
        "偏印": "偏印运中内向、喜独处。《庄子》云：「独与天地精神往来。」此运：① 不必强求社交，高质量的独处比低质量的社交更有价值 ② 线上交流和邮件沟通是你的舒适区 ③ 但要避免完全封闭——定期与2-3个知心朋友保持联系。",
        "比肩": "比肩运中同辈缘分佳但也有竞争。《孙子兵法》云：「知己知彼，百战不殆。」此运：① 与同事既是战友也是竞争对手——保持良性竞争 ② 适度参加团建和同事聚会 ③ 合作时明确权责。",
        "劫财": "劫财运中需防被骗被坑。《增广贤文》云：「画龙画虎难画骨，知人知面不知心。」此运：① 不轻易为人担保 ② 借款需有借条 ③ 社交中保持警觉，天上不会掉馅饼。",
    }

    def _pick(d, k1):
        return d.get(k1, "此运平稳，宜安分守己。")

    # 根据天干十神为主、地支十神为辅生成分析
    detail = {
        "财富": _pick(wealth_desc, ssg),
        "事业": _pick(career_desc, ssg),
        "婚姻": _pick(marriage_desc, ssg),
        "健康": _pick(health_desc, ssg),
        "学业": _pick(study_desc, ssg),
        "人际": _pick(social_desc, ssg),
    }

    # 如果地支十神与天干不同，补充地支影响
    if ssz != ssg:
        if ssz in ("偏财", "正财"):
            detail["财富"] += f" 地支{ssz}暗藏，有隐性财务机会或隐性支出，需仔细记账。"
        elif ssz in ("正印", "偏印"):
            detail["学业"] += f" 地支{ssz}暗助，学习有暗中贵人或悟性超常。"
        elif ssz == "七杀":
            detail["健康"] += " 地支暗藏七杀，需提防潜伏的健康风险和意外。"
        elif ssz in ("正官",):
            detail["事业"] += " 地支正官暗助，暗中有人提拔。"
        elif ssz == "伤官":
            detail["人际"] += " 地支伤官暗动，注意幕后的小人口舌。"
        elif ssz == "劫财":
            detail["财富"] += " 地支劫财暗藏，防不知不觉的金钱流失。"

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
    th = bz.get("调候用神", [])
    if th:
        parts.append(f"【调候建议】生于特定时节，除喜用神外，五行「{'、'.join(th)}」亦为调候所需。《穷通宝鉴》云：「格中调候为急。」")
    return "\n\n".join(parts)


# ===== 主入口 =====
def full_analysis(year, month, day, hour, sex, birthplace=""):
    fp = get_four_pillars(year, month, day, hour, birthplace)
    # 提取真太阳时校正后的实际日期（可能因跨日而不同）
    solar_info = fp.pop("_solar_info", None)
    actual_year = year
    actual_month = month
    actual_day = day
    # 若有跨日调整，从四柱中日柱的排定逆推实际日期
    # 简化处理：直接使用原始日期即可（大运起运以节气距出生日计算，误差极小可忽略）
    fp2 = {k: list(v) for k, v in fp.items()}
    bz = analyze_bazi(fp, sex)
    qi, dl = calc_dayun(sex, fp["year"][0], tuple(fp["month"]), actual_year, actual_month, actual_day)
    bz["起运年龄"] = qi
    bz["大运"] = dl
    bz["四柱"] = fp2
    if solar_info:
        bz["真太阳时"] = solar_info
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
        bz["流年"][str(step)] = calc_liunian_list(actual_year, fp, bz, dy)
    bz["命理总论"] = gen_overview(bz, sex)
    bz["基本信息"] = {"性别": sex, "出生地": birthplace,
                         "公历": f"{year}年{month}月{day}日{hour}时"}
    return bz


if __name__ == "__main__":
    r = full_analysis(1990, 6, 15, 12, "男", "北京")
    import json
    print(json.dumps(r, ensure_ascii=False, indent=2))
