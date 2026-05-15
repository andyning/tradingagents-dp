"""Test data schema validation."""

from datetime import date

import pytest
from pydantic import ValidationError

from tradingagents.data.schema import KLineRow, KLineData, FinancialSummary, Quote


class TestKLineRow:
    def test_valid_row(self):
        row = KLineRow(
            date=date(2025, 1, 15),
            open=10.0, high=11.0, low=9.5, close=10.5,
            volume=1000000, amount=10500000.0,
        )
        assert row.high == 11.0
        assert row.open == 10.0

    def test_high_lt_low_rejected(self):
        with pytest.raises(ValueError):
            KLineRow(
                date=date(2025, 1, 15),
                open=10.0, high=9.0, low=9.5, close=10.0,
                volume=100, amount=1000.0,
            )

    def test_negative_price_rejected(self):
        with pytest.raises(ValueError):
            KLineRow(
                date=date(2025, 1, 15),
                open=-10.0, high=11.0, low=9.5, close=10.5,
                volume=1000000, amount=10500000.0,
            )


class TestKLineData:
    def test_empty_rows_rejected(self):
        with pytest.raises(ValueError):
            KLineData(symbol="600519", market="a_stock", rows=[])


class TestQuote:
    def test_valid_quote(self):
        q = Quote(symbol="600519", name="贵州茅台", price=1800.0)
        assert q.price == 1800.0
        assert q.name == "贵州茅台"


class TestFinancialSummary:
    def test_valid_summary(self):
        fs = FinancialSummary(
            symbol="600519", report_date=date(2024, 12, 31),
            pe=25.5, pb=8.2, roe=0.32, roa=0.15,
            debt_ratio=0.21, gross_margin=0.92, net_margin=0.52,
            revenue_yoy=0.15, profit_yoy=0.18, market_cap=2.2e4,
        )
        assert fs.pe == 25.5
