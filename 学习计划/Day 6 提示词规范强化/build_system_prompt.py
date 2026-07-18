import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DAY4_DIR = BASE_DIR.parent / "Day 4 LoRA风格数据准备"
STYLE_SPEC_PATH = DAY4_DIR / "style_spec.json"
CORE_BELIEFS_PATH = DAY4_DIR / "core_beliefs.json"
PROMPT_SPEC_PATH = BASE_DIR / "prompt_spec.json"
OUTPUT_DIR = BASE_DIR / "output"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def gangzhen_instruction(turn_number: int, prompt_spec):
    stages = prompt_spec["gangzhen_progression"]["stages"]
    if turn_number <= 2:
        stage = stages[0]
    elif turn_number <= 5:
        stage = stages[1]
    elif turn_number <= 9:
        stage = stages[2]
    else:
        stage = stages[3]

    return (
        f"当前是第 {turn_number} 轮。"
        f"“港真”目标次数：{stage['target_count']}；{stage['instruction']}。"
    )


def build_system_prompt(turn_number: int):
    style_spec = load_json(STYLE_SPEC_PATH)
    core_beliefs = load_json(CORE_BELIEFS_PATH)
    prompt_spec = load_json(PROMPT_SPEC_PATH)

    tone = "、".join(style_spec["voice"]["tone"])
    preferred_expressions = "、".join(style_spec["preferred_expressions"])
    beliefs = "\n".join(
        f"- {item['principle']}：{item['dialogue_effect']}"
        for item in core_beliefs["beliefs"]
    )
    red_lines = "\n".join(f"- {item}" for item in core_beliefs["red_lines"])
    english_units = "、".join(prompt_spec["code_switching"]["preferred_units"])
    code_switch_rules = "\n".join(
        f"- {item}" for item in prompt_spec["code_switching"]["rules"]
    )
    gangzhen_rules = "\n".join(
        f"- {item}" for item in prompt_spec["gangzhen_progression"]["rules"]
    )
    response_structure = "\n".join(
        f"- {item}" for item in prompt_spec["response_structure"]
    )
    negative_constraints = "\n".join(
        f"- {item}" for item in prompt_spec["negative_constraints"]
    )
    persona_forbidden = "\n".join(
        f"- {item}" for item in prompt_spec["persona_boundary"]["forbidden"]
    )

    return f"""你是一个爱说教的中年公众号口吻对话智能体。

你的核心任务是对话，不是写公众号长文。你像饭局上话很多的中年观察者：爱下判断、爱举现实例子、有一点爹味和自信，但不能恶意，也不能胡说。

口吻：
- 主要气质：{tone}
- 常用表达：{preferred_expressions}
- 节奏：{style_spec['voice']['rhythm']}

思想钢印：
{beliefs}

思想红线：
{red_lines}

中英混用规范：
- 中文是主语言，英文占比约 {prompt_spec['code_switching']['english_ratio']}。
- 优先使用这些短表达：{english_units}。
{code_switch_rules}

“港真”动态规范：
- {gangzhen_instruction(turn_number, prompt_spec)}
{gangzhen_rules}

回答结构：
{response_structure}

身份边界：
{persona_forbidden}

负面约束：
{negative_constraints}

输出时只给对话回答，不解释你遵守了哪些规则。"""


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for turn_number in (1, 3, 6, 10):
        prompt = build_system_prompt(turn_number)
        output_path = OUTPUT_DIR / f"system_prompt_turn_{turn_number}.txt"
        output_path.write_text(prompt, encoding="utf-8")
        print(f"已生成：{output_path}")


if __name__ == "__main__":
    main()
