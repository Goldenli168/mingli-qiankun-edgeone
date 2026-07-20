"""
测试：八字数据常量表（天干地支、五行、纳音、藏干）
"""
from utils.bazi_data import (
    GAN, ZHI, GAN_I, ZHI_I,
    WXG, WXZ, ZHICANG,
    SHISHEN, NAYIN, NY,
    CITY_COORDS,
)


class TestGanZhi:
    """天干地支基础"""

    def test_gan_count(self):
        """天干应有 10 个"""
        assert len(GAN) == 10

    def test_zhi_count(self):
        """地支应有 12 个"""
        assert len(ZHI) == 12

    def test_gan_first(self):
        """第一天干是甲"""
        assert GAN[0] == "甲"

    def test_gan_last(self):
        """最后天干是癸"""
        assert GAN[9] == "癸"

    def test_zhi_first(self):
        """第一地支是子"""
        assert ZHI[0] == "子"

    def test_gan_index(self):
        """天干索引映射"""
        assert GAN_I["甲"] == 0
        assert GAN_I["癸"] == 9

    def test_zhi_index(self):
        """地支索引映射"""
        assert ZHI_I["子"] == 0
        assert ZHI_I["亥"] == 11


class TestWuXing:
    """五行体系"""

    def test_gan_wuxing(self):
        """天干五行对应"""
        assert WXG["甲"] == "木"
        assert WXG["丙"] == "火"
        assert WXG["戊"] == "土"
        assert WXG["庚"] == "金"
        assert WXG["壬"] == "水"

    def test_zhi_wuxing(self):
        """地支五行对应"""
        assert WXZ["子"] == "水"
        assert WXZ["寅"] == "木"
        assert WXZ["午"] == "火"
        assert WXZ["申"] == "金"
        assert WXZ["辰"] == "土"


class TestShiShen:
    """十神体系"""

    def test_jiashu_geng(self):
        """甲日主见庚金 → 七杀"""
        assert SHISHEN["甲"]["庚"] == "七杀"

    def test_jiashu_gui(self):
        """甲日主见癸水 → 正印"""
        assert SHISHEN["甲"]["癸"] == "正印"

    def test_yishu_xin(self):
        """乙日主见辛金 → 七杀"""
        assert SHISHEN["乙"]["辛"] == "七杀"

    def test_dingshu_jia(self):
        """丁日主见甲木 → 正印"""
        assert SHISHEN["丁"]["甲"] == "正印"

    def test_jishu_jia(self):
        """己日主见甲木 → 正官"""
        assert SHISHEN["己"]["甲"] == "正官"

    def test_self_bijian(self):
        """同五行阳见阳 → 比肩"""
        for g in GAN:
            assert SHISHEN[g][g] == "比肩"


class TestNayin:
    """纳音六十甲子"""

    def test_nayin_count(self):
        """纳音应有 60 个条目"""
        assert len(NAYIN) == 60

    def test_nayin_jiazi(self):
        """甲子 → 海中金"""
        assert NAYIN[("甲", "子")] == "海中金"

    def test_nayin_bingyin(self):
        """丙寅 → 炉中火"""
        assert NAYIN[("丙", "寅")] == "炉中火"

    def test_nayin_wuchen(self):
        """戊辰 → 大林木"""
        assert NAYIN[("戊", "辰")] == "大林木"

    def test_nayin_guihai(self):
        """癸亥 → 大海水"""
        assert NAYIN[("癸", "亥")] == "大海水"


class TestZhiCang:
    """地支藏干"""

    def test_zi_cang(self):
        """子藏癸"""
        assert ZHICANG["子"] == ["癸"]

    def test_chou_cang(self):
        """丑藏己辛癸"""
        assert ZHICANG["丑"] == ["己", "辛", "癸"]

    def test_yin_cang(self):
        """寅藏甲丙戊"""
        assert ZHICANG["寅"] == ["甲", "丙", "戊"]

    def test_mao_cang(self):
        """卯藏乙"""
        assert ZHICANG["卯"] == ["乙"]


class TestCityCoords:
    """城市坐标"""

    def test_beijing(self):
        assert CITY_COORDS["北京"] == (116.4, 39.9)

    def test_shanghai(self):
        assert CITY_COORDS["上海"] == (121.5, 31.2)
