#!/usr/bin/env python3
"""Pump.fun top-5 market-cap forecast (make.fun pumpfun-top5-forecast-01).

Reads the house's 10-minute snapshot history from $MAKEFUN_INPUT_DIR (or
/input) and writes one forecast to $MAKEFUN_OUTPUT_DIR (or /output).

Method (all from the history alone; no network, no randomness but a fixed
seed, so the two grading runs produce byte-identical output):

1.  For every coin in the last mark, build its log10 market-cap (in SOL)
    series over the marks. Estimate a recent drift (OLS slope of log-cap
    vs time over the last 2 hours, winsorised) and a volatility (std of
    hourly log-cap increments, clamped).
2.  Extrapolate each coin to the middle answer read (H hours after the
    history ends, read from task.json): drift is mean-reverted with a
    1.5 h time constant, so a hot coin cannot be extrapolated to the moon
    for 10 hours; uncertainty grows as sqrt(vol^2 * H).
3.  Monte-Carlo the ranking at that horizon (fixed seed): each coin's
    log-cap is Normal(mu, sigma); count how often each coin lands in
    places 1..5. That gives honest, diffuse place probabilities -- the
    practice history shows the top 5 turning over almost every mark, and
    3 of the 5 coins at the practice's last answer read were born after
    its history ended.
4.  Leave 42% of every place unnamed: the scorer shares it over the
    answer chart's coins the forecast did not name, which is exactly how
    a coin born after the cut is scored. The remaining 58% is split over
    the Monte-Carlo place probabilities.
5.  Sizes: for each place, a mixture over the coins (their place
    probability times their Normal(mu, sigma)) plus the 42% newcomer
    component, a wide Normal around the median top-5 mu, integrated over
    the 82 log-size bins from task.json.
6.  top5 is the five coins with the largest extrapolated mu.

Standard library only.
"""

import json
import math
import os
import random
from datetime import datetime, timezone

SEED = 20261112
N_DRAWS = 4000
UNNAMED = 0.42          # share of each place left for coins born after the cut
TAU_H = 1.5             # mean-reversion time constant of the drift, hours
SLOPE_LO, SLOPE_HI = -0.6, 1.0   # winsorised drift, dex per hour
VOL_LO, VOL_HI = 0.15, 0.70      # per-hour log-cap volatility, dex
CURVE_VOL_MULT = 1.3    # coins still on the bonding curve are wilder
SIGMA0 = 0.08           # base uncertainty, dex
NEWCOMER_SIGMA = 0.8    # width of the newcomer size component, dex
MIN_P = 0.001           # smallest named place probability kept
MICRO = 1_000_000


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def logcap_sol(market_cap_lamports):
    return math.log10(int(market_cap_lamports)) - 9.0


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def ols_slope(xs, ys):
    """Least-squares slope of ys on xs (both lists of floats)."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return 0.0
    return num / den


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

    with open(os.path.join(input_dir, "task.json")) as f:
        task = json.load(f)
    places = int(task["places"])
    edges = [float(e) for e in task["size"]["edges"]]
    history_until = parse_time(task["history_until"])
    reads = [parse_time(r) for r in task["reads"]]
    horizon_h = (sorted(reads)[len(reads) // 2] - history_until) / 3600.0
    if horizon_h <= 0:
        horizon_h = 1.0

    marks = []
    with open(os.path.join(input_dir, "history.ndjson")) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            if m.get("ok") is True and isinstance(m.get("rows"), list):
                marks.append(m)
    if not marks:
        raise SystemExit("the history holds no ok mark")
    last = marks[-1]
    chart = sorted(last["rows"], key=lambda r: r["rank"])
    if len(chart) < places:
        raise SystemExit(
            "the last mark ranks %d coins, fewer than the %d places"
            % (len(chart), places)
        )

    # Per-coin series: (time_hours, log-cap, venue, complete).
    series = {}
    for m in marks:
        t = (parse_time(m["at"]) - history_until) / 3600.0
        for r in m["rows"]:
            s = series.setdefault(r["mint"], [])
            s.append((t, logcap_sol(r["market_cap_lamports"]),
                      r.get("venue", "curve"), bool(r.get("complete"))))

    # Extrapolated mean and sigma per coin in the last mark.
    coins = []  # (mint, mu, sigma, last_logcap)
    for r in chart:
        mint = r["mint"]
        pts = sorted(series.get(mint, []))
        l0 = logcap_sol(r["market_cap_lamports"])
        t_end = pts[-1][0] if pts else 0.0
        # Drift: OLS slope over the last 2 hours of marks (or all we have).
        win = [(t, v) for (t, v, _, _) in pts if t >= t_end - 2.0]
        if len(win) < 2:
            win = [(t, v) for (t, v, _, _) in pts]
        slope = ols_slope([t for t, _ in win], [v for _, v in win])
        slope = max(SLOPE_LO, min(SLOPE_HI, slope))
        # Volatility: std of hourly log-cap increments.
        incs = []
        for (t0, v0, _, _), (t1, v1, _, _) in zip(pts, pts[1:]):
            dt = t1 - t0
            if dt > 0:
                incs.append((v1 - v0) / math.sqrt(dt))
        if len(incs) >= 2:
            mean_inc = sum(incs) / len(incs)
            var = sum((x - mean_inc) ** 2 for x in incs) / (len(incs) - 1)
            vol = math.sqrt(max(var, 0.0))
        elif incs:
            vol = abs(incs[0])
        else:
            vol = 0.30
        vol = max(VOL_LO, min(VOL_HI, vol))
        if not r.get("complete"):
            vol = min(VOL_HI, vol * CURVE_VOL_MULT)
        drift = slope * TAU_H * (1.0 - math.exp(-horizon_h / TAU_H))
        mu = l0 + drift
        sigma = math.sqrt(SIGMA0 ** 2 + (vol ** 2) * horizon_h)
        coins.append((mint, mu, sigma, l0))

    # Monte-Carlo the ranking at the horizon (fixed seed: deterministic).
    rng = random.Random(SEED)
    n = len(coins)
    mints = [c[0] for c in coins]
    mus = [c[1] for c in coins]
    sigmas = [c[2] for c in coins]
    place_counts = [[0] * n for _ in range(places)]
    for _ in range(N_DRAWS):
        vals = [rng.gauss(mus[i], sigmas[i]) for i in range(n)]
        order = sorted(range(n), key=lambda i: (-vals[i], mints[i]))[:places]
        for k, i in enumerate(order):
            place_counts[k][i] += 1
    # place_probs[k][i] = P(coin i at place k+1), scaled to the named share.
    named_share = 1.0 - UNNAMED
    place_probs = []
    for k in range(places):
        row = [(place_counts[k][i] / N_DRAWS) * named_share for i in range(n)]
        place_probs.append(row)

    probabilities = []
    for k in range(places):
        for i in range(n):
            p = place_probs[k][i]
            if p >= MIN_P:
                probabilities.append(
                    {"mint": mints[i], "place": k + 1, "p": round(p, 6)}
                )

    # top5: order by expected place (probability-weighted over places 1..5,
    # with 6 for "outside the top 5"), tie-broken by extrapolated mean --
    # a steadier coin can outrank a slightly hotter but wilder one.
    raw_probs = [[place_counts[k][i] / N_DRAWS for i in range(n)]
                 for k in range(places)]
    expected_place = []
    for i in range(n):
        p_in = sum(raw_probs[k][i] for k in range(places))
        exp_place = sum((k + 1) * raw_probs[k][i] for k in range(places))
        exp_place += 6.0 * (1.0 - p_in)
        expected_place.append(exp_place)
    by_expected = sorted(range(n),
                         key=lambda i: (expected_place[i], -mus[i], mints[i]))
    top5 = [mints[i] for i in by_expected[:places]]

    # Sizes: mixture of the coins' Normals (by place probability) plus the
    # newcomer component, integrated over the bins.
    top_mu = sorted((mus[i] for i in by_expected[:places]))
    mu_new = top_mu[len(top_mu) // 2]
    sizes = []
    for k in range(places):
        comps = []
        for i in range(n):
            w = place_probs[k][i]
            if w >= MIN_P:
                comps.append((w, mus[i], sigmas[i]))
        comps.append((UNNAMED, mu_new, NEWCOMER_SIGMA))
        for b in range(len(edges) + 1):
            lo = -math.inf if b == 0 else edges[b - 1]
            hi = math.inf if b == len(edges) else edges[b]
            p = 0.0
            for (w, mu, sd) in comps:
                p += w * (norm_cdf((hi - mu) / sd) - norm_cdf((lo - mu) / sd))
            u = math.floor(p * MICRO)
            if u > 0:
                sizes.append({"place": k + 1, "bin": b, "p": u / MICRO})

    forecast = {"probabilities": probabilities, "top5": top5, "sizes": sizes}
    out_path = os.path.join(output_dir, task["output"])
    os.makedirs(output_dir, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json.dumps(forecast) + "\n")


if __name__ == "__main__":
    main()
