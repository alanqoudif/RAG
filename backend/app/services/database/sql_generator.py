import re

from app.services.llm.ollama_client import OllamaClient
from app.services.llm.prompts import TEXT_TO_SQL_SYSTEM_PROMPT, build_text_to_sql_prompt

_FENCE_PATTERN = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_sql(raw_response: str) -> str | None:
    """Pulls the SQL statement out of a raw LLM response: strips markdown fences if present,
    strips a trailing semicolon, and returns None for the model's explicit "cannot answer" signal.
    """
    text = raw_response.strip()
    if not text:
        return None

    fence_match = _FENCE_PATTERN.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    if text.upper().startswith("NO_QUERY"):
        return None

    text = text.strip().rstrip(";").strip()
    return text or None


async def generate_sql(
    ollama_client: OllamaClient, *, question: str, allowed_schema: dict, dialect: str
) -> str | None:
    prompt = build_text_to_sql_prompt(question=question, allowed_schema=allowed_schema, dialect=dialect)
    raw_response = await ollama_client.generate(prompt, system=TEXT_TO_SQL_SYSTEM_PROMPT, temperature=0.0)
    return extract_sql(raw_response)
