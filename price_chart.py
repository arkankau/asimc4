from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DATA_DIR = Path("ROUND1")

frames = [pd.read_csv(p, sep=";") for p in sorted(DATA_DIR.glob("prices_round_1_day_*.csv"))]
df = pd.concat(frames, ignore_index=True)
df["t"] = (df["day"] - df["day"].min()) * 1_000_000 + df["timestamp"]

ipr = df[(df["product"] == "INTARIAN_PEPPER_ROOT") & (df["mid_price"] > 0)][["t","mid_price"]].drop_duplicates("t").sort_values("t")
aco = df[(df["product"] == "ASH_COATED_OSMIUM") & (df["mid_price"] > 0)][["t","mid_price"]].drop_duplicates("t").sort_values("t")

day_breaks = [1_000_000, 2_000_000]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
fig.suptitle("Round 1 — Mid Price Over Time", fontsize=14)

ax1.plot(ipr["t"], ipr["mid_price"], color="#d62728", lw=0.8)
ax1.set_ylabel("Price (XIREC)")
ax1.set_title("INTARIAN_PEPPER_ROOT  (+~1000/day uptrend)")
for b in day_breaks:
    ax1.axvline(b, color="gray", ls="--", alpha=0.5, label="day boundary")
ax1.legend(["mid price", "day boundary"])

ax2.plot(aco["t"], aco["mid_price"], color="#1f77b4", lw=0.8)
ax2.set_ylabel("Price (XIREC)")
ax2.set_title("ASH_COATED_OSMIUM  (mean-reverts ~10000)")
ax2.axhline(10000, color="orange", ls="--", lw=1, label="fair value 10000")
for b in day_breaks:
    ax2.axvline(b, color="gray", ls="--", alpha=0.5)
ax2.legend(["mid price", "fair value 10000", "day boundary"])
ax2.set_xlabel("Time (day 0 starts at 0, day 1 at 1M, day 2 at 2M)")

plt.tight_layout()
plt.savefig("price_chart.png", dpi=150, bbox_inches="tight")
print("Saved to price_chart.png")
