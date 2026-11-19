"""Run on the VM host. Only controls our isolated GPU 1 container."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
CONTAINER = "hw6-lena-20261119"
GPU = "GPU-473487c4-3598-2b12-8c6d-54d5f4a0c0b6"
SHA = "67c48379e5ae2608f7ca08650fd346facdc01f766a3e8eecea6459d7cec00ebc"

def docker(*args, **kwargs):
    return subprocess.run(["sudo", "-n", "docker", *args], check=True, **kwargs)

def log(message):
    line = f"{datetime.datetime.now(datetime.timezone.utc).isoformat()} {message}"
    print(line, flush=True)
    with (ROOT / "progress.log").open("a") as stream:
        stream.write(line + "\n")

def check_data():
    data = (ROOT / "data/requests.jsonl").read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA
    rows = [json.loads(line) for line in data.splitlines()]
    assert len(rows) == 640
    for row in rows:
        assert row["model"] == "Qwen/Qwen3-8B"
        assert row["max_tokens"] == 512 and row["temperature"] == 0 and row["seed"] == 42
        assert row["chat_template_kwargs"]["enable_thinking"] is False

def guard_gpu():
    own = docker("top", CONTAINER, "-eo", "pid", capture_output=True, text=True).stdout.splitlines()[1:]
    own = {line.strip() for line in own}
    active = subprocess.check_output(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"], text=True)
    for line in active.splitlines():
        gpu, pid = [value.strip() for value in line.split(",")]
        if gpu == GPU and pid not in own:
            raise RuntimeError(f"Physical GPU 1 has another process: {pid}")

def start(config):
    guard_gpu()
    log(f"START {config}")
    previous_log = ROOT / "logs" / f"{config}-server.log"
    if previous_log.exists():
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(previous_log, ROOT / "logs" / f"{config}-server-before-{stamp}.log")
    docker("restart", "-t", "3", CONTAINER, stdout=subprocess.DEVNULL)
    docker("exec", "-d", CONTAINER, "bash", "-c",
           f"exec bash configs/{config}.sh > logs/{config}-server.log 2>&1")
    ready(config)

def ready(config):
    for _ in range(240):
        try:
            with urllib.request.urlopen("http://127.0.0.1:18061/health", timeout=3) as response:
                if response.status == 200:
                    log(f"READY {config}")
                    return
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError(f"Server failed to start: {config}")

def measure(config, rpm, mode):
    check_data()
    guard_gpu()
    name = f"{mode}-{config}-{rpm}rpm"
    output = ROOT / "results" / name
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite {output}")
    log(f"MEASURE {name}")
    with urllib.request.urlopen("http://127.0.0.1:18061/server_info?config_format=json") as response:
        (ROOT / "logs" / f"{config}-server-info.json").write_bytes(response.read())
    command = ["bash", "benchmark.sh", f"results/{name}"] if mode == "fixed" else ["bash", "sweep.sh" if mode == "sweep" else "load_test.sh", str(rpm), f"results/{name}"]
    with (ROOT / "logs" / f"{name}.log").open("w") as stream:
        process = subprocess.Popen(["sudo", "-n", "docker", "exec", CONTAINER, *command], stdout=stream, stderr=subprocess.STDOUT)
        while process.poll() is None:
            time.sleep(10)
            try:
                guard_gpu()
            except Exception:
                docker("stop", "-t", "3", CONTAINER)
                process.wait()
                raise
        if process.returncode:
            raise RuntimeError(f"Benchmark failed: {name}; exit={process.returncode}")
    check_data()
    with urllib.request.urlopen("http://127.0.0.1:18061/metrics") as response:
        (output / "server_metrics.txt").write_bytes(response.read())
    subprocess.run(["nvidia-smi", "-i", "1", "-q"], stdout=(output / "gpu.txt").open("w"), check=True)
    log(f"DONE {name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", nargs="+", required=True)
    parser.add_argument("--rpms", nargs="+", type=int, default=[120])
    parser.add_argument("--mode", choices=["fixed", "sweep", "load"], default="fixed")
    parser.add_argument("--reuse-server", action="store_true")
    args = parser.parse_args()
    check_data()
    for index, config in enumerate(args.configs):
        if not (args.reuse_server and index == 0):
            start(config)
        else:
            ready(config)
        for rpm in args.rpms:
            if args.mode == "fixed" and rpm != 120:
                raise ValueError("The provided benchmark.sh uses 120 RPM")
            measure(config, rpm, args.mode)
    log("BATCH COMPLETE")
