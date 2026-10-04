from __future__ import annotations

import ipaddress
import json
import re
import shutil
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from config import settings
from engine import engine, validate_request
from storage import publish_job, publish_summary

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,179}$")
_REDIRECTS = {301, 302, 303, 307, 308}


def _safe_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"{field} must be a filename-safe identifier")
    return value


def _validate_public_https(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("BATCH_MANIFEST_URL must be a public HTTPS URL")
    port = parsed.port or 443
    for info in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError("BATCH_MANIFEST_URL resolves to a non-public address")
    return url


def _download_json(url: str) -> dict:
    current = _validate_public_https(url)
    session = requests.Session()
    for _ in range(6):
        response = session.get(
            current,
            allow_redirects=False,
            timeout=(settings.manifest_connect_timeout, settings.manifest_read_timeout),
            headers={"User-Agent": "yue2-batch/0.1"},
        )
        if response.status_code in _REDIRECTS:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ValueError("manifest redirect has no Location")
            current = _validate_public_https(urljoin(current, location))
            continue
        response.raise_for_status()
        if len(response.content) > 5 * 1024 * 1024:
            raise ValueError("batch manifest exceeds 5 MiB")
        return response.json()
    raise ValueError("too many manifest redirects")


def load_manifest() -> dict:
    if settings.manifest_json:
        return json.loads(settings.manifest_json)
    if settings.manifest_url:
        return _download_json(settings.manifest_url)
    path = Path(settings.manifest_file)
    if not path.is_file():
        raise FileNotFoundError(
            "provide BATCH_MANIFEST_JSON, BATCH_MANIFEST_URL, or BATCH_MANIFEST_FILE"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(data: dict) -> tuple[str, list[dict]]:
    if not isinstance(data, dict):
        raise ValueError("batch manifest must be a JSON object")
    unknown = set(data) - {"batch_id", "jobs"}
    if unknown:
        raise ValueError(f"unsupported manifest fields: {sorted(unknown)}")
    batch_id = _safe_id(data.get("batch_id", "batch"), "batch_id")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("jobs must be a non-empty array")
    if len(jobs) > settings.max_jobs:
        raise ValueError(f"batch exceeds BATCH_MAX_JOBS={settings.max_jobs}")

    seen: set[str] = set()
    clean: list[dict] = []
    for index, raw in enumerate(jobs):
        job = validate_request(raw)
        job_id = _safe_id(str(job.get("id") or f"song-{index + 1:03d}"), "job id")
        if job_id in seen:
            raise ValueError(f"duplicate job id: {job_id}")
        seen.add(job_id)
        job["id"] = job_id
        clean.append(job)
    return batch_id, clean


def main() -> int:
    settings.prepare()
    manifest = load_manifest()
    batch_id, jobs = validate_manifest(manifest)
    batch_root = Path(settings.output_dir) / batch_id
    batch_root.mkdir(parents=True, exist_ok=True)

    started = time.time()
    print(f"BATCH_START batch_id={batch_id} jobs={len(jobs)}", flush=True)
    print("Loading YuE2 once for the whole batch...", flush=True)
    engine.load()
    print("YuE2 loaded.", flush=True)

    results = []
    failed = 0
    for index, job in enumerate(jobs, start=1):
        job_id = job["id"]
        job_dir = batch_root / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
        job_dir.mkdir(parents=True)

        t0 = time.time()
        print(f"JOB_START {index}/{len(jobs)} id={job_id}", flush=True)
        try:
            result = engine.generate(job, job_dir)
            artifacts = publish_job(job_dir, batch_id, job_id)
            elapsed = time.time() - t0
            item = {
                "id": job_id,
                "status": "complete",
                "audio_seconds": result.get("audio_seconds"),
                "truncated": result.get("truncated", {}),
                "execution_seconds": elapsed,
                "timing": result.get("timing", {}),
                "artifacts": artifacts,
            }
            print(
                f"JOB_COMPLETE {index}/{len(jobs)} id={job_id} "
                f"audio_seconds={item['audio_seconds']} execution_seconds={elapsed:.3f}",
                flush=True,
            )
            if settings.s3_bucket and settings.cleanup_after_upload:
                shutil.rmtree(job_dir, ignore_errors=True)
        except Exception as exc:
            failed += 1
            elapsed = time.time() - t0
            item = {
                "id": job_id,
                "status": "failed",
                "execution_seconds": elapsed,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"JOB_FAILED {index}/{len(jobs)} id={job_id} error={item['error']}", flush=True)
            if not settings.continue_on_error:
                results.append(item)
                break
        results.append(item)

    summary = {
        "batch_id": batch_id,
        "status": "complete" if failed == 0 else "partial_failure",
        "jobs_requested": len(jobs),
        "jobs_finished": len(results),
        "jobs_failed": failed,
        "wall_seconds": time.time() - started,
        "results": results,
    }
    summary_path = batch_root / "batch-result.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_artifact"] = publish_summary(summary_path, batch_id)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("BATCH_RESULT " + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    print(f"BATCH_COMPLETE batch_id={batch_id} failed={failed}", flush=True)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
