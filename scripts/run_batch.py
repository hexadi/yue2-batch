#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time


def run(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["runpodctl", *args],
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one YuE2 batch on an ephemeral RunPod GPU Pod.")
    parser.add_argument("--manifest-url", required=True)
    parser.add_argument("--image", default="ghcr.io/hexadi/yue2-batch:latest")
    parser.add_argument("--gpu-id", default="NVIDIA GeForce RTX 4090")
    parser.add_argument("--cloud-type", choices=("COMMUNITY", "SECURE"), default="COMMUNITY")
    parser.add_argument("--container-disk-gb", type=int, default=30)
    parser.add_argument("--timeout-minutes", type=int, default=60)
    parser.add_argument("--name", default="yue2-batch")
    parser.add_argument("--registry-auth-id", default=None)
    parser.add_argument("--keep-pod", action="store_true")
    args = parser.parse_args()

    env = {
        "BATCH_MANIFEST_URL": args.manifest_url,
        "HF_HOME": "/workspace/huggingface",
        "BATCH_OUTPUT_DIR": "/workspace/yue2-batch-output",
        "YUE2_MODEL": "m-a-p/YuE2-3B",
        "YUE2_VAE": "m-a-p/YuE2-Vae",
        "YUE2_DEVICE": "cuda",
        "YUE2_MEMORY_BUDGET_GIB": "24",
        "YUE2_BACKEND": "torch",
        "YUE2_QUANTIZATION": "none",
        "YUE2_OFFLOAD_AR": "false",
        "BATCH_CONTINUE_ON_ERROR": "true",
        "BATCH_MAX_JOBS": "50",
    }

    pod_id = None
    completed = False
    try:
        create_args = [
            "pod", "create",
            "--image", args.image,
            "--gpu-id", args.gpu_id,
            "--gpu-count", "1",
            "--cloud-type", args.cloud_type,
            "--container-disk-in-gb", str(args.container_disk_gb),
            "--min-cuda-version", "12.8",
            "--name", args.name,
            "--ssh=false",
            "--env", json.dumps(env, separators=(",", ":")),
        ]
        if args.registry_auth_id:
            create_args += ["--registry-auth-id", args.registry_auth_id]
        raw = run(*create_args)
        pod = json.loads(raw)
        pod_id = pod["id"]
        print(json.dumps({"pod_id": pod_id, "status": "created"}), flush=True)

        deadline = time.time() + args.timeout_minutes * 60
        last_log = ""
        while time.time() < deadline:
            logs = run(
                "pod", "logs", pod_id,
                "--tail", "500",
                "--max-wait", "5s",
                check=False,
            )
            if logs and logs != last_log:
                print(logs, flush=True)
                last_log = logs
            if "BATCH_COMPLETE " in logs:
                completed = True
                break

            details = run("pod", "get", pod_id, check=False)
            if details:
                try:
                    state = json.loads(details).get("desiredStatus")
                    if state in {"EXITED", "TERMINATED"} and "BATCH_COMPLETE " not in logs:
                        raise RuntimeError(f"pod exited before batch completion: {state}")
                except json.JSONDecodeError:
                    pass
            time.sleep(5)

        if not completed:
            raise TimeoutError(f"batch did not finish within {args.timeout_minutes} minutes")
        return 0
    finally:
        if pod_id:
            print(json.dumps({"pod_id": pod_id, "action": "stop"}), flush=True)
            run("pod", "stop", pod_id, check=False)
            if not args.keep_pod:
                print(json.dumps({"pod_id": pod_id, "action": "delete"}), flush=True)
                run("pod", "delete", pod_id, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
