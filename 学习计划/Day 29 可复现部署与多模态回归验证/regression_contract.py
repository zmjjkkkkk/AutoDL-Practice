"""Pure response checks for the public Day 29 regression runner."""


def _dict(value):
    return value if isinstance(value, dict) else {}


def assess_health(status: int, body: object) -> tuple[bool, str]:
    body = _dict(body)
    command = _dict(body.get("command_upstream"))
    vision = _dict(body.get("vision_upstream"))
    ok = status == 200 and body.get("ok") is True and command.get("reachable") is True and vision.get("reachable") is True
    return ok, "both_upstreams_reachable" if ok else "health_contract_failed"


def assess_text_command(status: int, body: object) -> tuple[bool, str]:
    command = _dict(_dict(body).get("command"))
    ok = status == 200 and command.get("status") == "verified_command" and command.get("command") == '!followPlayer("robot", 3)'
    return ok, "verified_follow_command" if ok else "text_command_contract_failed"


def assess_safe_transfer(status: int, body: object) -> tuple[bool, str]:
    command = _dict(_dict(body).get("command"))
    ok = status == 200 and command.get("status") == "no_command" and command.get("command") is None
    return ok, "transfer_not_executed" if ok else "transfer_safety_contract_failed"


def assess_invalid_request(status: int, body: object) -> tuple[bool, str]:
    body = _dict(body)
    ok = status == 400 and body.get("ok") is False and body.get("reason") == "invalid_request"
    return ok, "invalid_request_rejected" if ok else "invalid_request_contract_failed"


def assess_visual_only(status: int, body: object, expected_entity: str) -> tuple[bool, str]:
    body = _dict(body)
    command = _dict(body.get("command"))
    observation = _dict(body.get("observation"))
    ok = status == 200 and command.get("status") == "not_requested" and observation.get("status") == "verified_observation" and observation.get("entity") == expected_entity
    return ok, "visual_only_isolated" if ok else "visual_only_contract_failed"


def assess_combined(status: int, body: object, expected_entity: str) -> tuple[bool, str]:
    text_ok, _ = assess_text_command(status, body)
    observation = _dict(_dict(body).get("observation"))
    ok = text_ok and observation.get("status") == "verified_observation" and observation.get("entity") == expected_entity
    return ok, "combined_results_isolated" if ok else "combined_contract_failed"
