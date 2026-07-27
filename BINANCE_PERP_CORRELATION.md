# Binance perp near-duplicate finder

`binance_perp_correlation.py` finds Binance USDT-M perpetual futures whose daily
return series are highly correlated (>= 0.97 by default) — i.e. redundant /
near-duplicate exposure across the perp universe.

## What it does

1. Fetches the USDT-M perpetual universe from
   `fapi.binance.com/fapi/v1/exchangeInfo`
   (`contractType == PERPETUAL`, `status == TRADING`, `quoteAsset == USDT`).
2. Pulls the last ~180 daily klines per symbol (`/fapi/v1/klines`), paced with a
   short sleep and 429-aware exponential backoff.
3. Aligns closes on a common date index, drops symbols with < 90% coverage
   (recently listed), and computes log returns `ln(P_t / P_{t-1})`.
4. Computes pairwise Pearson correlation (min-overlap guard = 70% of the window).
5. Reports pairs with `corr >= threshold`, sorted descending, and **separately**
   lists trivial same-asset pairs (multiplier prefixes like `1000SHIB` vs
   `SHIB`, and known rebrands like `MATIC`/`POL`) so they don't drown out the
   genuinely interesting duplicates.
6. Runs average-linkage hierarchical clustering on `distance = 1 - corr`, cut at
   `1 - threshold`, to surface chains (A~B, B~C) that a flat pairwise list would
   fragment.
7. Saves the full correlation matrix to `binance_perp_correlation_matrix.csv`
   for re-slicing at different thresholds without re-fetching.

## Usage

```bash
pip install requests pandas numpy scipy

python binance_perp_correlation.py                      # full universe, corr >= 0.97
python binance_perp_correlation.py --threshold 0.99     # isolate near-identical symbols
python binance_perp_correlation.py --filter DOGE        # scope to a sector first
python binance_perp_correlation.py --lookback 90        # shorter window
```

Config knobs (CLI flags, defaults at top of the script):
`--interval` (1d), `--lookback` (180), `--threshold` (0.97),
`--filter` (substring), `--output` (CSV path).

## Note on running here

The full analysis pipeline (matrix build, correlation, clustering,
trivial-pair detection) is verified with synthetic data. The **live fetch was
not exercised in the build environment** because its egress policy blocks
`fapi.binance.com` (403 on CONNECT). Run the script from an environment with
outbound access to Binance to pull real data.
