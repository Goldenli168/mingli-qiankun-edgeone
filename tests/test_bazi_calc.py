"""
测试：八字四柱计算 + 大运排盘
"""
from utils.bazi_core import get_four_pillars, calc_dayun, full_analysis
from utils.bazi_data import GAN, ZHI, SHISHEN


class TestFourPillars:
    """四柱排盘"""

    def test_known_birthday(self):
        """
        已知生日: 1987-07-08 戌时 (亥时? 按默认12点)
        验证返回四柱基本结构
        """
        result = get_four_pillars(1987, 7, 8, 12)
        assert "year" in result
        assert "month" in result
        assert "day" in result
        assert "hour" in result
        # 每柱是 (天干, 地支) 元组
        for p in ["year", "month", "day", "hour"]:
            assert len(result[p]) == 2
            assert result[p][0] in GAN
            assert result[p][1] in ZHI

    def test_year_range(self):
        """年份范围测试"""
        # 1924
        r1 = get_four_pillars(1924, 1, 1, 0)
        assert "year" in r1
        # 2100
        r2 = get_four_pillars(2100, 12, 31, 23)
        assert "year" in r2

    def test_all_months(self):
        """所有月份都能正常排盘"""
        for m in range(1, 13):
            result = get_four_pillars(2000, m, 15, 12)
            assert result["month"][0] in GAN


class TestDayun:
    """大运排盘"""

    def test_dayun_male(self):
        """男命大运 (1987 年)"""
        fp = get_four_pillars(1987, 7, 8, 20)
        qi_yun, dayun_list = calc_dayun(
            "男", fp["year"][0], tuple(fp["month"]),
            1987, 7, 8
        )
        assert qi_yun >= 0
        assert len(dayun_list) >= 6

    def test_dayun_female(self):
        """女命大运 (1987 年)"""
        fp = get_four_pillars(1987, 7, 8, 20)
        qi_yun, dayun_list = calc_dayun(
            "女", fp["year"][0], tuple(fp["month"]),
            1987, 7, 8
        )
        assert qi_yun >= 0
        assert len(dayun_list) >= 6

    def test_dayun_structure(self):
        """大运列表结构验证"""
        fp = get_four_pillars(1987, 7, 8, 20)
        _, dayun_list = calc_dayun("男", fp["year"][0], tuple(fp["month"]), 1987, 7, 8)
        for dy in dayun_list:
            assert "gan" in dy
            assert "zhi" in dy
            assert "age_start" in dy
            assert "age_end" in dy
            assert dy["gan"] in GAN


class TestFullAnalysis:
    """完整分析入口"""

    def test_full_analysis_returns_all_keys(self):
        """full_analysis 返回可用结构（无错误）"""
        result = full_analysis(1987, 7, 8, 20, "男", "北京", 0)
        assert isinstance(result, dict)
        assert "error" not in result
        assert "四柱" in result

    def test_full_analysis_sex_variant(self):
        """不同性别不报错"""
        r1 = full_analysis(2000, 1, 1, 12, "男")
        r2 = full_analysis(2000, 1, 1, 12, "女")
        assert "四柱" in r1
        assert "四柱" in r2
