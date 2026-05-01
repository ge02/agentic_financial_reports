import pandas as pd
import pytest

from main import analyze, _build_data_summary, _md_table, render_report


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_correct_top_gainer(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        assert result["top_gainers"][0]["ticker"] == "AAA.DE"
        assert result["top_gainers"][0]["value"] == pytest.approx(10.0, abs=0.01)

    def test_correct_top_loser(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        assert result["top_losers"][0]["ticker"] == "ZZZ.DE"
        assert result["top_losers"][0]["value"] == pytest.approx(-10.0, abs=0.01)

    def test_average_return(self, stocks, close_df, volume_df):
        # (10 + 6 + 3 - 3 - 7 - 10) / 6 = -0.17
        result = analyze(stocks, close_df, volume_df)
        assert result["dax_avg_return"] == pytest.approx(-0.17, abs=0.01)

    def test_gainers_sorted_descending(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        values = [s["value"] for s in result["top_gainers"]]
        assert values == sorted(values, reverse=True)

    def test_losers_sorted_ascending(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        values = [s["value"] for s in result["top_losers"]]
        assert values == sorted(values)

    def test_top_volume_spike_is_aaa(self, stocks, close_df, volume_df):
        # AAA last-day volume 2000 vs avg 1270 → ~57.5% spike, highest
        result = analyze(stocks, close_df, volume_df)
        assert result["vol_spikes"][0]["ticker"] == "AAA.DE"

    def test_volume_spike_value_is_correct(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        aaa_spike = next(s for s in result["vol_spikes"] if s["ticker"] == "AAA.DE")
        # avg = (1000+1200+1100+1050+2000)/5 = 1270, last = 2000
        expected = (2000 - 1270) / 1270 * 100
        assert aaa_spike["value"] == pytest.approx(expected, abs=0.1)

    def test_sector_performance_groups_correctly(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        # Technology: AAA (+10) and GGG (+3) → avg 6.5
        assert result["sector_performance"]["Technology"] == pytest.approx(6.5, abs=0.01)
        # Financials: DDD (-3) and ZZZ (-10) → avg -6.5
        assert result["sector_performance"]["Financials"] == pytest.approx(-6.5, abs=0.01)

    def test_stock_name_resolved_from_ticker_map(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        assert result["top_gainers"][0]["name"] == "Alpha AG"

    def test_period_string_uses_correct_dates(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        assert "20 Apr" in result["period"]
        assert "24 Apr" in result["period"]

    def test_raises_on_empty_dataframe(self, stocks):
        with pytest.raises(ValueError, match="Not enough data"):
            analyze(stocks, pd.DataFrame(), pd.DataFrame())

    def test_raises_on_single_row(self, stocks, close_df, volume_df):
        with pytest.raises(ValueError, match="Not enough data"):
            analyze(stocks, close_df.iloc[:1], volume_df.iloc[:1])

    def test_unknown_ticker_falls_back_to_ticker_as_name(self, close_df, volume_df):
        # Stock list doesn't include AAA.DE — name should fall back to ticker string
        sparse_stocks = [
            {"name": "Beta AG", "ticker": "BBB.DE", "industries": ["Automotive"]},
        ]
        result = analyze(sparse_stocks, close_df, volume_df)
        aaa = next((s for s in result["top_gainers"] if s["ticker"] == "AAA.DE"), None)
        if aaa:
            assert aaa["name"] == "AAA.DE"

    def test_stock_with_no_industry_goes_to_other(self, close_df, volume_df):
        stocks_no_industry = [
            {"name": "Alpha AG", "ticker": "AAA.DE", "industries": []},
            {"name": "Beta AG",  "ticker": "BBB.DE", "industries": []},
            {"name": "Gamma AG", "ticker": "GGG.DE", "industries": []},
            {"name": "Delta AG", "ticker": "DDD.DE", "industries": []},
            {"name": "Epsilon AG","ticker": "EEE.DE", "industries": []},
            {"name": "Zeta AG",  "ticker": "ZZZ.DE", "industries": []},
        ]
        result = analyze(stocks_no_industry, close_df, volume_df)
        assert "Other" in result["sector_performance"]

    def test_industry_movers_has_positive_and_negative_keys(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        assert "positive" in result["industry_movers"]
        assert "negative" in result["industry_movers"]

    def test_industry_movers_positive_sorted_descending(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        avgs = [i["avg_return"] for i in result["industry_movers"]["positive"]]
        assert avgs == sorted(avgs, reverse=True)

    def test_industry_movers_negative_sorted_ascending(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        avgs = [i["avg_return"] for i in result["industry_movers"]["negative"]]
        assert avgs == sorted(avgs)

    def test_industry_movers_top_positive_is_technology(self, stocks, close_df, volume_df):
        # Technology avg = +6.5% — highest in fixture
        result = analyze(stocks, close_df, volume_df)
        assert result["industry_movers"]["positive"][0]["sector"] == "Technology"

    def test_industry_movers_top_negative_is_financials(self, stocks, close_df, volume_df):
        # Financials avg = -6.5% — lowest in fixture
        result = analyze(stocks, close_df, volume_df)
        assert result["industry_movers"]["negative"][0]["sector"] == "Financials"

    def test_industry_movers_contains_per_sector_gainers(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        tech = result["industry_movers"]["positive"][0]
        assert len(tech["top_gainers"]) > 0
        # AAA.DE (+10%) should be the top gainer in Technology
        assert tech["top_gainers"][0]["ticker"] == "AAA.DE"

    def test_industry_movers_at_most_three_industries_each(self, stocks, close_df, volume_df):
        result = analyze(stocks, close_df, volume_df)
        assert len(result["industry_movers"]["positive"]) <= 3
        assert len(result["industry_movers"]["negative"]) <= 3

    def test_fewer_than_five_stocks_returns_shorter_lists(self):
        dates = pd.to_datetime(["2026-04-20", "2026-04-21", "2026-04-22",
                                "2026-04-23", "2026-04-24"])
        two_stocks = [
            {"name": "Alpha AG", "ticker": "AAA.DE", "industries": ["Tech"]},
            {"name": "Beta AG",  "ticker": "BBB.DE", "industries": ["Auto"]},
        ]
        close = pd.DataFrame({"AAA.DE": [100, 101, 102, 103, 110],
                               "BBB.DE": [100,  99,  98,  97,  90]}, index=dates)
        volume = pd.DataFrame({"AAA.DE": [1000]*5, "BBB.DE": [1000]*5}, index=dates)
        result = analyze(two_stocks, close, volume)
        assert len(result["top_gainers"]) == 2
        assert len(result["top_losers"]) == 2


# ---------------------------------------------------------------------------
# _build_data_summary
# ---------------------------------------------------------------------------

class TestBuildDataSummary:
    def _sample_analysis(self):
        return {
            "date": "25 April 2026",
            "period": "20 Apr – 24 Apr 2026",
            "dax_avg_return": -0.17,
            "top_gainers": [{"name": "Alpha AG", "ticker": "AAA.DE", "value": 10.0}],
            "top_losers":  [{"name": "Zeta AG",  "ticker": "ZZZ.DE", "value": -10.0}],
            "vol_spikes":  [{"name": "Alpha AG", "ticker": "AAA.DE", "value": 57.5}],
            "sector_performance": {"Technology": 6.5, "Financials": -6.5},
        }

    def test_contains_date(self):
        summary = _build_data_summary(self._sample_analysis())
        assert "25 April 2026" in summary

    def test_contains_average_return(self):
        summary = _build_data_summary(self._sample_analysis())
        assert "-0.17%" in summary

    def test_contains_top_gainer(self):
        summary = _build_data_summary(self._sample_analysis())
        assert "Alpha AG" in summary
        assert "+10.00%" in summary

    def test_contains_top_loser(self):
        summary = _build_data_summary(self._sample_analysis())
        assert "Zeta AG" in summary
        assert "-10.00%" in summary

    def test_sectors_sorted_descending(self):
        summary = _build_data_summary(self._sample_analysis())
        tech_pos = summary.index("Technology")
        fin_pos = summary.index("Financials")
        assert tech_pos < fin_pos  # Technology (6.5%) listed before Financials (-6.5%)


# ---------------------------------------------------------------------------
# _md_table
# ---------------------------------------------------------------------------

class TestMdTable:
    def test_header_row(self):
        rows = [{"A": "x", "B": "y"}]
        out = _md_table(rows, ["A", "B"], ["A", "B"])
        assert out.startswith("|A|B|")

    def test_separator_row(self):
        rows = [{"A": "x", "B": "y"}]
        out = _md_table(rows, ["A", "B"], ["A", "B"])
        assert "|---|---|" in out

    def test_body_row_values(self):
        rows = [{"A": "hello", "B": "world"}]
        out = _md_table(rows, ["A", "B"], ["A", "B"])
        assert "|hello|world|" in out

    def test_multiple_rows(self):
        rows = [{"A": "1"}, {"A": "2"}, {"A": "3"}]
        out = _md_table(rows, ["A"], ["A"])
        assert out.count("|1|") == 1
        assert out.count("|2|") == 1
        assert out.count("|3|") == 1


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------

class TestRenderReport:
    def _sample_analysis(self):
        return {
            "date": "25 April 2026",
            "period": "20 Apr – 24 Apr 2026",
            "dax_avg_return": 1.5,
            "top_gainers": [{"name": "Alpha AG", "ticker": "AAA.DE", "value": 10.0}],
            "top_losers":  [{"name": "Zeta AG",  "ticker": "ZZZ.DE", "value": -10.0}],
            "vol_spikes":  [{"name": "Alpha AG", "ticker": "AAA.DE", "value": 57.5}],
            "sector_performance": {"Technology": 1.5},
            "industry_movers": {
                "positive": [{"sector": "Technology", "avg_return": 1.5,
                              "top_gainers": [{"name": "Alpha AG", "ticker": "AAA.DE", "value": 10.0}],
                              "top_losers": []}],
                "negative": [{"sector": "Financials", "avg_return": -6.5,
                              "top_gainers": [],
                              "top_losers": [{"name": "Zeta AG", "ticker": "ZZZ.DE", "value": -10.0}]}],
            },
        }

    def test_contains_report_title(self):
        report = render_report(self._sample_analysis(), "Test commentary.")
        assert "# DAX 40 Market Report" in report

    def test_positive_return_shows_plus_sign(self):
        report = render_report(self._sample_analysis(), "")
        assert "**+1.50%**" in report

    def test_negative_return_shows_no_extra_sign(self):
        analysis = self._sample_analysis()
        analysis["dax_avg_return"] = -2.0
        report = render_report(analysis, "")
        assert "**-2.00%**" in report

    def test_commentary_is_included(self):
        report = render_report(self._sample_analysis(), "Great week for markets.")
        assert "Great week for markets." in report

    def test_contains_all_sections(self):
        report = render_report(self._sample_analysis(), "commentary")
        for section in ["Top Gainers", "Top Losers", "Volume Spikes",
                        "Sector Performance", "AI Commentary",
                        "Industry Deep Dive", "Best Performing Industries",
                        "Worst Performing Industries"]:
            assert section in report

    def test_industry_deep_dive_contains_sector_names(self):
        report = render_report(self._sample_analysis(), "commentary")
        assert "Technology" in report
        assert "Financials" in report
