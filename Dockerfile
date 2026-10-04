FROM ghcr.io/hexadi/yue2-serverless:sha-b8a2ac1

ENV HF_HOME=/workspace/huggingface \
    BATCH_OUTPUT_DIR=/workspace/yue2-batch-output

WORKDIR /app

RUN python -m pip install "requests>=2.32,<3"

COPY config.py engine.py storage.py batch.py ./

CMD ["python", "-u", "batch.py"]
