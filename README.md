# yue2-batch

Cost-optimized batch song generation with YuE2 on RunPod GPU Pods.

This worker is separate from `yue2-serverless`. The Serverless endpoint is for interactive one-song requests; this repository targets queued/bulk generation where loading YuE2 once and processing many songs on a cheaper Pod lowers cost per song.

## Architecture

```text
batch manifest
   |
   v
temporary RunPod GPU Pod
   |
   +-- load YuE2 once
   |
   +-- song 1
   +-- song 2
   +-- song 3
   +-- ...
   |
   v
R2/S3 or local batch output
   |
   v
orchestrator stops/deletes Pod
```

## Manifest

```json
{
  "batch_id": "album-001",
  "jobs": [
    {
      "id": "song-001",
      "style": "Thai indie pop, warm male vocal, 100 BPM",
      "lyrics": "[Verse]\n...",
      "cot": "full",
      "seed": 42
    },
    {
      "id": "song-002",
      "style": "Dream pop, female vocal, 95 BPM",
      "lyrics": "[Verse]\n...",
      "cot": "full",
      "seed": 43
    }
  ]
}
```

Each job accepts the same generation fields as `yue2-serverless`: `style`, `lyrics`, `cot`, `seed`, `abc`, `cfg_scale`, `id`, `abc_sampling`, and `semantic_sampling`.

The default maximum is 50 jobs per batch.

## Run a batch

The client-side orchestrator requires `runpodctl` to already be authenticated:

```bash
python scripts/run_batch.py \
  --manifest-url https://example.com/batch.json
```

Defaults:

- Community RTX 4090
- 30 GB container disk
- 60-minute safety timeout
- ephemeral Pod: stop and delete when `BATCH_COMPLETE` appears
- YuE2 is loaded once for all jobs

Use `--cloud-type SECURE` if Community Cloud is not appropriate. Use `--keep-pod` only when intentionally retaining the Pod.

## Smoke manifest

```bash
python scripts/run_batch.py \
  --manifest-url https://raw.githubusercontent.com/hexadi/yue2-batch/main/examples/batch-smoke.json
```

The smoke manifest generates two short ~10-second outputs to validate batching without paying for full songs.

## Output

Without S3/R2, output is written under:

```text
/workspace/yue2-batch-output/<batch-id>/
  batch-result.json
  song-001/
    audio.flac
    ...
  song-002/
    audio.flac
    ...
```

With S3-compatible storage configured, selected artifacts are uploaded to:

```text
<S3_PREFIX>/<batch-id>/<song-id>/
```

## Cost model

The batch approach targets two savings:

1. A Pod GPU hourly rate can be lower than Serverless.
2. Model load/startup overhead is shared across all songs in one batch.

The exact saving depends on GPU availability, batch size, song duration, retries, storage, and warm/cold model state. Measure real RunPod billing for production-sized batches before setting customer pricing.

## Safety

The orchestrator always attempts to stop the Pod in a `finally` block and deletes it by default. A hard client/network failure can still leave cloud resources alive, so production orchestration should add an external watchdog and RunPod spend limits.

## Upstream licensing

YuE2 model weights and upstream runtime have their own license terms. Review current upstream commercial-use requirements before offering this as a paid service.
