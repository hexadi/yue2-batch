import pytest

from batch import validate_manifest
from engine import validate_request


def test_two_job_manifest():
    batch_id, jobs = validate_manifest({
        "batch_id": "test-batch",
        "jobs": [
            {"id": "a", "style": "pop", "lyrics": "hello", "cot": "off"},
            {"id": "b", "style": "rock", "lyrics": "world", "cot": "full"},
        ],
    })
    assert batch_id == "test-batch"
    assert [j["id"] for j in jobs] == ["a", "b"]


def test_duplicate_job_id_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        validate_manifest({
            "batch_id": "test",
            "jobs": [
                {"id": "same", "style": "pop", "lyrics": "a"},
                {"id": "same", "style": "pop", "lyrics": "b"},
            ],
        })


def test_sampling_validation():
    clean = validate_request({
        "style": "pop",
        "lyrics": "hello",
        "semantic_sampling": {"min_tokens": 64, "max_tokens": 256},
    })
    assert clean["semantic_sampling"]["max_tokens"] == 256
