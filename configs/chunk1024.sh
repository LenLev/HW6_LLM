#!/usr/bin/env bash
set -euo pipefail
cd /homework
exec bash serve.sh --max-num-seqs 32 --max-num-batched-tokens 1024
