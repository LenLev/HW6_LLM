#!/usr/bin/env bash
set -euo pipefail
cd /homework
exec bash serve.sh --max-num-seqs 64 --max-num-batched-tokens 2048 --speculative-config '{"model":"RedHatAI/Qwen3-8B-speculator.eagle3","num_speculative_tokens":3,"method":"eagle3"}'
