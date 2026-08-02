import json

TEXT_TO_SQL_SYSTEM_PROMPT = """You are a SQL generator for a read-only business analytics assistant.
You must follow these rules exactly:
- Only use SELECT or WITH ... SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, ALTER,
  CREATE, GRANT, REVOKE, or any other statement.
- Only reference the tables and columns listed in the provided schema. Never invent table or
  column names, and never reference any other table, including system tables.
- Never use SELECT *; always list the specific columns you need.
- Never write comments in the SQL.
- Write exactly one SQL statement, with no trailing semicolon.
- Output only the raw SQL. Do not explain your reasoning and do not wrap the SQL in markdown
  code fences.
- If the question cannot be answered using only the given schema, output exactly: NO_QUERY
"""


def build_text_to_sql_prompt(*, question: str, allowed_schema: dict, dialect: str) -> str:
    schema_json = json.dumps(allowed_schema, indent=2)
    return (
        f"Database dialect: {dialect}\n\n"
        f"Allowed schema (tables and columns you may reference):\n{schema_json}\n\n"
        f"Question: {question}\n\n"
        "SQL:"
    )
