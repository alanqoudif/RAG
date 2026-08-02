from app.services.database.sql_generator import extract_sql


def test_extract_sql_strips_markdown_fence():
    raw = "```sql\nSELECT id FROM customers\n```"
    assert extract_sql(raw) == "SELECT id FROM customers"


def test_extract_sql_strips_plain_fence():
    raw = "```\nSELECT id FROM customers\n```"
    assert extract_sql(raw) == "SELECT id FROM customers"


def test_extract_sql_strips_trailing_semicolon():
    assert extract_sql("SELECT id FROM customers;") == "SELECT id FROM customers"


def test_extract_sql_no_query_signal_returns_none():
    assert extract_sql("NO_QUERY") is None
    assert extract_sql("no_query") is None


def test_extract_sql_empty_returns_none():
    assert extract_sql("") is None
    assert extract_sql("   ") is None


def test_extract_sql_plain_sql_passthrough():
    assert extract_sql("SELECT id FROM customers") == "SELECT id FROM customers"
