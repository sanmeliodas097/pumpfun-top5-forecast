# Research notes — pumpfun-top5-forecast-01

All figures below are from data I actually read on 2026-11-12 (UTC times).
The entry program itself uses only the history the grader hands it; this
file records why its parameters are what they are.

## 1. The practice history (kit `input/`)

- 6 marks, t0 2026-11-11T20:00Z, last mark 20:50Z; 454 distinct coins seen.
- Eligible coins grew 235 → 1,434 across the marks; graduated 1 → 17.
- Last mark's top 5 (all graduated pool coins, 1,912–3,638 SOL):
  AIB, DeepSeek, CHAT, Google, Claude.
- Top-5 membership turned over almost every 10-minute mark:
  mark 1: Claude, CHAD, Squirrel, POLYCAT, PLOTS; mark 3: Google,
  DeepSeek, Claude, GTA 6, GTA 6 Coin; mark 5: AIB, DeepSeek, CHAT,
  Google, Claude.
- Biggest log-cap movers over the 50 minutes: +0.59 dex (SELONMUSK) to
  −0.88 dex (nihao). Volatility is extreme even among leaders.
- The practice answer's last read (given in the rules) was Max, MIHAO VI,
  Google, NIHAONOON, HAMSTER — only Google and MIHAO VI (rank 7 at the
  cut) were in the history at all. **3 of the 5 were born after the
  history ended.** The rules add that 3 of the 9 coins holding a top-5
  place at any of its seven reads were born after the cut.

Lesson: persistence is weak, and post-cut coins take a large share of
top-5 slots. A forecast that bets everything on the last mark's order
(the house baseline) scores −40.41 on the practice; the even spread
scores −45.06. Honest diffuse probabilities plus a large unnamed share
for newcomers are worth more than a confident point forecast.

## 2. Live snapshot (DexScreener, 2026-11-12 ~05:22Z)

Fresh pump.fun mints minutes old, by market cap:

| coin | age | market cap |
| --- | --- | --- |
| GABOON | ~1 h | $149,077 |
| DihcityCoin | ~25 min | $6,765 |
| ling | ~1 h | $7,706 |
| MHI6900 | ~10 min | $3,655 |
| would | ~50 min | $1,634 |

A coin can reach ~200 SOL within an hour of launch. That is why the
forecast leaves 42% of every place unnamed: a coin born after the cut
has real top-5 chances, and the scorer can only credit it through the
unnamed share.

## 3. Calibration choices in `main.py`

- **Horizon H** is read from `task.json` (median answer read minus
  `history_until`): 10 h in the final, 0.5 h in the practice. The model
  adapts; nothing about the final's times is hardcoded.
- **Drift** is the OLS slope of log-cap over the last 2 h, winsorised to
  [−0.6, +1.0] dex/h, then mean-reverted with a 1.5 h time constant:
  a +1 dex/h coin gains at most +1.5 dex over the horizon. Without the
  mean reversion, a 10 h extrapolation of a hot coin would be absurd.
- **Volatility** is the std of hourly log-cap increments, clamped to
  [0.15, 0.70] dex; bonding-curve (incomplete) coins ×1.3. Sigma at the
  horizon is sqrt(0.08² + vol²·H) — about 0.95 dex at H = 10 h for a
  typical coin, which is honest for a 13-hour gap.
- **Unnamed share 0.42** per place: the practice's post-cut share was
  3/5 at the last read; the final's gap is 7–13 h (vs 1–2 h in the
  practice), so newcomers should take at least as large a share.
- **Monte-Carlo ranking**, 4,000 draws, fixed seed: place probabilities
  come from the overlap of the coins' forecast distributions, not from
  a point ranking. Two runs are byte-identical (verified).
- **Top 5** is ordered by expected place, not by extrapolated mean, so
  a steadier coin can outrank a slightly hotter but wilder one.

## 4. Local validation

- Ran on the kit's practice input: valid `forecast.json` (68 probability
  rows, 410 size rows, 5 distinct top-5 mints, 22,325 bytes), 0.66 s.
- Order score on the practice's known last answer read: **−21.49**
  (house baseline on the same read: −23.20; even spread: −23.03).
  Top-5 agreement on that read: 8/25 (baseline's top 5 shares the
  same #1 coin but orders the rest by last-mark rank).
- Determinism: two runs byte-identical.
- Synthetic 66-mark history (practice pattern repeated): runs in ~1 s,
  valid output — the final's longer history is no problem.
- Sizes sum to ≈0.999 per place (6-decimal floor rounding); place
  probabilities sum to ≈0.579 per place (0.58 named share, minus rows
  below the 0.001 keep threshold).
