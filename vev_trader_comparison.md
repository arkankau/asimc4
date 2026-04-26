# VEV Trader Comparison

| Trader | Day 0 | Day 1 | Day 2 | Split Total | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `vev_trader_zscore.py` | -144826 | -141799 | -137331 | -423956 | Worst by a wide margin. Pure per-voucher mean reversion is not a good fit for these data. |
| `vev_trader_bs.py` | -82438 | -40261 | -27288 | -149987 | Much better than z-score, but still materially worse than smile-based relative pricing. |
| `vev_trader_smile.py` | -13854 | -21301 | -27984 | -63139 | Best result on every historical day and on the split replay. Promoted to live default. |

## Promotion Decision

`vev_trader.py` is aligned with `vev_trader_smile.py`.

The current three-way comparison does not produce a profitable historical bot, but among the implemented candidates the smile trader is the clear winner:

- lowest loss on day 0
- lowest loss on day 1
- lowest loss on day 2
- lowest loss on split replay

## Next Read

If we keep iterating, the first target should be improving the smile trader rather than revisiting the z-score baseline. The gap between smile and single-vol Black-Scholes suggests that cross-strike relative pricing is the right direction, but the current thresholds and execution still need tuning.
