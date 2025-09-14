# SafeLens Backend (web/)

This folder contains the FastAPI backend for video analysis. Follow the steps below to set up a local PostgreSQL database and prepare the backend environment.

## Prerequisites

- Either of the following Python tooling options:
    - `uv` (recommended): https://docs.astral.sh/uv/getting-started/installation/
    - or system `python3` + `pip`
- `docker` (used to run PostgreSQL locally)

## 1) Configure environment

Copy the example env file and edit database credentials.

```bash
cd web
cp .env.example .env
```

Open `.env` and set the `DATABASE_URL` user and password to match the database you will run in Docker, for example:

```
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/safelens_web_db
```

## 2) Start PostgreSQL (Docker)

Run a local PostgreSQL 17 container. Set `POSTGRES_USER` and `POSTGRES_PASSWORD` to the same values you used in `DATABASE_URL` above.

```bash
docker run --name safelens_web_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=safelens_web_db \
  -p 5432:5432 \
  -v safelens_web_data:/var/lib/postgresql/data \
  -d postgres:17.5
```

Notes

- The named volume `harmful_moderation_data` persists data across container restarts.
- If another service is already using port 5432, change the host port (e.g., `-p 5433:5432`) and update `DATABASE_URL` accordingly.

## 3) Install backend dependencies

Choose ONE of the two options below.

### Option A — Using uv (recommended)

Run all commands from the `web/` directory so uv detects the project.

```bash
cd web
uv venv --seed           # create .venv (optional; uv sync will also create it)
uv sync                  # install from pyproject/uv.lock
```

### Option B — Using python + pip

```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4) Create database tables (Alembic migrations)

Alembic is configured to work from any directory, but the simplest is to run it from `web/`.

### With uv

```bash
cd web
uv run alembic upgrade head
```

### With python + pip

```bash
cd web
alembic upgrade head
```

That’s it — the database schema is now created. You can proceed to start the API server (from `web/`) or continue with the frontend setup in `web/frontend/`.

## 5) Run the API server (from web/)

All runtime commands are intended to be executed inside the `web/` directory.

### With uv (recommended)

```bash
cd web
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Alternative: run the entry script directly
uv run server.py                    # defaults to 0.0.0.0:8000
uv run server.py --port 9000        # override port via CLI
PORT=9000 uv run server.py          # or via env var
uv run server.py --host 127.0.0.1   # override host
```

### With python + pip

```bash
cd web
source .venv/bin/activate  # if you created one
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Notes
- If you see “Failed to spawn: `uvicorn`”, ensure you ran `uv sync` (or installed requirements into your venv) while in `web/`.
- The server file handles script execution cleanly; running `python server.py` from `web/` is also supported.

Where uploads are stored

- The backend writes uploads and analysis artifacts under `./videos/<video_id>/` relative to the working directory (here, `web/` if you follow the commands above). The directory is created automatically.

## vLLM Inference (LoRA Llama‑3‑8B and Qwen2.5‑VL‑7B)

This project expects two local OpenAI‑compatible endpoints provided by vLLM:

- Llama‑3‑8B‑Instruct with our LoRA adapter (for text analysis/summarization)
- Qwen2.5‑VL‑7B‑Instruct (for vision+language captioning)

Set the endpoints before running analysis. If you only need one of them, you can run a single server.

### GPU / VRAM sizing (rule‑of‑thumb)

- Llama‑3‑8B‑Instruct (bf16/fp16 weights): ~15–16 GB VRAM for weights alone. With runtime overhead and KV cache (depends on `--max-model-len`, concurrency, and vLLM’s memory fraction), plan for ~18–22 GB. On 16 GB cards you’ll likely need lower `--max-model-len` (e.g., 4096) and/or lower `--gpu-memory-utilization`.
- Qwen2.5‑VL‑7B‑Instruct (bf16/fp16): ~14–16 GB for weights; plan ~16–22 GB with overhead/KV cache.
- Lower memory tips:
    - Reduce `--max-model-len` (KV cache is the biggest variable).
    - Reduce `--gpu-memory-utilization` (vLLM will reserve less VRAM for cache).
    - Use a smaller base model or a quantized base (vLLM requires specific quantized model weights; it’s not a flag‑only change).

Numbers above are ballpark; exact usage varies by driver/framework/version and concurrent requests.

### Start the servers (uvx or pip)

Compute the absolute path to the LoRA adapter (must point at `web/lora_adapter/`):

```bash
LORA_DIR=$(python3 - << 'PY'
import os
print(os.path.abspath('web/lora_adapter'))
PY
)
```

Run both servers (adjust `CUDA_VISIBLE_DEVICES` as needed):

```bash
# 1) Llama‑3‑8B‑Instruct + LoRA (port 8192)
CUDA_VISIBLE_DEVICES=0 \
uvx vllm serve meta-llama/Meta-Llama-3-8B-Instruct \
  --host 0.0.0.0 --port 8192 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.7 \
  --dtype bfloat16 \
  --enable-lora \
  --lora-modules SafeLens/llama-3-8b=${LORA_DIR}

# 2) Qwen2.5‑VL‑7B‑Instruct (port 8193)
CUDA_VISIBLE_DEVICES=1 \
uvx vllm serve Qwen/Qwen2.5-VL-7B-Instruct \
  --host 0.0.0.0 --port 8193 \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.5 \
  --max-model-len 8192
```

Notes

- Single‑GPU machines: start only one server at a time, or run both with smaller `--max-model-len` and lower `--gpu-memory-utilization` on the same device.
- Multi‑GPU machines: use different `CUDA_VISIBLE_DEVICES` and ports as shown.
- pip alternative: `pip install vllm` then replace `uvx vllm serve` with `python -m vllm.entrypoints.openai.api_server serve ...` (or `python -m vllm …` depending on your vLLM version).

### Point the backend at vLLM

Update `web/.env` so the backend uses these endpoints:

```env
# Text LLM (LoRA over Llama‑3‑8B)
ANALYSIS_LLM_HTTP_URL=http://localhost:8192/v1
ANALYSIS_LLM_MODEL=SafeLens/llama-3-8b

# Vision LLM (Qwen2.5‑VL‑7B)
QWEN_VLLM_BASE_URL=http://localhost:8193/v1
QWEN_VLLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
```

The LoRA adapter is registered with vLLM under the alias `SafeLens/llama-3-8b` via `--lora-modules`. Our backend sends the `model` field accordingly.

### Quick health checks

```bash
curl -s http://localhost:8192/v1/models | jq .
curl -s http://localhost:8193/v1/models | jq .
```

If either returns an error or OOMs, lower `--max-model-len`, reduce `--gpu-memory-utilization`, or stop one server to free VRAM.
