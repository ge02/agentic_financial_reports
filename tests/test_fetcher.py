import pandas as pd
import pytest

from main import _valid_yahoo_ticker, get_dax_tickers, _fetch_ticker, fetch_ohlcv


# ---------------------------------------------------------------------------
# _valid_yahoo_ticker
# ---------------------------------------------------------------------------

class TestValidYahooTicker:
    def test_accepts_de_suffix(self):
        assert _valid_yahoo_ticker("ADS.DE") is True

    def test_accepts_frankfurt_suffix(self):
        assert _valid_yahoo_ticker("AIR.F") is True

    def test_accepts_single_char_suffix(self):
        assert _valid_yahoo_ticker("X.F") is True

    def test_rejects_double_suffix(self):
        # AIR.PA.DE is the real-world bad value from pytickersymbols
        assert _valid_yahoo_ticker("AIR.PA.DE") is False

    def test_rejects_no_dot(self):
        assert _valid_yahoo_ticker("NODOT") is False

    def test_rejects_empty_string(self):
        assert _valid_yahoo_ticker("") is False

    def test_rejects_suffix_too_long(self):
        assert _valid_yahoo_ticker("SAP.XETR") is False


# ---------------------------------------------------------------------------
# get_dax_tickers  (mocked PyTickerSymbols)
# ---------------------------------------------------------------------------

class TestGetDaxTickers:
    def _make_stock(self, name, symbol, symbols=None, industries=None):
        return {
            "name": name,
            "symbol": symbol,
            "symbols": symbols or [],
            "industries": industries or [],
        }

    def test_uses_symbol_field_when_valid(self, mocker):
        mocker.patch(
            "main.PyTickerSymbols.get_stocks_by_index",
            return_value=[self._make_stock("Alpha AG", "AAA.DE")],
        )
        result = get_dax_tickers()
        assert len(result) == 1
        assert result[0]["ticker"] == "AAA.DE"
        assert result[0]["name"] == "Alpha AG"

    def test_falls_back_to_symbols_list_de(self, mocker):
        mocker.patch(
            "main.PyTickerSymbols.get_stocks_by_index",
            return_value=[
                self._make_stock(
                    "Airbus",
                    "AIR.PA.DE",  # bad primary symbol
                    symbols=[{"yahoo": "AIR.DE"}, {"yahoo": "AIR.F"}],
                )
            ],
        )
        result = get_dax_tickers()
        assert result[0]["ticker"] == "AIR.DE"

    def test_falls_back_to_frankfurt_when_no_de(self, mocker):
        mocker.patch(
            "main.PyTickerSymbols.get_stocks_by_index",
            return_value=[
                self._make_stock(
                    "Airbus",
                    "AIR.PA.DE",
                    symbols=[{"yahoo": "EADSY"}, {"yahoo": "AIR.F"}],
                )
            ],
        )
        result = get_dax_tickers()
        assert result[0]["ticker"] == "AIR.F"

    def test_skips_stock_with_no_usable_ticker(self, mocker):
        mocker.patch(
            "main.PyTickerSymbols.get_stocks_by_index",
            return_value=[
                self._make_stock("Bad Corp", "", symbols=[{"yahoo": "BC.XETR"}]),
            ],
        )
        result = get_dax_tickers()
        assert result == []

    def test_includes_industries(self, mocker):
        mocker.patch(
            "main.PyTickerSymbols.get_stocks_by_index",
            return_value=[
                self._make_stock("SAP", "SAP.DE", industries=["Software", "Cloud"]),
            ],
        )
        result = get_dax_tickers()
        assert result[0]["industries"] == ["Software", "Cloud"]


# ---------------------------------------------------------------------------
# _fetch_ticker  (mocked yf.Ticker)
# ---------------------------------------------------------------------------

class TestFetchTicker:
    def _make_hist(self, n=15):
        idx = pd.date_range("2026-04-01", periods=n, freq="B")
        return pd.DataFrame({"Close": range(n), "Volume": range(n)}, index=idx)

    def test_returns_series_on_success(self, mocker):
        mocker.patch("main.yf.Ticker").return_value.history.return_value = self._make_hist()
        close, volume = _fetch_ticker("SAP.DE")
        assert close is not None
        assert volume is not None

    def test_returns_none_for_empty_history(self, mocker):
        mocker.patch("main.yf.Ticker").return_value.history.return_value = pd.DataFrame()
        close, volume = _fetch_ticker("SAP.DE")
        assert close is None
        assert volume is None

    def test_returns_none_immediately_on_non_rate_limit_error(self, mocker):
        mocker.patch("main.yf.Ticker").return_value.history.side_effect = ValueError("bad ticker")
        mocker.patch("main.time.sleep")
        close, volume = _fetch_ticker("BAD.DE")
        assert close is None
        assert volume is None

    def test_retries_on_rate_limit_then_succeeds(self, mocker):
        hist = self._make_hist()
        ticker_mock = mocker.patch("main.yf.Ticker").return_value
        ticker_mock.history.side_effect = [
            Exception("Too Many Requests. Rate limited."),
            hist,
        ]
        mocker.patch("main.time.sleep")
        close, volume = _fetch_ticker("SAP.DE")
        assert close is not None
        assert ticker_mock.history.call_count == 2

    def test_gives_up_after_all_retries_exhausted(self, mocker):
        ticker_mock = mocker.patch("main.yf.Ticker").return_value
        ticker_mock.history.side_effect = Exception("429 rate limited")
        mocker.patch("main.time.sleep")
        close, volume = _fetch_ticker("SAP.DE")
        assert close is None


# ---------------------------------------------------------------------------
# fetch_ohlcv  (mocked _fetch_ticker)
# ---------------------------------------------------------------------------

class TestFetchOhlcv:
    def _series(self, ticker, n=15):
        idx = pd.date_range("2026-04-01", periods=n, freq="B")
        return pd.Series(range(n), index=idx, name=ticker)

    def test_returns_dataframes_with_correct_shape(self, mocker):
        tickers = ["AAA.DE", "BBB.DE"]
        mocker.patch("main.time.sleep")
        mocker.patch(
            "main._fetch_ticker",
            side_effect=[(self._series(t), self._series(t)) for t in tickers],
        )
        close, volume = fetch_ohlcv(tickers)
        assert list(close.columns) == tickers
        assert len(close) == 5  # tail(5)

    def test_returns_empty_dataframes_when_all_fail(self, mocker):
        mocker.patch("main.time.sleep")
        mocker.patch("main._fetch_ticker", return_value=(None, None))
        close, volume = fetch_ohlcv(["AAA.DE", "BBB.DE"])
        assert close.empty
        assert volume.empty

    def test_skips_failed_tickers_and_keeps_rest(self, mocker):
        mocker.patch("main.time.sleep")
        good = self._series("BBB.DE")
        mocker.patch(
            "main._fetch_ticker",
            side_effect=[(None, None), (good, good)],
        )
        close, _ = fetch_ohlcv(["AAA.DE", "BBB.DE"])
        assert "BBB.DE" in close.columns
        assert "AAA.DE" not in close.columns
