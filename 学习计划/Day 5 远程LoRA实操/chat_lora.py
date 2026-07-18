import argparse
import json
from pathlib import Path
from datetime import datetime

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (
    "你是一个爱说教的中年公众号口吻对话智能体。"
    "回答要像饭局上有点爹味但确实见过一些事的人：先给判断，再讲现实约束，"
    "最后给一个下一步。可以偏爱 UCLA 和港中深，但不能伪造事实。"
)


def save_conversation(history, model_path, adapter_path, session_id):
    """Save after every turn so a disconnect cannot erase the whole session."""
    conversation_dir = adapter_path.parent / "conversations"
    conversation_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "base_model": str(model_path),
        "adapter": str(adapter_path),
        "turn_count": len(history),
        "history": history,
    }

    latest_path = conversation_dir / "latest_conversation.json"
    session_path = conversation_dir / f"conversation_{session_id}.json"
    latest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    session_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return session_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3-8B")
    parser.add_argument(
        "--adapter",
        type=Path,
        default=BASE_DIR / "outputs" / "wechat-qwen3-8b-lora" / "final_adapter",
    )
    args = parser.parse_args()

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
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("LoRA 对话已启动。输入 q 退出，输入 /reset 清空上下文。")

    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in {"q", "quit", "exit"}:
            if history:
                output_path = save_conversation(
                    history,
                    args.model,
                    args.adapter,
                    session_id,
                )
                print(f"对话记录已保存：{output_path}")
            break
        if user_input == "/reset":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("上下文已清空。")
            continue
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        model_inputs = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            enable_thinking=False,
            return_tensors="pt",
            return_dict=True,
        ).to(model.device)

        with torch.inference_mode():
            generated = model.generate(
                **model_inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.75,
                top_p=0.9,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.eos_token_id,
            )

        new_tokens = generated[0, model_inputs["input_ids"].shape[1]:]
        answer = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        messages.append({"role": "assistant", "content": answer})
        messages = [messages[0]] + messages[1:][-12:]
        history.append({"user": user_input, "assistant": answer})
        output_path = save_conversation(
            history,
            args.model,
            args.adapter,
            session_id,
        )

        print("\n智能体：")
        print(answer)
        print(f"\n[已自动保存至 {output_path}]")


if __name__ == "__main__":
    main()
