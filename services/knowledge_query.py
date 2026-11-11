"""Public one-question entry point for the TrackFlow RAG pipeline."""

from __future__ import annotations

import re

from data.pipelines.rag import OpenAICompatibleGenerationProvider, answer_question


class UnsafeGeneratedAnswerError(RuntimeError):
    """The model response did not satisfy the required policy guardrail."""


_POLICIES = {
    "peak_delivery": {
        "source": "sla-delivery",
        "section": "Delivery SLA",
        "evidence": ("does not guarantee delivery SLA", "40%", "proactively"),
    },
    "international_returns": {
        "source": "returns-policy",
        "section": "Returns Policy",
        "evidence": ("not covered by the standard automated process", "require manual handling"),
    },
    "storage_discount": {
        "source": "storage-pricing",
        "section": "Storage Pricing",
        "evidence": ("more than 50 cubic meters", "preferential rate", "Miguel Torres"),
    },
    "carrier_exception": {
        "source": "carrier-coverage",
        "section": "Carrier Coverage",
        "evidence": ("exception approved by Carlos Vega",),
    },
}


def _policy_categories(text: str) -> set[str]:
    normalized = text.casefold()
    categories = set()
    if re.search(r"black\s+friday|christmas|january\s+sales|high[ -]demand|peak\s+(?:season|period|dates)", normalized):
        categories.add("peak_delivery")
    if re.search(r"international|cross[ -]border|another country|different countr(?:y|ies)", normalized) and re.search(r"return", normalized):
        categories.add("international_returns")
    if re.search(r"storage|warehouse|inventory|volume", normalized) and re.search(r"discount|preferential|negotiat|reduc(?:e|ed|tion)|special\s+rate", normalized):
        categories.add("storage_discount")
    if re.search(r"carrier|courier", normalized) and re.search(r"exception|manual|override|choose|select", normalized):
        categories.add("carrier_exception")
    return categories


def _validate_policy_response(category: str, generated: str) -> bool:
    answer = generated.casefold()
    if category == "peak_delivery":
        sentences = re.split(r"(?<=[.!?])\s+", answer)
        positive_guarantee = any(
            "guarantee" in sentence
            and not re.search(r"\b(?:does not|do not|is not|are not|never|no|cannot|can't)\b", sentence)
            for sentence in sentences
        )
        denies_guarantee = bool(
            re.search(r"\b(?:does not|do not|is not|are not|never|no|cannot|can't)\b.{0,40}\bguarantee(?:d)?\b", answer)
        )
        return not positive_guarantee and denies_guarantee and "40%" in answer and "proactiv" in answer

    if category == "international_returns":
        positive_automatic = bool(
            re.search(
                r"\binternational returns?\b.{0,140}\b(?:are|is|can be|may be|will be)\s+(?:fully\s+)?(?:automatic|automated)\b",
                answer,
            )
        )
        has_manual = "manual handling" in answer
        has_non_automatic_scope = bool(
            re.search(r"\bnot\b.{0,50}\b(?:standard\s+)?automated process\b", answer)
            or re.search(r"\bnot automatic(?:ally)?\b", answer)
        )
        return not positive_automatic and has_manual and has_non_automatic_scope

    if category == "storage_discount":
        approval = "miguel torres" in answer and bool(
            re.search(r"\b(?:approval|approved|must go through|requires? approval)\b", answer)
        )
        unauthorized_offer = bool(
            re.search(r"\bwithout\s+(?:miguel(?: torres)?'s?\s+)?approval\b|\bno approval required\b", answer)
            or re.search(r"\baccount manager\b.{0,80}\bcan\s+(?:offer|grant)\b.{0,80}\b(?:independently|on their own|without approval)\b", answer)
        )
        return approval and not unauthorized_offer

    if category == "carrier_exception":
        approval = "carlos vega" in answer and bool(re.search(r"\b(?:approval|approved)\b", answer))
        unauthorized_choice = bool(
            re.search(r"\bwithout\s+(?:carlos(?: vega)?'s?\s+)?approval\b|\bno approval required\b", answer)
            or re.search(r"\b(?:any|all) carriers?\b.{0,60}\b(?:can|may|choose|select)\b", answer)
        )
        return approval and not unauthorized_choice
    return True


class _GuardedGenerationProvider:
    """Accept safe source-backed paraphrases; reject conflicts and unsupported policy replies."""

    def __init__(self, provider: OpenAICompatibleGenerationProvider, question: str):
        self.provider = provider
        self.question = question

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        generated = self.provider.generate(system_prompt, user_prompt)
        if "[NO RELEVANT EVIDENCE RETRIEVED ABOVE THE SIMILARITY THRESHOLD]" in user_prompt:
            return generated

        context = user_prompt.split("</context>", 1)[0]
        available_sources = {
            (source.strip(), section.strip())
            for source, section in re.findall(
                r"\[source_document:\s*([^|]+?)\s*\|\s*section:\s*([^|]+?)\s*\|",
                context,
            )
        }
        citations = {
            (source.strip(), section.strip())
            for source, section in re.findall(r"\[([^\]|]+)\s*\|\s*([^\]]+)\]", generated)
        }
        if any(citation not in available_sources for citation in citations):
            raise UnsafeGeneratedAnswerError("The generated answer cited a source that was not retrieved.")

        categories = _policy_categories(self.question) | _policy_categories(generated)
        evidence = context.casefold()
        for category in categories:
            policy = _POLICIES[category]
            source_marker = f"[source_document: {policy['source']} | section: {policy['section']} |"
            if source_marker.casefold() not in evidence:
                raise UnsafeGeneratedAnswerError("The required policy source was not retrieved.")
            if not all(phrase.casefold() in evidence for phrase in policy["evidence"]):
                raise UnsafeGeneratedAnswerError("The retrieved source does not contain all required policy facts.")
            if not _validate_policy_response(category, generated):
                raise UnsafeGeneratedAnswerError("The generated answer conflicts with or omits a required policy guardrail.")
        return generated


def query(question: str) -> str:
    """Retrieve and generate one grounded answer; this is the external query wrapper."""
    if not question.strip():
        raise ValueError("Question must not be blank.")
    provider = OpenAICompatibleGenerationProvider.from_env()
    return answer_question(question.strip(), _GuardedGenerationProvider(provider, question.strip()))
