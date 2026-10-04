FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/workspace/huggingface \
    BATCH_OUTPUT_DIR=/workspace/yue2-batch-output

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    git \
    libsndfile1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv "$VIRTUAL_ENV" \
    && python -m pip install --upgrade pip setuptools wheel

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

COPY config.py engine.py storage.py batch.py ./

CMD ["python", "-u", "batch.py"]
