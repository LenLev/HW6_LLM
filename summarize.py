"""Summarize raw AIPerf request records, excluding warmup."""
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent

def percentile(values, q):
    values = sorted(values)
    position = (len(values) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)

def summarize(path):
    records = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # A running export may end with an incomplete line.
        if row["metadata"].get("benchmark_phase") == "warmup":
            continue
        records.append(row)
    valid = [r for r in records if "request_latency" in r.get("metrics", {})]
    if not valid:
        return None
    def metric(key):
        return [r["metrics"][key]["value"] for r in valid if key in r["metrics"]]
    latencies = metric("request_latency")
    assert all(tokens <= 512 for tokens in metric("usage_completion_tokens"))
    mode, config, rate = path.parents[1].name.split("-")
    starts = [r["metadata"]["request_start_ns"] for r in valid]
    ends = [r["metadata"]["request_end_ns"] for r in valid]
    credits = [r["metadata"]["credit_issued_ns"] for r in valid]
    elapsed = (max(ends) - min(starts)) / 1e9
    delays = [(r["metadata"]["request_start_ns"] - r["metadata"]["credit_issued_ns"]) / 1e6 for r in valid]
    complete = (path.parent/".aiperf_results_ready.json").exists()
    if complete:
        exported = json.loads((path.parent/"profile_export_aiperf.json").read_text())
        assert abs(statistics.mean(latencies) - exported["request_latency"]["avg"]) < 1e-5
        assert abs(percentile(latencies, .9) - exported["request_latency"]["p90"]) < 1e-5
    return dict(mode=mode, config=config, rpm=int(rate.removesuffix("rpm")), complete=complete,
                requests=len(records), success=len(valid), errors=len(records)-len(valid),
                mean_s=statistics.mean(latencies)/1000, p90_s=percentile(latencies, .9)/1000,
                ttft_mean_s=statistics.mean(metric("time_to_first_token"))/1000,
                output_tokens_mean=statistics.mean(metric("usage_completion_tokens")),
                elapsed_s=elapsed, dispatch_span_s=(max(credits)-min(credits))/1e9,
                completed_rpm=len(valid)/elapsed*60, dispatch_delay_p90_ms=percentile(delays, .9))

def collect():
    return [row for path in sorted((ROOT/"results").glob("*/profile/profile_export.jsonl"))
            if (row := summarize(path)) is not None]

if __name__ == "__main__":
    rows = collect()
    for row in rows:
        print(f"{row['mode']:5} {row['config']:10} {row['rpm']:4} RPM  n={row['success']:5} errors={row['errors']} mean={row['mean_s']:.3f}s p90={row['p90_s']:.3f}s span={row['dispatch_span_s']:.1f}s delay_p90={row['dispatch_delay_p90_ms']:.1f}ms")
    if rows:
        with (ROOT/"metrics.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (ROOT/"metrics.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
