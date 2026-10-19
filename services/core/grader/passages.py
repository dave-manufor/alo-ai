"""What the Grader reads from a passage artifact (schemas/passage.schema.json)."""


def ordered_items(passage: dict) -> list[dict]:
    """Scripted items in the order they are asked; index 0 is the first question."""
    return sorted(passage["items"], key=lambda item: item["order"])


def total_weight(passage: dict) -> int:
    return sum(proposition["weight"] for proposition in passage["propositions"])


def weights(passage: dict) -> dict[str, int]:
    return {proposition["id"]: proposition["weight"] for proposition in passage["propositions"]}
