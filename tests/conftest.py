import pandas as pd
import pytest

DATES = pd.to_datetime(
    ["2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23", "2026-04-24"]
)

# Six stocks: 3 gainers, 3 losers, two sectors each
STOCKS = [
    {"name": "Alpha AG",   "ticker": "AAA.DE", "industries": ["Technology"]},
    {"name": "Beta AG",    "ticker": "BBB.DE", "industries": ["Automotive"]},
    {"name": "Gamma AG",   "ticker": "GGG.DE", "industries": ["Technology"]},
    {"name": "Delta AG",   "ticker": "DDD.DE", "industries": ["Financials"]},
    {"name": "Epsilon AG", "ticker": "EEE.DE", "industries": ["Automotive"]},
    {"name": "Zeta AG",    "ticker": "ZZZ.DE", "industries": ["Financials"]},
]

# Day-1 → Day-5 prices chosen for exact known returns:
#   AAA +10%, BBB +6%, GGG +3%, DDD -3%, EEE -7%, ZZZ -10%
CLOSE_VALUES = {
    "AAA.DE": [100.0, 102.0, 104.0, 106.0, 110.0],
    "BBB.DE": [100.0, 103.0, 105.0, 107.0, 106.0],
    "GGG.DE": [100.0, 101.0, 100.5, 101.5, 103.0],
    "DDD.DE": [100.0,  99.0,  98.0,  97.5,  97.0],
    "EEE.DE": [100.0,  98.0,  96.0,  94.0,  93.0],
    "ZZZ.DE": [100.0,  95.0,  93.0,  92.0,  90.0],
}

# Last-day volume spike: AAA ~58% above avg, ZZZ ~49% above avg
VOLUME_VALUES = {
    "AAA.DE": [1000, 1200, 1100, 1050, 2000],
    "BBB.DE": [2000, 2100, 1900, 2000, 2050],
    "GGG.DE": [500,  600,  550,  520,  510],
    "DDD.DE": [800,  850,  820,  810,  800],
    "EEE.DE": [1500, 1600, 1400, 1500, 1550],
    "ZZZ.DE": [3000, 2900, 3100, 2800, 5000],
}


@pytest.fixture
def stocks():
    return STOCKS


@pytest.fixture
def close_df():
    return pd.DataFrame(CLOSE_VALUES, index=DATES)


@pytest.fixture
def volume_df():
    return pd.DataFrame(VOLUME_VALUES, index=DATES)
