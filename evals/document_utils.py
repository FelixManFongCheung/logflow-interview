"""Format retrieved context for LLM-as-judge evaluators."""


def format_documents(documents: object) -> str:
    """Join retrieved context blocks into one FACTS string for graders."""
    if not documents:
        return "(no documents retrieved)"
    if not isinstance(documents, list):
        return str(documents)
    parts: list[str] = []
    for doc in documents:
        if isinstance(doc, str):
            parts.append(doc)
        elif isinstance(doc, dict):
            content = doc.get("content") or doc.get("page_content")
            parts.append(str(content) if content else str(doc))
        elif hasattr(doc, "page_content"):
            parts.append(str(doc.page_content))
    if not parts:
        return "(no documents retrieved)"
    return "\n\n".join(parts)
