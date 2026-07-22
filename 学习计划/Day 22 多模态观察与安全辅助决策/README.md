# Day 22: Multimodal Observation and Safe Decision Support

## Why This Day Exists

The current Mindcraft bot can query structured game state through Mineflayer commands such as `!nearbyBlocks`, `!inventory`, and `!stats`. It does not read screenshots, estimate distance from pixels, or understand objects outside those API query ranges. Asking "What can you see?" is therefore routed to a nearby-block query, not to vision.

Day 22 starts a separate multimodal path: a future vision-language model may describe one Minecraft frame, but it may not create a command or control the bot directly.

## Safety Architecture

```text
local Minecraft frame
-> future vision-language model
-> strict JSON observation guard
-> safe observation text for the player

separate player action request
-> existing LoRA command router
-> exact command allowlist
-> Minecraft action
```

There is deliberately no arrow from the vision model directly to the command allowlist. An observation such as "water is visible" is information, not an instruction to move.

## Files

- `vision_observation_contract.json`: the exact permitted input/output contract.
- `vision_observation_guard.py`: rejects malformed, command-like, multiline, or extra-field vision output.
- `vision_observation_cases.json`: six synthetic offline cases; no real screenshots are stored.
- `test_vision_observation_guard.py`: runs the guard cases without a vision model or GPU.
- `check_vision_environment.py`: reports GPU, PyTorch, and vLLM readiness before model download.
- `query_vision_observation.py`: sends one explicitly selected local image to the future vision endpoint, then prints the raw model result and guarded result. It never calls Mindcraft.

The client keeps the original screenshot unchanged. Before upload it creates a temporary in-memory JPEG whose longest side defaults to 768 pixels. This keeps image token usage inside the small observation context budget and avoids creating a derived screenshot on disk.

## Current Scope

The repository currently uses `Qwen/Qwen3-4B`, a text-only base model. It is not a vision-language model, so this Day does not pretend that the running bot can see images yet.

The selected first vision model is `Qwen/Qwen2.5-VL-7B-Instruct`. It is a vision-language model: it receives an image and text instruction, then returns text. It is separate from the existing `Qwen/Qwen3-4B` LoRA command model.

The next practical step is to run this model in an isolated observation service on GPU 1, send it only one local Minecraft frame, and verify that its raw JSON passes `vision_observation_guard.py`. Real screenshots, personal images, server addresses, and generated reports remain local and ignored by Git.

## Run the Offline Guard Check

```powershell
$day22 = "学习计划\Day 22 多模态观察与安全辅助决策"
python "$day22\test_vision_observation_guard.py"
```

Expected output:

```text
Day 22 observation guard passed: 6/6
```

## Remote Run

Run these only after the Qwen2.5-VL model has been downloaded to the remote cache. Keep the established text command service on GPU 0. Start the vision service separately on GPU 1 and port `8001`:

```bash
export CUDA_VISIBLE_DEVICES=1
export HF_HOME=/root/autodl-tmp/day15-sft/hf-cache
vllm serve Qwen/Qwen2.5-VL-7B-Instruct \
  --host 127.0.0.1 \
  --port 8001 \
  --dtype bfloat16 \
  --max-model-len 2048 \
  --served-model-name minecraft-vision
```

In a second remote terminal, first confirm readiness:

```bash
python check_vision_environment.py
```

For a deliberately chosen test image that remains on the remote machine:

```bash
python query_vision_observation.py \
  --image /root/autodl-tmp/private-test-frame.png \
  --vllm-url http://127.0.0.1:8001/v1 \
  --model minecraft-vision
```

An accepted result is only a player-facing observation. A blocked result returns the fixed safe fallback; neither result reaches the command gateway or controls the bot.

## First Real Observation Run

The selected `Qwen/Qwen2.5-VL-7B-Instruct` model was served through vLLM under the `minecraft-vision` alias on a separate GPU. One deliberately selected Minecraft frame was sent through `query_vision_observation.py`; the client downscaled it only in memory, the model returned a one-line JSON observation, and `vision_observation_guard.py` accepted it as `verified_observation`.

This validates the transport and safety contract, not the factual accuracy of every visual label. Observation output remains player-facing information only, and no visual result is routed into the command allowlist or the Mindcraft bot.
