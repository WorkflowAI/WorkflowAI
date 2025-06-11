REASONING_EFFORT_TO_BUDGET = {
    "low": 1024,
    "medium": 8192,
    "high": 16384,
}


def reasoning_effort_to_budget(reasoning_effort: str | int, max_output_tokens: int) -> int:
    if isinstance(reasoning_effort, int):
        return reasoning_effort
    if reasoning_effort == "highest":
        return max_output_tokens - 1
    return REASONING_EFFORT_TO_BUDGET.get(reasoning_effort, 0)


def budget_to_reasoning_effort(budget: int, max_output_tokens: int) -> str:
    for effort, val in REASONING_EFFORT_TO_BUDGET.items():
        if budget == val:
            return effort
    if budget >= max_output_tokens - 1:
        return "highest"
    # Default to low if unknown
    return "low"
