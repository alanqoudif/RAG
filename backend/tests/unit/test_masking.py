from app.services.database.masking import mask_value


def test_mask_none_type_passthrough():
    assert mask_value("123-45-6789", None) == "123-45-6789"
    assert mask_value("123-45-6789", "none") == "123-45-6789"


def test_mask_full_replaces_entirely():
    assert mask_value("123-45-6789", "full") == "***"


def test_mask_partial_keeps_last_four():
    assert mask_value("123-45-6789", "partial") == "*******6789"


def test_mask_partial_short_value_fully_masked():
    assert mask_value("abc", "partial") == "***"


def test_mask_none_value_passthrough():
    assert mask_value(None, "full") is None
