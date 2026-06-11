"""
Global coal consumption time series (past decade).

Source: Energy Institute, Statistical Review of World Energy 2025
(coverage through 2024), as published in the Our World in Data energy
dataset (https://github.com/owid/energy-data). Figures are converted from
TWh to exajoules (EJ) to match the EI "Coal Consumption - EJ" tab,
using 1 EJ = 277.778 TWh.
"""
import pandas as pd
import matplotlib.pyplot as plt

TWH_PER_EJ = 1000 / 3.6  # 277.778

df = pd.read_csv("owid-energy.csv")
world = df[df.country == "World"][["year", "coal_consumption"]].dropna()
world = world[(world.year >= 2015) & (world.year <= 2024)].copy()
world["coal_ej"] = world["coal_consumption"] / TWH_PER_EJ

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(world["year"], world["coal_ej"], marker="o", color="#1f4e5f", linewidth=2)
ax.set_title("Global Coal Consumption, 2015–2024", fontsize=14, fontweight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Coal consumption (exajoules)")
ax.set_xticks(world["year"])
ax.grid(True, axis="y", linestyle="--", alpha=0.5)
ax.margins(x=0.03)
fig.text(0.5, 0.01,
         "Source: Energy Institute, Statistical Review of World Energy 2025 (via Our World in Data)",
         ha="center", fontsize=8, color="gray")
fig.tight_layout(rect=[0, 0.03, 1, 1])
fig.savefig("coal_consumption_global.png", dpi=150)

print(world[["year", "coal_ej"]].round(1).to_string(index=False))
