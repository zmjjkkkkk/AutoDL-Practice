#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/root/autodl-tmp}"
RUNTIME_DIR="$ROOT/day29-deployment/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_FILE="$RUNTIME_DIR/pids.tsv"
SITE_PACKAGES="/root/miniconda3/lib/python3.12/site-packages"
NVRTC_DIR="$SITE_PACKAGES/nvidia/cu13/lib"
DAY21="$ROOT/day21-policy"
DAY27="$ROOT/day27-vision-service"
DAY28="$ROOT/day28-multimodal-gateway"

mkdir -p "$LOG_DIR"

require_file() {
  [[ -f "$1" ]] || { echo "Missing required file: $1" >&2; exit 1; }
}

require_file "$NVRTC_DIR/libnvrtc-builtins.so.13.0"
require_file "$ROOT/day19-sft/artifacts/qwen3_4b_mindcraft_lora_v2/adapter/adapter_model.safetensors"
require_file "$ROOT/day26-vision-lora/artifacts/qwen25vl_minecraft_entity_lora/adapter/adapter_model.safetensors"
require_file "$DAY21/day21_policy_gateway.py"
require_file "$DAY21/experimental_command_guard.py"
require_file "$DAY27/vision_entity_gateway.py"
require_file "$DAY28/multimodal_gateway.py"

if [[ -f "$PID_FILE" ]]; then
  while IFS=$'\t' read -r _ pid _; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "A Day29-recorded service is still running. Use ./stop_stack.sh first." >&2
      exit 1
    fi
  done < "$PID_FILE"
fi
rm -f "$PID_FILE"

port_is_ready() {
  curl -fsS --max-time 2 "http://127.0.0.1:$1$2" >/dev/null 2>&1
}

for port in 8000 8767 8769 8770; do
  if port_is_ready "$port" "/health"; then
    echo "Port $port already has a healthy service; refusing to take it over." >&2
    exit 1
  fi
done

start_service() {
  local name="$1"
  local marker="$2"
  shift 2
  nohup "$@" >"$LOG_DIR/$name.log" 2>&1 &
  local pid=$!
  printf '%s\t%s\t%s\n' "$name" "$pid" "$marker" >> "$PID_FILE"
  echo "Started $name (pid=$pid)"
}

wait_for() {
  local name="$1"
  local url="$2"
  for _ in $(seq 1 90); do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      echo "$name is healthy"
      return 0
    fi
    sleep 2
  done
  echo "$name did not become healthy. See $LOG_DIR/$name.log" >&2
  exit 1
}

start_service vllm "vllm" env \
  "VLLM_USE_FLASHINFER_SAMPLER=0" "CUDA_VISIBLE_DEVICES=0" \
  "HF_HOME=$ROOT/day15-sft/hf-cache" "HF_HUB_OFFLINE=1" "TRANSFORMERS_OFFLINE=1" \
  "LD_LIBRARY_PATH=$NVRTC_DIR:${LD_LIBRARY_PATH:-}" \
  vllm serve Qwen/Qwen3-4B --host 127.0.0.1 --port 8000 --enable-lora \
  --lora-modules "mindcraft-lora-v2=$ROOT/day19-sft/artifacts/qwen3_4b_mindcraft_lora_v2/adapter" \
  --max-lora-rank 16 --max-model-len 2048 --gpu-memory-utilization 0.80 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
wait_for vllm "http://127.0.0.1:8000/health"

start_service policy "day21_policy_gateway.py" bash -lc "cd '$DAY21' && exec python day21_policy_gateway.py --vllm-url http://127.0.0.1:8000/v1 --model mindcraft-lora-v2 --host 127.0.0.1 --port 8767"
wait_for policy "http://127.0.0.1:8767/health"

start_service vision "vision_entity_gateway.py" env \
  "CUDA_VISIBLE_DEVICES=1" "HF_HUB_OFFLINE=1" "TRANSFORMERS_OFFLINE=1" \
  "LD_LIBRARY_PATH=$NVRTC_DIR:${LD_LIBRARY_PATH:-}" \
  python "$DAY27/vision_entity_gateway.py" --model-dir "$ROOT/models/Qwen2.5-VL-7B-Instruct" \
  --adapter-dir "$ROOT/day26-vision-lora/artifacts/qwen25vl_minecraft_entity_lora/adapter" \
  --host 127.0.0.1 --port 8769
wait_for vision "http://127.0.0.1:8769/health"

start_service multimodal "multimodal_gateway.py" bash -lc "cd '$DAY28' && exec python multimodal_gateway.py --command-url http://127.0.0.1:8767 --vision-url http://127.0.0.1:8769 --host 127.0.0.1 --port 8770"
wait_for multimodal "http://127.0.0.1:8770/health"

echo "Day29 stack is ready. Run: python run_regression.py --image <path> --expected-entity sheep"
