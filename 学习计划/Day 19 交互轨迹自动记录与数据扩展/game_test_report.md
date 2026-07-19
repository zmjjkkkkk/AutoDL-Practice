# Day 19 Real-Game Test Report

Test date: 2026-07-19

## Scope

- Base model: `Qwen/Qwen3-4B`
- Experimental adapter: `qwen3_4b_mindcraft_lora_v2`
- Runtime: vLLM with the Day 19 experimental command gateway
- Guard policy: the Day 18 production allowlist remained unchanged; the experiment used an isolated allowlist on port 8766.

## Offline Result

The expanded dataset contained 128 training examples and 32 held-out evaluation examples. Exact command matching was 31/32 (96.875%). The only mismatch was the ambiguous inventory request `do you have anything`, which the model treated as a greeting. It remains a future data-collection target and was not added back into this evaluation set.

## Real-Game Results

| User request | Generated command | Result | Interpretation |
| --- | --- | --- | --- |
| What time is it in the world | `!stats` | Passed | Returned the game status, including that the time was night. |
| Please give me an oak log | `!givePlayer("robot", "oak_log", 1)` | Passed | The agent reached the player, discarded one oak log, and the player received it. |
| Find an iron ore | `!searchForBlock("iron_ore", 32)` | Passed after retry | The first attempt found ore but could not path through stone with the current tool; the second found a non-destructive path and reached the ore. This is an execution-context issue, not a command-mapping error. |
| Eat an apple | `!consume("apple")` | Passed | The game confirmed apple consumption. |
| Craft an iron sword | `!craftRecipe("iron_sword", 1)` | Passed | The game confirmed that an iron sword was crafted. |
| Attack a creeper | `!attack("creeper")` | Needs retest | The command was accepted, but the action was interrupted by the agent's self-defense mode. |
| Throw an iron sword to me | `!givePlayer("robot", "iron_sword", 1)` | Blocked intentionally | The model generalized the command syntax to a new item, but the exact static allowlist had not authorized that item. |

## Decision

`!stats`, oak-log transfer, iron-ore search, apple consumption, and iron-sword crafting have completed real-game verification in the Day 19 experimental environment. They should still be promoted to the production allowlist one command at a time after a short regression check.

The creeper action needs a controlled retry. Iron-sword transfer is a useful next candidate: its model output is structurally correct, but it requires an explicit allowlist addition and a real-game test before promotion. Pathfinding/tool failures should be logged as environment constraints rather than used as negative SFT labels.
