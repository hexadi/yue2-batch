from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("YUE2_MODEL", "m-a-p/YuE2-3B")
    vae: str = os.getenv("YUE2_VAE", "m-a-p/YuE2-Vae")
    model_revision: str | None = os.getenv("YUE2_MODEL_REVISION") or None
    vae_revision: str | None = os.getenv("YUE2_VAE_REVISION") or None
    device: str = os.getenv("YUE2_DEVICE", "cuda")
    memory_budget_gib: float = float(os.getenv("YUE2_MEMORY_BUDGET_GIB", "24"))
    backend: str = os.getenv("YUE2_BACKEND", "torch")
    quantization: str = os.getenv("YUE2_QUANTIZATION", "none")
    offload_ar: bool = _bool("YUE2_OFFLOAD_AR", False)
    local_files_only: bool = _bool("YUE2_LOCAL_FILES_ONLY", False)
    hf_token: str | None = os.getenv("HF_TOKEN") or None
    hf_cache_dir: str = os.getenv("HF_HOME", "/root/.cache/huggingface")

    output_dir: str = os.getenv("BATCH_OUTPUT_DIR", "/workspace/yue2-batch-output")
    manifest_url: str | None = os.getenv("BATCH_MANIFEST_URL") or None
    manifest_json: str | None = os.getenv("BATCH_MANIFEST_JSON") or None
    manifest_file: str = os.getenv("BATCH_MANIFEST_FILE", "/workspace/batch.json")
    max_jobs: int = int(os.getenv("BATCH_MAX_JOBS", "50"))
    continue_on_error: bool = _bool("BATCH_CONTINUE_ON_ERROR", True)
    cleanup_after_upload: bool = _bool("BATCH_CLEANUP_AFTER_UPLOAD", False)
    manifest_connect_timeout: float = float(os.getenv("BATCH_MANIFEST_CONNECT_TIMEOUT", "10"))
    manifest_read_timeout: float = float(os.getenv("BATCH_MANIFEST_READ_TIMEOUT", "60"))

    s3_bucket: str | None = os.getenv("S3_BUCKET") or None
    s3_endpoint_url: str | None = os.getenv("S3_ENDPOINT_URL") or None
    s3_region: str = os.getenv("S3_REGION", "auto")
    s3_access_key_id: str | None = os.getenv("S3_ACCESS_KEY_ID") or None
    s3_secret_access_key: str | None = os.getenv("S3_SECRET_ACCESS_KEY") or None
    s3_public_base_url: str | None = os.getenv("S3_PUBLIC_BASE_URL") or None
    s3_prefix: str = os.getenv("S3_PREFIX", "yue2/batches").strip("/")
    s3_url_ttl_seconds: int = int(os.getenv("S3_URL_TTL_SECONDS", "86400"))
    upload_all_artifacts: bool = _bool("YUE2_UPLOAD_ALL_ARTIFACTS", False)

    def prepare(self) -> None:
        Path(self.hf_cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
