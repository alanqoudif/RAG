from app.core.constants import MASK_FULL, MASK_PARTIAL


def mask_value(value: object, mask_type: str | None) -> object:
    if value is None or not mask_type or mask_type == "none":
        return value
    text = str(value)
    if mask_type == MASK_FULL:
        return "***"
    if mask_type == MASK_PARTIAL:
        if len(text) <= 4:
            return "*" * len(text)
        return "*" * (len(text) - 4) + text[-4:]
    return value
