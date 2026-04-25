# ROUND2 Jupyter Workspace

This folder is a cleaner round 2 analysis workspace built from the structure of the round 1 notebook, but reorganized around decisions that are useful for market making:

1. Market behavior
2. Execution quality
3. Strategy implications

Files:

- `round2_eda.ipynb`: main notebook scaffold for round 2 analysis

The notebook is set up to read the existing files in `ROUND2/`:

- `prices_round_2_day_-1.csv`
- `prices_round_2_day_0.csv`
- `prices_round_2_day_1.csv`
- `trades_round_2_day_-1.csv`
- `trades_round_2_day_0.csv`
- `trades_round_2_day_1.csv`

Compared with the round 1 notebook, this version puts more weight on:

- trade markouts / adverse selection
- passive fill-quality proxies
- toxicity by regime
- signal decay by horizon
- quote-width, skew, and inventory rule calibration
- a parameterized MAF break-even view

If you want, the next natural step is to split the execution-quality and replay logic into a small `utils.py` helper module so future notebooks stay shorter.
