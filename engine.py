from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from config import settings

_ALLOWED = {"style", "tags", "lyrics", "cot", "seed", "abc", "cfg_scale", "id", "abc_sampling", "semantic_sampling"}
_MODES = {"full", "melody", "off"}
_SAMPLING_FIELDS = {"temperature", "top_p", "top_k", "repetition_penalty", "penalty_window", "min_tokens", "max_tokens"}


def validate_request(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("job must be a JSON object")
    unknown = set(data) - _ALLOWED
    if unknown:
        raise ValueError(f"unsupported job fields: {sorted(unknown)}")

    style, tags = data.get("style"), data.get("tags")
    if style is None and tags is None:
        raise ValueError("style is required")
    if style is not None and tags is not None and style != tags:
        raise ValueError("style and tags are aliases and cannot disagree")
    if not isinstance(data.get("lyrics"), str):
        raise ValueError("lyrics must be a string")

    mode = data.get("cot", "full")
    if mode not in _MODES:
        raise ValueError("cot must be one of: full, melody, off")
    if data.get("abc") is not None and mode == "off":
        raise ValueError("abc requires cot=full or cot=melody")

    for key in ("abc_sampling", "semantic_sampling"):
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise ValueError(f"{key} must be a JSON object")
        unknown_sampling = set(value) - _SAMPLING_FIELDS
        if unknown_sampling:
            raise ValueError(f"unsupported {key} fields: {sorted(unknown_sampling)}")

    clean = {k: v for k, v in data.items() if v is not None}
    clean.setdefault("cot", "full")
    return clean


class YuE2Engine:
    def __init__(self) -> None:
        self._pipe = None
        self._load_lock = threading.Lock()

    def load(self):
        if self._pipe is not None:
            return self._pipe
        with self._load_lock:
            if self._pipe is not None:
                return self._pipe
            from yue2 import YuE2Pipeline

            settings.prepare()
            self._pipe = YuE2Pipeline.from_pretrained(
                settings.model,
                vae=settings.vae,
                revision=settings.model_revision,
                vae_revision=settings.vae_revision,
                device=settings.device,
                memory_budget_gib=settings.memory_budget_gib,
                backend=settings.backend,
                quantization=settings.quantization,
                offload_ar=settings.offload_ar,
                local_files_only=settings.local_files_only,
                token=settings.hf_token,
                cache_dir=settings.hf_cache_dir,
                progress=True,
            )
        return self._pipe

    def generate(self, data: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        pipe = self.load()
        request = validate_request(data)
        song = pipe(**request)
        return song.save_artifacts(output_dir)


engine = YuE2Engine()
