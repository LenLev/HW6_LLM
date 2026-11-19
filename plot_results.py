"""Create figures from measured AIPerf records (run after summarize.py)."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--best", required=True)
args = parser.parse_args()
rows = json.loads((ROOT/"metrics.json").read_text())
out = ROOT/"figures"
out.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12})

def load(config):
    return sorted([r for r in rows if r["mode"] == "load" and r["config"] == config], key=lambda r:r["rpm"])

def sweep(config):
    valid_rates = {r["rpm"] for r in rows if r["config"] == "eagle3" and r["mode"] in ("sweep", "fixed") and r["errors"] == 0}
    return sorted([r for r in rows if r["mode"] in ("sweep", "fixed") and r["config"] == config and r["rpm"] in valid_rates and r["errors"] == 0], key=lambda r:r["rpm"])

control, spec = sweep("chunk2048"), sweep("eagle3")
fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.4), constrained_layout=True)
for data, label in [(control, "Без спекдека"), (spec, "EAGLE-3, 3 токена")]:
    axes[0].plot([r["rpm"] for r in data], [r["p90_s"] for r in data], "o-", label=label)
axes[0].set(xlabel="Нагрузка, RPM", ylabel="P90 E2E Latency, с")
axes[0].legend()
paired = [(c["rpm"], c["p90_s"]/s["p90_s"]) for c in control for s in spec if c["rpm"]==s["rpm"]]
axes[1].plot([r[0] for r in paired], [r[1] for r in paired], "o-", color="#157a6e")
axes[1].axhline(1, color="#a83a32", linestyle="--", label="Одинаковая скорость")
axes[1].set(xlabel="Нагрузка, RPM", ylabel="Ускорение по P90, раз")
axes[1].legend()
for ax in axes:
    ax.grid(alpha=.25)
fig.savefig(out/"speculation.png", dpi=180)
plt.close(fig)

tables = ROOT/"tables"
tables.mkdir(exist_ok=True)
def write_table(name, data):
    with (tables/name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)

fixed = [r for r in rows if r["mode"] == "fixed"]
baseline = next(r for r in fixed if r["config"] == "baseline")
write_table("configurations.csv", [dict(config=r["config"],
    command=next(line for line in (ROOT/"configs"/f"{r['config']}.sh").read_text().splitlines() if line.startswith("exec ")),
    mean_s=r["mean_s"], p90_s=r["p90_s"], speedup=baseline["mean_s"]/r["mean_s"], errors=r["errors"])
    for r in fixed])
paired_rows = []
for rpm in sorted({r["rpm"] for r in rows if r["mode"] in ("fixed", "sweep")}):
    c = next((r for r in rows if r["config"] == "chunk2048" and r["mode"] in ("fixed", "sweep") and r["rpm"] == rpm), None)
    s = next((r for r in rows if r["config"] == "eagle3" and r["mode"] in ("fixed", "sweep") and r["rpm"] == rpm), None)
    if c and s:
        paired_rows.append(dict(rpm=rpm, control_p90_s=c["p90_s"], eagle3_p90_s=s["p90_s"],
                                control_errors=c["errors"], eagle3_errors=s["errors"],
                                p90_speedup=c["p90_s"]/s["p90_s"] if not c["errors"] and not s["errors"] else "invalid: timeouts"))
write_table("speculation.csv", paired_rows)
write_table("load_test.csv", [dict(rpm=r["rpm"], requests=r["requests"], mean_s=r["mean_s"], p90_s=r["p90_s"],
                                  errors=r["errors"], sla_pass=r["p90_s"]<15 and r["errors"]==0,
                                  dispatch_span_s=r["dispatch_span_s"], drain_included_rpm=r["completed_rpm"])
                            for r in load(args.best)])

data = load(args.best)
fig, ax = plt.subplots(figsize=(8.4, 3.5), constrained_layout=True)
ax.plot([r["rpm"] for r in data], [r["p90_s"] for r in data], "o-", color="#24588b")
ax.axhline(15, linestyle="--", color="#a83a32", label="SLA: P90 < 15 с")
passing = [r for r in data if r["p90_s"] < 15 and r["errors"] == 0]
if passing:
    last = max(passing, key=lambda r:r["rpm"])
    ax.scatter([last["rpm"]], [last["p90_s"]], s=85, color="#157a6e", zorder=4,
               label=f"Максимум из проверенных: {last['rpm']} RPM")
    failing = [r for r in data if r["rpm"] > last["rpm"] and (r["p90_s"] >= 15 or r["errors"])]
    if failing:
        first = min(failing, key=lambda r:r["rpm"])
        ax.scatter([first["rpm"]], [first["p90_s"]], s=85, color="#a83a32", zorder=4,
                   label=f"Нарушение SLA: {first['rpm']} RPM")
ax.set(xlabel="Нагрузка, RPM", ylabel="P90 E2E Latency, с")
ax.grid(alpha=.25)
ax.legend()
fig.savefig(out/"capacity.png", dpi=180)
plt.close(fig)
