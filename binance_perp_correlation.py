#!/usr/bin/env python3
"""
Find near-duplicate Binance USDT-M perpetual futures by daily return correlation.

Fetches the Binance USDT-M perpetual universe, pulls recent daily klines per
symbol, builds a log-return matrix, computes pairwise Pearson correlation, and
reports pairs and clusters of symbols whose returns are highly correlated
(>= CORR_THRESHOLD) -- i.e. redundant / near-duplicate exposure.

Dependencies: requests, pandas, numpy, scipy

Usage:
    python binance_perp_correlation.py
    python binance_perp_correlation.py --threshold 0.99
    python binance_perp_correlation.py --filter DOGE --lookback 90
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

# ----------------------------------------------------------------------------
# Config knobs (overridable via CLI)
# ----------------------------------------------------------------------------
INTERVAL = "1d"          # kline interval
LOOKBACK_DAYS = 180      # ~6 months. Shorter catches short-term duplicates;
                         # longer is dominated by BTC-beta.
CORR_THRESHOLD = 0.97    # report pairs/clusters at or above this correlation.
                         # Use 0.99 to isolate near-identical "same asset,
                         # different symbol" cases.
SYMBOL_FILTER = ""       # optional substring filter to scope to a sector
                         # first for a faster pass (e.g. "DOGE", "1000").

# Coverage / overlap thresholds
COVERAGE_FRACTION = 0.90    # drop symbols present on < 90% of the date index
MIN_PERIODS_FRACTION = 0.70 # require >= 70% overlapping returns per pair

# Request pacing
REQUEST_SLEEP = 0.15     # seconds between kline requests
MAX_RETRIES = 5          # retries on 429 / transient errors

BASE_URL = "https://fapi.binance.com"
EXCHANGE_INFO_URL = f"{BASE_URL}/fapi/v1/exchangeInfo"
KLINES_URL = f"{BASE_URL}/fapi/v1/klines"

OUTPUT_MATRIX_CSV = "binance_perp_correlation_matrix.csv"

# Known trivial equivalences: same underlying asset under different tickers
# (rebrands / ticker swaps). Pairs whose *base assets* both fall in one of
# these groups are flagged as trivial and excluded from the "interesting" list.
TRIVIAL_EQUIVALENCE_GROUPS: List[frozenset] = [
    frozenset({"MATIC", "POL"}),      # Polygon rebrand
    frozenset({"FTM", "S"}),          # Fantom -> Sonic rebrand
    frozenset({"CFG", "CENTRIFUGE"}),
    frozenset({"OCEAN", "FET", "AGIX"}),  # Artificial Superintelligence merger
    frozenset({"GALA", "GALAX"}),
]

# Numeric-multiplier prefixes Binance uses for low-priced assets
# (e.g. 1000SHIB, 1000000MOG). Two symbols that differ only by such a prefix
# are the same underlying asset.
_MULTIPLIER_PREFIXES = ("1000000000", "1000000", "10000", "1000", "100", "10")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "binance-perp-correlation/1.0"})


# ----------------------------------------------------------------------------
# Fetching
# ----------------------------------------------------------------------------
def _get_with_retry(url: str, params: Optional[dict] = None) -> requests.Response:
    """GET with exponential backoff on 429 / 5xx / transient network errors."""
    backoff = 1.0
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = SESSION.get(url, params=params, timeout=30)
        except requests.RequestException as exc:  # network hiccup
            last_exc = exc
            time.sleep(backoff)
            backoff *= 2
            continue

        if resp.status_code == 200:
            return resp

        if resp.status_code == 429 or resp.status_code == 418:
            # Rate limited / IP banned briefly. Respect Retry-After if present.
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else backoff
            sys.stderr.write(
                f"  rate limited ({resp.status_code}), sleeping {wait:.1f}s\n"
            )
            time.sleep(wait)
            backoff *= 2
            continue

        if 500 <= resp.status_code < 600:
            time.sleep(backoff)
            backoff *= 2
            continue

        # Other client error -> not retryable
        resp.raise_for_status()

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Failed to GET {url} after {MAX_RETRIES} attempts")


def fetch_perpetual_symbols() -> List[str]:
    """Return sorted list of TRADING USDT-M perpetual symbols."""
    resp = _get_with_retry(EXCHANGE_INFO_URL)
    data = resp.json()
    symbols = []
    for s in data.get("symbols", []):
        if (
            s.get("contractType") == "PERPETUAL"
            and s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
        ):
            symbols.append(s["symbol"])
    return sorted(symbols)


def fetch_klines(symbol: str, interval: str, limit: int) -> Optional[pd.Series]:
    """Fetch daily closes for a symbol as a Series indexed by UTC date.

    Returns None if the symbol has no data.
    """
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = _get_with_retry(KLINES_URL, params=params)
    rows = resp.json()
    if not rows:
        return None

    open_times = [row[0] for row in rows]      # index 0: open time (ms)
    closes = [float(row[4]) for row in rows]   # index 4: close price
    idx = pd.to_datetime(open_times, unit="ms", utc=True).normalize()
    series = pd.Series(closes, index=idx, name=symbol)
    # Guard against any duplicate timestamps
    series = series[~series.index.duplicated(keep="last")]
    return series


def fetch_all_closes(
    symbols: List[str], interval: str, limit: int
) -> Dict[str, pd.Series]:
    """Fetch close-price series for every symbol, with pacing + progress."""
    closes: Dict[str, pd.Series] = {}
    total = len(symbols)
    for i, symbol in enumerate(symbols, 1):
        try:
            series = fetch_klines(symbol, interval, limit)
        except Exception as exc:  # noqa: BLE001 - keep going on per-symbol failure
            sys.stderr.write(f"  [{i}/{total}] {symbol}: fetch failed ({exc})\n")
            continue
        if series is not None and len(series) > 0:
            closes[symbol] = series
        if i % 25 == 0 or i == total:
            sys.stderr.write(f"  fetched {i}/{total} symbols\n")
            sys.stderr.flush()
        time.sleep(REQUEST_SLEEP)
    return closes


# ----------------------------------------------------------------------------
# Matrix building
# ----------------------------------------------------------------------------
def build_returns_matrix(
    closes: Dict[str, pd.Series], coverage_fraction: float
) -> pd.DataFrame:
    """Align closes on a common date index and compute log returns.

    Columns with < coverage_fraction of non-null closes are dropped.
    """
    if not closes:
        raise ValueError("No close-price data fetched.")

    price = pd.DataFrame(closes).sort_index()  # outer join on the date index
    n_dates = len(price.index)
    min_obs = int(np.ceil(coverage_fraction * n_dates))

    coverage = price.notna().sum()
    keep = coverage[coverage >= min_obs].index
    dropped = sorted(set(price.columns) - set(keep))
    if dropped:
        sys.stderr.write(
            f"  dropped {len(dropped)} symbols with < {coverage_fraction:.0%} "
            f"coverage (short history)\n"
        )
    price = price[keep]

    # Log returns: ln(P_t / P_{t-1}). Requires positive prices.
    price = price.where(price > 0)
    log_returns = np.log(price / price.shift(1))
    log_returns = log_returns.iloc[1:]  # first row is all-NaN
    return log_returns


def compute_correlation(
    returns: pd.DataFrame, min_periods_fraction: float
) -> pd.DataFrame:
    """Pairwise Pearson correlation with a minimum-overlap guard."""
    window = len(returns)
    min_periods = max(2, int(np.ceil(min_periods_fraction * window)))
    corr = returns.corr(method="pearson", min_periods=min_periods)
    return corr


# ----------------------------------------------------------------------------
# Trivial-equivalence detection
# ----------------------------------------------------------------------------
def base_asset(symbol: str) -> str:
    """Strip the USDT quote and any numeric multiplier prefix."""
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    for prefix in _MULTIPLIER_PREFIXES:
        if base.startswith(prefix) and len(base) > len(prefix):
            return base[len(prefix):]
    return base


def is_trivial_pair(sym_a: str, sym_b: str) -> bool:
    """True if the two symbols are the same underlying asset.

    Covers: identical base asset after stripping numeric multiplier prefixes
    (1000SHIB vs SHIB), and known rebrand / ticker-swap equivalence groups
    (MATIC vs POL, etc.).
    """
    base_a, base_b = base_asset(sym_a), base_asset(sym_b)
    if base_a == base_b:
        return True
    for group in TRIVIAL_EQUIVALENCE_GROUPS:
        if base_a in group and base_b in group:
            return True
    return False


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------
def find_pairs(
    corr: pd.DataFrame, threshold: float
) -> List[Tuple[str, str, float]]:
    """All symbol pairs with correlation >= threshold, sorted descending."""
    symbols = list(corr.columns)
    pairs: List[Tuple[str, str, float]] = []
    values = corr.values
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            c = values[i, j]
            if np.isfinite(c) and c >= threshold:
                pairs.append((symbols[i], symbols[j], float(c)))
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs


def print_pairs(pairs: List[Tuple[str, str, float]]) -> None:
    interesting = [p for p in pairs if not is_trivial_pair(p[0], p[1])]
    trivial = [p for p in pairs if is_trivial_pair(p[0], p[1])]

    print("\n" + "=" * 64)
    print(f"NEAR-DUPLICATE PAIRS (corr >= {CORR_THRESHOLD})")
    print("=" * 64)
    if interesting:
        width = max(len(s) for p in interesting for s in p[:2])
        for a, b, c in interesting:
            print(f"{a:<{width}}  {b:<{width}}  {c:.4f}")
    else:
        print("(none)")

    print("\n" + "-" * 64)
    print(f"TRIVIAL / SAME-ASSET PAIRS (excluded from above): {len(trivial)}")
    print("-" * 64)
    if trivial:
        width = max(len(s) for p in trivial for s in p[:2])
        for a, b, c in trivial:
            print(f"{a:<{width}}  {b:<{width}}  {c:.4f}")
    else:
        print("(none)")


def find_clusters(
    corr: pd.DataFrame, threshold: float
) -> List[List[str]]:
    """Hierarchical (average-linkage) clustering on distance = 1 - corr.

    Cut the tree at distance = 1 - threshold. Returns clusters with > 1 member.
    """
    symbols = list(corr.columns)
    if len(symbols) < 2:
        return []

    # Distance matrix; clip to [0, 2] and fill missing overlaps as max distance.
    dist = 1.0 - corr.values
    dist = np.nan_to_num(dist, nan=2.0, posinf=2.0, neginf=2.0)
    np.fill_diagonal(dist, 0.0)
    dist = np.clip(dist, 0.0, 2.0)
    # Enforce symmetry for squareform.
    dist = (dist + dist.T) / 2.0
    np.fill_diagonal(dist, 0.0)

    condensed = squareform(dist, checks=False)
    linkage_matrix = linkage(condensed, method="average")
    labels = fcluster(linkage_matrix, t=1.0 - threshold, criterion="distance")

    clusters: Dict[int, List[str]] = {}
    for sym, lab in zip(symbols, labels):
        clusters.setdefault(lab, []).append(sym)

    multi = [sorted(members) for members in clusters.values() if len(members) > 1]
    # Sort clusters by size (desc) then alphabetically.
    multi.sort(key=lambda m: (-len(m), m))
    return multi


def print_clusters(clusters: List[List[str]]) -> None:
    print("\n" + "=" * 64)
    print(f"CORRELATION CLUSTERS (cut at distance = {1 - CORR_THRESHOLD:.4f})")
    print("=" * 64)
    if not clusters:
        print("(no multi-member clusters)")
        return
    for i, members in enumerate(clusters, 1):
        all_trivial = all(
            is_trivial_pair(members[a], members[b])
            for a in range(len(members))
            for b in range(a + 1, len(members))
        )
        tag = "  [same-asset]" if all_trivial else ""
        print(f"Cluster {i} ({len(members)} members){tag}: {', '.join(members)}")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--interval", default=INTERVAL, help="kline interval")
    p.add_argument(
        "--lookback", type=int, default=LOOKBACK_DAYS,
        help="number of klines / days to fetch",
    )
    p.add_argument(
        "--threshold", type=float, default=CORR_THRESHOLD,
        help="correlation threshold for near-duplicates",
    )
    p.add_argument(
        "--filter", default=SYMBOL_FILTER,
        help="optional symbol substring filter (e.g. DOGE, 1000)",
    )
    p.add_argument(
        "--output", default=OUTPUT_MATRIX_CSV,
        help="path for the full correlation-matrix CSV",
    )
    return p.parse_args()


def main() -> int:
    global INTERVAL, LOOKBACK_DAYS, CORR_THRESHOLD, SYMBOL_FILTER
    args = parse_args()
    INTERVAL = args.interval
    LOOKBACK_DAYS = args.lookback
    CORR_THRESHOLD = args.threshold
    SYMBOL_FILTER = args.filter

    print(
        f"Config: interval={INTERVAL} lookback={LOOKBACK_DAYS} "
        f"threshold={CORR_THRESHOLD} filter={SYMBOL_FILTER!r}",
        file=sys.stderr,
    )

    print("Fetching perpetual symbol universe...", file=sys.stderr)
    symbols = fetch_perpetual_symbols()
    print(f"  {len(symbols)} USDT-M perpetuals TRADING", file=sys.stderr)

    if SYMBOL_FILTER:
        symbols = [s for s in symbols if SYMBOL_FILTER.upper() in s.upper()]
        print(f"  {len(symbols)} after filter {SYMBOL_FILTER!r}", file=sys.stderr)

    if not symbols:
        print("No symbols to process.", file=sys.stderr)
        return 1

    print("Fetching daily klines...", file=sys.stderr)
    closes = fetch_all_closes(symbols, INTERVAL, LOOKBACK_DAYS)
    print(f"  got price data for {len(closes)} symbols", file=sys.stderr)

    print("Building returns matrix...", file=sys.stderr)
    returns = build_returns_matrix(closes, COVERAGE_FRACTION)
    print(
        f"  {returns.shape[1]} symbols x {returns.shape[0]} return periods",
        file=sys.stderr,
    )

    print("Computing correlation matrix...", file=sys.stderr)
    corr = compute_correlation(returns, MIN_PERIODS_FRACTION)

    corr.to_csv(args.output)
    print(f"  saved full correlation matrix -> {args.output}", file=sys.stderr)

    pairs = find_pairs(corr, CORR_THRESHOLD)
    print_pairs(pairs)

    clusters = find_clusters(corr, CORR_THRESHOLD)
    print_clusters(clusters)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
