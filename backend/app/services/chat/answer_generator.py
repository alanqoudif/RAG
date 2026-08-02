from app.services.llm.ollama_client import OllamaClient
from app.services.llm.prompts import ANSWER_SYSTEM_PROMPT, build_answer_prompt


async def generate_answer(
    ollama_client: OllamaClient,
    *,
    question: str,
    database_evidence: list[dict],
    document_evidence: list[dict],
) -> str:
    if not database_evidence and not document_evidence:
        return "I could not find enough approved evidence to answer this question."

    prompt = build_answer_prompt(
        question=question, database_evidence=database_evidence, document_evidence=document_evidence
    )
    return await ollama_client.generate(prompt, system=ANSWER_SYSTEM_PROMPT, temperature=0.1)
