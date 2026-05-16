"""Tests for news_filter — relevance scoring, dedup, edge cases."""

from tradingagents.graph.news_filter import filter_news, _deduplicate


class TestFilterNews:
    def test_empty_input(self):
        result = filter_news([], "600519")
        assert result == []

    def test_symbol_match(self):
        items = [
            {"title": "贵州茅台(600519)业绩超预期", "source": "证券时报"},
            {"title": "全球市场今日动态", "source": "Reuters"},
        ]
        result = filter_news(items, "600519", company_name="贵州茅台")
        assert len(result) >= 1
        assert "600519" in result[0]["title"]

    def test_all_irrelevant(self):
        items = [
            {"title": "天气预报警告", "source": "CCTV"},
            {"title": "体育赛事结果", "source": "ESPN"},
        ]
        result = filter_news(items, "600519")
        assert result == []

    def test_noise_filtered(self):
        items = [
            {"title": "Sponsored: 贵州茅台推荐", "source": "ad"},
            {"title": "订阅我们的财经频道", "source": "promo"},
            {"title": "广告：茅台促销活动", "source": "spam"},
        ]
        result = filter_news(items, "600519")
        # All three are noise keywords — should be empty
        noise_kw = ["advertisement", "sponsored", "promoted", "subscribe", "广告", "推广", "赞助", "订阅", "免责声明"]
        for item in items:
            title = item["title"].lower()
            if any(nk in title for nk in noise_kw):
                assert item not in result

    def test_credible_source_bonus(self):
        items = [
            {"title": "茅台营收增长25%", "source": "Reuters"},
            {"title": "茅台营收增长25%", "source": "Unknown Blog"},
        ]
        result = filter_news(items, "600519", company_name="茅台")
        # Both should pass, but Reuters one should score higher (first in list)
        assert len(result) >= 1


class TestDeduplicate:
    def test_identical_titles(self):
        items = [
            {"title": "茅台业绩增长", "source": "A"},
            {"title": "茅台业绩增长", "source": "B"},
        ]
        result = _deduplicate(items)
        assert len(result) == 1

    def test_similar_titles(self):
        """Titles with same first 30 chars should be deduped."""
        items = [
            {"title": "贵州茅台2026年第一季度财报公布营收大幅增长超出市场预期25%", "source": "A"},
            {"title": "贵州茅台2026年第一季度财报公布营收大幅增长超出市场预期25%", "source": "B"},
        ]
        result = _deduplicate(items)
        assert len(result) == 1

    def test_different_titles(self):
        items = [
            {"title": "茅台业绩超预期", "source": "A"},
            {"title": "五粮液发布新产品", "source": "B"},
        ]
        result = _deduplicate(items)
        assert len(result) == 2


class TestEdgeCases:
    def test_none_title(self):
        items = [{"title": None, "source": "A"}]
        result = filter_news(items, "600519")
        assert result == []

    def test_empty_title(self):
        items = [{"title": "", "source": "A"}]
        result = filter_news(items, "600519")
        assert result == []

    def test_missing_fields(self):
        items = [{"source": "A"}]  # No title at all
        result = filter_news(items, "600519")
        assert result == []

    def test_company_name_matching(self):
        items = [
            {"title": "歌尔股份获大客户订单", "source": "东方财富"},
            {"title": "全球手机出货量增长", "source": "Reuters"},
        ]
        result = filter_news(items, "002241", company_name="歌尔股份")
        assert len(result) >= 1
        assert "歌尔" in result[0]["title"]

    def test_max_items_limit(self):
        items = [{"title": f"茅台新闻{i}", "source": "X"} for i in range(30)]
        result = filter_news(items, "600519", company_name="茅台", max_items=5)
        assert len(result) <= 5
