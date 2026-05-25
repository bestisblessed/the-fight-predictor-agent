import re
from dataclasses import dataclass


AI_REPLY_ACTION = "ai_reply"
SCOPE_REPLY_ACTION = "scope_reply"
SCOPE_REPLY_TEXT = (
    "I only process MMA/UFC/fight prediction questions or questions about this AI "
    "bot, its data, and how it works. Tag me with an in-scope question and I'll help."
)

HANDLE_RE = re.compile(r"@\w+")
URL_RE = re.compile(r"https?://\S+")
WORD_RE = re.compile(r"[a-z0-9']+")

MMA_TERMS = {
    "mma",
    "ufc",
    "bellator",
    "pfl",
    "rizin",
    "one championship",
    "fight night",
    "fight card",
    "fight",
    "fights",
    "fighting",
    "main event",
    "co main",
    "matchup",
    "match up",
    "versus",
    "fighter",
    "fighters",
    "bout",
    "round",
    "ko",
    "tko",
    "knockout",
    "submission",
    "decision",
    "grappling",
    "wrestling",
    "striking",
    "cage",
    "octagon",
    "champ",
    "champion",
}

WEAK_MMA_TERMS = {
    "prediction",
    "predictions",
    "predict",
    "pick",
    "picks",
    "odds",
    "bet",
    "bets",
    "betting",
    "underdog",
}

CORE_AI_META_TERMS = {
    "ai",
    "bot",
    "agent",
    "model",
    "openai",
    "data",
    "dataset",
    "datasets",
    "source",
    "sources",
    "work",
    "works",
    "capabilities",
}

AUX_AI_META_TERMS = {
    "prediction",
    "predictions",
    "pick",
    "picks",
}

QUESTION_TERMS = {
    "what",
    "how",
    "why",
    "where",
    "which",
    "who",
    "can",
    "could",
    "do",
    "does",
    "did",
    "is",
    "are",
    "tell",
    "explain",
}

SPAM_TERMS = {
    "altcoin",
    "crypto",
    "coin",
    "token",
    "wallet",
    "airdrop",
    "nft",
    "pump",
    "privately",
    "private",
    "dm",
    "direct message",
    "collab",
    "collaborate",
    "collaboration",
    "follow back",
    "follow me",
}


@dataclass(slots=True)
class ScopeDecision:
    action: str
    reason: str
    signals: list[str]


def classify_mention_scope(tweet_text: str, matched_fighters: list[str] | None = None) -> ScopeDecision:
    normalized = normalize_scope_text(tweet_text)
    matched_fighters = [name for name in (matched_fighters or []) if str(name).strip()]
    spam_signals = matching_terms(normalized, SPAM_TERMS)

    signals = []
    if matched_fighters:
        signals.extend(f"fighter:{name}" for name in matched_fighters)

    mma_signals = matching_terms(normalized, MMA_TERMS)
    if mma_signals:
        signals.extend(f"mma:{term}" for term in mma_signals)

    meta_signals = matching_meta_terms(normalized, CORE_AI_META_TERMS)
    if meta_signals:
        signals.extend(f"meta:{term}" for term in meta_signals)

    if signals:
        return ScopeDecision(action=AI_REPLY_ACTION, reason="in_scope", signals=signals)

    weak_signals = matching_terms(normalized, WEAK_MMA_TERMS)
    auxiliary_meta_signals = matching_meta_terms(normalized, AUX_AI_META_TERMS)
    weak_scope_signals = weak_signals + auxiliary_meta_signals
    if weak_scope_signals and not spam_signals:
        return ScopeDecision(
            action=AI_REPLY_ACTION,
            reason="in_scope",
            signals=[f"weak_scope:{term}" for term in weak_scope_signals],
        )

    if spam_signals:
        return ScopeDecision(
            action=SCOPE_REPLY_ACTION,
            reason="out_of_scope_spam",
            signals=[f"spam:{term}" for term in spam_signals],
        )

    return ScopeDecision(action=SCOPE_REPLY_ACTION, reason="out_of_scope", signals=[])


def normalize_scope_text(value: str) -> str:
    without_handles = HANDLE_RE.sub(" ", value or "")
    without_urls = URL_RE.sub(" ", without_handles)
    lowered = without_urls.lower()
    cleaned = re.sub(r"[^a-z0-9\s'?]", " ", lowered)
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    return collapsed.replace("'", "")


def matching_terms(normalized_text: str, terms: set[str]) -> list[str]:
    padded = f" {normalized_text} "
    matches = []
    for term in sorted(terms):
        normalized_term = normalize_scope_text(term)
        if f" {normalized_term} " in padded:
            matches.append(term)
    return matches


def matching_meta_terms(normalized_text: str, terms: set[str]) -> list[str]:
    words = set(WORD_RE.findall(normalized_text))
    has_question_intent = "?" in normalized_text or bool(words & QUESTION_TERMS)
    if not has_question_intent:
        return []
    return matching_terms(normalized_text, terms)
