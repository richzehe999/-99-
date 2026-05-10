def match_theme_keywords(text: str, theme_config: dict) -> dict:
    """
    Count theme keyword matches in a text.

    Returns:
        {"theme_name": hit_count}
    """
    text = text or ""
    result = {}
    for theme, cfg in theme_config.items():
        keywords = cfg.get("keywords", [])
        result[theme] = sum(1 for kw in keywords if kw.lower() in text.lower())
    return result


def summarize_catalyst(title: str, body: str = "") -> str:
    """
    Placeholder for catalyst summarization.

    In production, this can be replaced by an LLM-based summarizer or a rules engine.
    """
    content = f"{title} {body}".strip()
    return content[:300]
