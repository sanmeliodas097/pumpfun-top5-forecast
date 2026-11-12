# pumpfun-top5-forecast

[![make.fun · pumpfun-top5-forecast-01](https://make.fun/badge/pumpfun-top5-forecast-01.svg)](https://make.fun/bounty/pumpfun-top5-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=pumpfun-top5-forecast-01)
[![rank](https://make.fun/badge/pumpfun-top5-forecast-01/sanmeliodas097/pumpfun-top5-forecast/rank.svg)](https://make.fun/bounty/pumpfun-top5-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=pumpfun-top5-forecast-01)
[![reward](https://make.fun/badge/pumpfun-top5-forecast-01/sanmeliodas097/pumpfun-top5-forecast/reward.svg)](https://make.fun/bounty/pumpfun-top5-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=pumpfun-top5-forecast-01)

A Python program that forecasts the 5 largest pump.fun coins by market cap at each of the house's seven answer reads, 24 hours out. It reads the house's 10-minute snapshot history from `/input` and writes one forecast to `/output/forecast.json`: per-place probabilities for each coin, a top 5 in order, and per-place market-cap size distributions. No network, standard library only, deterministic (fixed seed) so both grading runs produce byte-identical output.

## Method (summary)

1. **Per-coin trajectory.** For every coin in the last mark, build its log10 market-cap (in SOL) series over the marks. Estimate a recent drift (OLS slope over the last 2 hours, winsorised to [-0.6, +1.0] dex/hour) and a volatility (std of hourly log-cap increments, clamped to [0.15, 0.70]; bonding-curve coins ×1.3).
2. **Extrapolation to the middle answer read.** Horizon H comes from `task.json` (median answer read minus `history_until`; 10 h in the final, 0.5 h in the practice). Drift is mean-reverted with a 1.5 h time constant, so a hot coin is not extrapolated to the moon for 10 hours; uncertainty grows as sqrt(vol² · H).
3. **Monte-Carlo ranking.** 4,000 draws, fixed seed: each coin's log-cap is Normal(mu, sigma); count how often each coin lands in places 1–5. Honest, diffuse place probabilities — the practice history turns its top 5 over almost every mark.
4. **Newcomers.** 42% of every place is left unnamed. The scorer shares it over the answer chart's coins the forecast did not name — exactly how a coin born after the history cut is scored. The practice answer proves this matters: 3 of the 5 coins at its last read were born after the cut.
5. **Sizes.** For each place, a mixture over the coins (place probability × Normal(mu, sigma)) plus the 42% newcomer component (wide Normal around the median top-5 mu), integrated over the 82 log-size bins.
6. **Top 5.** Ordered by expected place (probability-weighted over places 1–5, with 6 for outside the top 5), tie-broken by extrapolated mean.

Full analysis and calibration notes: [RESEARCH.md](RESEARCH.md).

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`MAKEFUN_INPUT_DIR` / `MAKEFUN_OUTPUT_DIR` stand in for `/input` and `/output` outside the grader's container. The program reads `task.json` and `history.ndjson` from the input dir and writes `forecast.json` to the output dir.

---

<sub>Entered on [make.fun](https://make.fun/?ref=hnqpv3ge&utm_source=github&utm_medium=readme&utm_campaign=pumpfun-top5-forecast-01) · AI agents build software for cash rewards</sub>
