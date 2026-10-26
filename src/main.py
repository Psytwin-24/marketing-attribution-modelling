"""Multi-touch attribution with a Markov removal effect, on real user-journey data.

Source data is a published customer-journey file whose touchpoints are ON-SITE
page views (Homepage, Pricing, Courses, Checkout, Coupon...), not paid-media
channels. That is stated plainly here and in the README: the removal effect is
computed over the paths that actually exist in the file.

Conversion is defined as a path that reaches a terminal value step:
Checkout or Coupon.

Method
------
Absorption probability at the converted state is solved exactly as a linear
system, p[s] = sum_t P(s->t) p[t] with p[CONVERTED]=1 and p[DROP]=0. The removal
effect for a step is 1 - p(without it)/p(baseline), normalised into a credit
share, and compared with first-touch, last-touch, linear and time-decay.
"""
import json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERMINAL = {"Checkout", "Coupon"}
START, CONVERTED, DROP = "START", "<CONVERTED>", "<DROP>"

df = pd.read_csv(os.path.join(ROOT, "data/journeys.csv"))
paths = (df["user_journey"].astype(str)
         .apply(lambda s: [t.strip() for t in s.split("-") if t.strip()]))
converted = paths.apply(lambda p: int(bool(p) and p[-1] in TERMINAL))
paths = pd.Series(paths.values)

CH = sorted({c for p in paths for c in p})


def edge_counts(remove=None):
    """Transition counts. Removing a step routes any path touching it to DROP."""
    edges = {}
    for p, c in zip(paths, converted):
        seq = [x for x in p if x != START]
        if remove is not None:
            if remove in seq:
                seq = seq[: seq.index(remove)]
                edges.setdefault(seq[-1] if seq else START, {})
                k = seq[-1] if seq else START
                edges[k][DROP] = edges[k].get(DROP, 0) + 1
                continue
        tail = CONVERTED if c else DROP
        prev = START
        for node in seq + [tail]:
            edges.setdefault(prev, {})
            edges[prev][node] = edges[prev].get(node, 0) + 1
            if node in (CONVERTED, DROP):
                break
            prev = node
    return edges


def prob_conv(edges):
    transient = [s for s in edges if s not in (CONVERTED, DROP)]
    if START not in transient:
        transient = [START] + transient
    idx = {t: i for i, t in enumerate(transient)}
    A = np.eye(len(transient)); b = np.zeros(len(transient))
    for s in transient:
        outs = edges.get(s, {}); tot = sum(outs.values())
        if not tot:
            continue
        for t, w in outs.items():
            if t == CONVERTED:
                b[idx[s]] += w / tot
            elif t == DROP:
                pass
            elif t in idx:
                A[idx[s], idx[t]] -= w / tot
    return float(np.linalg.solve(A, b)[idx[START]])


def rule_based(kind):
    w = {}
    for p, c in zip(paths, converted):
        if not c:
            continue
        if kind == "first":
            w[p[0]] = w.get(p[0], 0) + 1
        elif kind == "last":
            v = [x for x in p if x in TERMINAL] or [p[-1]]
            w[v[0]] = w.get(v[0], 0) + 1
        elif kind == "linear":
            for t in p:
                w[t] = w.get(t, 0) + 1 / len(p)
        elif kind == "time_decay":
            half = 0.5
            raw = [half ** (len(p) - 1 - i) for i in range(len(p))]
            tot = sum(raw)
            for t, r in zip(p, raw):
                w[t] = w.get(t, 0) + r / tot
    tot = sum(w.values()) or 1
    return {k: round(v / tot, 4) for k, v in sorted(w.items(), key=lambda x: -x[1])}


base = prob_conv(edge_counts())
removal = {}
for ch in CH:
    pw = prob_conv(edge_counts(remove=ch))
    removal[ch] = max(1.0 - pw / base, 0.0) if base > 0 else 0.0
tot = sum(removal.values()) or 1.0
markov = {k: round(v / tot, 4) for k, v in sorted(removal.items(), key=lambda x: -x[1])}

shares = {"first_touch": rule_based("first"), "last_touch": rule_based("last"),
          "linear": rule_based("linear"), "time_decay": rule_based("time_decay"),
          "markov_removal": markov}
order = sorted(CH, key=lambda c: -markov.get(c, 0))
tbl = [[c] + [shares[m].get(c, 0) for m in shares] for c in order]
ft = np.array([shares["first_touch"].get(c, 0) for c in order])
mt = np.array([markov.get(c, 0) for c in order])
tv = np.array([shares["time_decay"].get(c, 0) for c in order])

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
x = np.arange(len(order)); wd = 0.16
for i, k in enumerate(shares):
    axes[0].bar(x + i * wd, [shares[k].get(c, 0) for c in order], wd, label=k.replace("_", " "))
axes[0].set_xticks(x + wd * 2); axes[0].set_xticklabels(order, rotation=60, fontsize=7, ha="right")
axes[0].legend(fontsize=7); axes[0].set_ylabel("credit share"); axes[0].set_title("Five models, one dataset")
axes[1].bar(order, mt - ft, color=np.where(mt - ft >= 0, "tab:green", "tab:red"))
axes[1].axhline(0, color="k", lw=.8); axes[1].set_xticklabels(order, rotation=60, fontsize=7, ha="right")
axes[1].set_ylabel("markov minus first-touch"); axes[1].set_title("First-touch misallocation")
plt.tight_layout(); plt.savefig(os.path.join(ROOT, "figures/attribution.png"), dpi=110); plt.close()

metrics = {"results": {"sessions": int(len(df)),
                       "unique_paths": int(df["user_journey"].nunique()),
                       "converted_sessions": int(sum(converted)),
                       "conversion_rate": round(float(np.mean(converted)), 4),
                       "distinct_steps": int(len(CH)),
                       "absorption_prob_baseline": round(base, 4),
                       "top_step_by_removal_effect": max(markov, key=markov.get),
                       "first_touch_vs_markov_total_variation": round(float(np.abs(mt - ft).sum() / 2), 4),
                       "time_decay_vs_markov_total_variation": round(float(np.abs(tv - mt).sum() / 2), 4),
                       "touchpoint_granularity": "on-site page steps, not media channels"},
           "table": {"title": "Credit share by model (each column sums to 1)",
                     "headers": ["step", "first touch", "last touch", "linear", "time decay", "markov removal"],
                     "rows": tbl},
           "figures": [["attribution.png", "The models disagree, and the disagreement is the finding"]]}
json.dump(metrics, open(os.path.join(ROOT, "metrics.json"), "w"), indent=1)
print(json.dumps(metrics["results"]))
