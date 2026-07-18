import argparse
import json
from datetime import datetime
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (
    "你是一个爱说教的中年公众号口吻对话智能体。中文为主，可以自然夹少量英文，"
    "并把“港真”用作自然转折。先给判断，再讲现实约束，最后给下一步。"
    "你可以主观偏爱 UCLA 和港中深，但必须区分偏爱与客观事实。"
    "禁止虚构个人履历、教授关系、工作经历或亲历故事。"
)


def save_history(history, adapter):
    output_dir = BASE_DIR / "output" / "conversations"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"final_chat_{timestamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "adapter": str(adapter),
        "turn_count": len(history),
        "history": history,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter", required=True, type=Path)
    args = parser.parse_args()

    if not args.adapter.is_dir():
        raise FileNotFoundError(
            f"LoRA adapter 目录不存在：{args.adapter}\n"
            "请先确认最终训练已完成，或用 find 命令查找 adapter_config.json 的实际位置。"
        )
    adapter_config = args.adapter / "adapter_config.json"
    if not adapter_config.is_file():
        raise FileNotFoundError(
            f"目录存在，但缺少 adapter_config.json：{args.adapter}"
        )

    tokenizer = AutoTokenizer.from_pretrained(args.adapter)
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
    )
    model = PeftModel.from_pretrained(base_model, args.adapter)
    model.eval()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    history = []
    print("最终版公众号风格智能体已启动。输入 q 退出。")

    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in {"q", "quit", "exit"}:
            if history:
                print(f"对话已保存：{save_history(history, args.adapter)}")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        context_messages = [messages[0]] + messages[1:][-12:]
        inputs = tokenizer.apply_chat_template(
            context_messages,
            add_generation_prompt=True,
            enable_thinking=False,
            return_tensors="pt",
            return_dict=True,
        ).to(model.device)

        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.08,
                pad_token_id=tokenizer.eos_token_id,
            )

        new_tokens = generated[0, inputs["input_ids"].shape[1]:]
        answer = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        messages.append({"role": "assistant", "content": answer})
        history.append({"user": user_input, "assistant": answer})
        print("\n智能体：")
        print(answer)


if __name__ == "__main__":
    main()
