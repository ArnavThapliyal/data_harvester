from .Numeric.yfinance_collector import YFinanceCollector
from .Numeric.nse_collector import NSECollector
from .Numeric.bsc_collector import BSCCollector
from .Numeric.screener_collector import ScreenerCollector

COLLECTOR_REGISTRY = {
    "yfinance": YFinanceCollector,
    "nse": NSECollector,
    "bsc": BSCCollector,
    "screener": ScreenerCollector,
}

def get_collector(source_name: str, **kwargs):
    cls = COLLECTOR_REGISTRY.get(source_name)
    if not cls:
        raise ValueError(f"Unknown source: {source_name}")
    return cls(**kwargs)

def get_collectors():
    """Return list of all registered collector classes"""
    return list(COLLECTOR_REGISTRY.values())