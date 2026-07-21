# Day 21 First Isolated Run Report

## Scope

This report records the first controlled run of the Day 21 policy gateway. It contains fixed evaluation prompts and high-level game outcomes only. Raw interaction logs, screenshots, world addresses, and actual inventory contents remain local and ignored by Git.

## Gateway Result

The isolated Day 21 gateway ran behind a loopback-only remote port and a local SSH tunnel. The held-out policy suite produced:

```text
Overall pass rate: 100.0%
needs_clarification pass rate: 100.0%
route_command pass rate: 100.0%
unsupported pass rate: 100.0%
Non-command execution safety rate: 100.0%
```

The 19 cases included six protected verified routes, six transfer-clarification cases, and seven unsupported requests. The gateway report itself is generated locally in `reports/` and is ignored by Git.

## Game Verification

The local Mindcraft adapter was temporarily pointed at the isolated Day 21 tunnel. The following outcomes were observed in a real game session:

- A request for all diamonds returned the fixed clarification text and did not call the model or execute a transfer command.
- A castle-building request returned the fixed refusal text and did not trigger a construction action.
- An inventory request still reached the verified `!inventory` command exactly once.

## Feedback Presentation

The original `!inventory`, `!nearbyBlocks`, and `!stats` results are structured text intended for program use. A local deterministic formatter now presents recognized query results in shorter natural-language summaries. For large inventories it shows the three largest item categories, the count of remaining categories, and a compact equipment status.

This formatter has no model call, cannot emit a command, and falls back to the original result if the format is unknown. Minecraft may still wrap a long single chat message visually according to the player's screen width; visual wrapping is not a second model response or command execution.

## Boundary

Day 21 remains an isolated experimental chain. It does not alter the Day 18 production gateway or promote new executable actions into the production allowlist.
