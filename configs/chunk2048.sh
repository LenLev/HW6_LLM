#!/usr/bin/env bash
set -euo pipefail
cd /homework
exec bash serve.sh --max-num-seqs 64 --max-num-batched-tokens 2048
