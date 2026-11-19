#!/usr/bin/env bash
# Same 640 requests at every rate: avoids changing the workload mix.
set -euo pipefail
cd "$(dirname "$0")"
rpm="${1:-120}"
url="${URL:-http://localhost:8000}"
output="${2:-results/sweep-${rpm}rpm-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$(dirname "$output")"
mkdir "$output"
trap 'curl -fsS -X POST "$url/reset_prefix_cache" >/dev/null' EXIT
curl -fsS -X POST "$url/reset_prefix_cache" >/dev/null
rps="$(awk -v rpm="$rpm" 'BEGIN { print rpm / 60 }')"
aiperf profile --url "$url" --model Qwen/Qwen3-8B \
  --endpoint-type chat --custom-dataset-type raw_payload \
  --input-file data/requests.jsonl --dataset-sampling-strategy sequential \
  --warmup-request-count 40 --warmup-concurrency 8 \
  --request-count "$(wc -l < data/requests.jsonl)" \
  --request-rate "$rps" --arrival-pattern constant \
  --streaming --request-timeout-seconds 120 \
  --export-outputs-json --output-artifact-dir "$output/profile"
