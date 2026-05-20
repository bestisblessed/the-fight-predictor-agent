import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd


WORD_RE = re.compile(r"[a-z0-9']+")
MAX_ALIAS_TOKENS = 4


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    lowered = str(value).lower()
    cleaned = re.sub(r"[^a-z0-9\s']", " ", lowered)
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    return collapsed.replace("'", "")


def token_sort_text(value: str) -> str:
    return " ".join(sorted(value.split()))


@dataclass(slots=True)
class FighterMatch:
    fighter_name: str
    normalized_name: str
    fighter_id: str
    score: float
    row: dict[str, Any]
    match_type: str = "exact"
    matched_text: str = ""


class MmaContextBuilder:
    def __init__(self, fighter_info_path: Path, event_data_path: Path):
        self.fighter_info = pd.read_csv(fighter_info_path).fillna("")
        self.fighter_info["normalized_name"] = self.fighter_info["Fighter"].map(normalize_text)
        self.fighter_info["sort_fights"] = self.fighter_info["Wins"].astype(int) + self.fighter_info["Losses"].astype(int)

        deduped = (
            self.fighter_info.sort_values(by="sort_fights", ascending=False)
            .drop_duplicates(subset=["normalized_name"], keep="first")
            .copy()
        )

        self.fighter_records = []
        self.fighters_by_name: dict[str, dict[str, Any]] = {}
        self.names_by_token_count: dict[int, list[str]] = {1: [], 2: [], 3: [], 4: []}
        self.aliases_by_token_count: dict[int, list[tuple[str, str]]] = {
            1: [],
            2: [],
            3: [],
            4: [],
        }
        self.canonical_by_alias: dict[str, str] = {}

        for _, row in deduped.iterrows():
            record = row.to_dict()
            normalized_name = record["normalized_name"]
            self.fighters_by_name[normalized_name] = record
            self.fighter_records.append(record)
            if normalized_name:
                token_count = min(len(normalized_name.split()), MAX_ALIAS_TOKENS)
                self.names_by_token_count[token_count].append(normalized_name)
                for alias in self._aliases_for_name(normalized_name):
                    self.canonical_by_alias.setdefault(alias, normalized_name)

        for alias, canonical_name in self.canonical_by_alias.items():
            token_count = min(len(alias.split()), MAX_ALIAS_TOKENS)
            self.aliases_by_token_count[token_count].append((alias, canonical_name))

        for aliases in self.aliases_by_token_count.values():
            aliases.sort(key=lambda item: len(item[0]), reverse=True)

        self.fighter_records.sort(key=lambda item: len(item["normalized_name"]), reverse=True)

        self.events = pd.read_csv(event_data_path).fillna("")
        self.events["normalized_fighter_1"] = self.events["Fighter 1"].map(normalize_text)
        self.events["normalized_fighter_2"] = self.events["Fighter 2"].map(normalize_text)
        self.events["fighter_1_id_str"] = self.events["Fighter 1 ID"].map(lambda value: str(value).strip())
        self.events["fighter_2_id_str"] = self.events["Fighter 2 ID"].map(lambda value: str(value).strip())
        self.events["event_date_dt"] = pd.to_datetime(self.events["Event Date"], utc=True, errors="coerce")
        self.events = self.events.sort_values(by="event_date_dt", ascending=False)

    def build_context(self, tweet_text: str) -> dict[str, Any]:
        matches = self.match_fighters(tweet_text)
        if not matches:
            return {
                "matched_fighters": [],
                "context_text": "No structured fighter match found in local MMA data.",
                "resolution_source": "local",
                "resolution_complete": False,
                "match_details": [],
            }

        sections = []
        for match in matches:
            sections.append(self._build_fighter_section(match))

        if len(matches) == 2:
            comparison = self._build_comparison_section(matches[0], matches[1])
            if comparison:
                sections.append(comparison)

        return {
            "matched_fighters": [match.fighter_name for match in matches],
            "context_text": "\n\n".join(section for section in sections if section),
            "resolution_source": "local",
            "resolution_complete": len(matches) >= 2,
            "match_details": [
                {
                    "fighter_name": match.fighter_name,
                    "matched_text": match.matched_text or match.normalized_name,
                    "match_type": match.match_type,
                    "score": round(match.score, 3),
                }
                for match in matches
            ],
        }

    def match_fighters(self, tweet_text: str, limit: int = 2) -> list[FighterMatch]:
        normalized_tweet = normalize_text(tweet_text)
        exact_matches = self._exact_matches(normalized_tweet)
        if len(exact_matches) >= limit:
            return exact_matches[:limit]

        fuzzy_matches = self._fuzzy_matches(normalized_tweet)
        combined = exact_matches[:]
        seen = {match.normalized_name for match in combined}
        for match in fuzzy_matches:
            if match.normalized_name in seen:
                continue
            combined.append(match)
            seen.add(match.normalized_name)
            if len(combined) >= limit:
                break
        return combined[:limit]

    def _exact_matches(self, normalized_tweet: str) -> list[FighterMatch]:
        padded = f" {normalized_tweet} "
        indexed_matches: list[tuple[int, FighterMatch]] = []
        for alias, canonical_name in self.canonical_by_alias.items():
            if not alias:
                continue
            pattern = f" {alias} "
            index = padded.find(pattern)
            if index < 0:
                continue
            record = self.fighters_by_name[canonical_name]
            indexed_matches.append(
                (
                    index,
                    FighterMatch(
                        fighter_name=str(record["Fighter"]),
                        normalized_name=canonical_name,
                        fighter_id=str(record.get("Fighter_ID", "")).strip(),
                        score=1.0 if alias == canonical_name else 0.97,
                        row=record,
                        match_type="exact" if alias == canonical_name else "alias",
                        matched_text=alias,
                    ),
                )
            )
        indexed_matches.sort(key=lambda item: (item[0], -len(item[1].matched_text)))
        matches = [match for _, match in indexed_matches]
        return self._unique_matches(matches)

    def _fuzzy_matches(self, normalized_tweet: str) -> list[FighterMatch]:
        tokens = WORD_RE.findall(normalized_tweet)
        if len(tokens) < 2:
            return []

        candidates: list[FighterMatch] = []
        for width in (4, 3, 2):
            if len(tokens) < width:
                continue
            for index in range(len(tokens) - width + 1):
                ngram = " ".join(tokens[index : index + width])
                sorted_ngram = token_sort_text(ngram)
                for candidate_alias, canonical_name in self.aliases_by_token_count.get(width, []):
                    sequence_score = SequenceMatcher(None, ngram, candidate_alias).ratio()
                    token_sort_score = SequenceMatcher(
                        None,
                        sorted_ngram,
                        token_sort_text(candidate_alias),
                    ).ratio()
                    score = max(sequence_score, token_sort_score)
                    if score < 0.88:
                        continue
                    record = self.fighters_by_name[canonical_name]
                    candidates.append(
                        FighterMatch(
                            fighter_name=str(record["Fighter"]),
                            normalized_name=canonical_name,
                            fighter_id=str(record.get("Fighter_ID", "")).strip(),
                            score=score,
                            row=record,
                            match_type="token_sort_fuzzy"
                            if token_sort_score > sequence_score
                            else "fuzzy",
                            matched_text=ngram,
                        )
                    )
        candidates.sort(key=lambda item: (item.score, len(item.normalized_name)), reverse=True)
        return self._unique_matches(candidates)

    @staticmethod
    def _aliases_for_name(normalized_name: str) -> set[str]:
        aliases = {normalized_name}
        parts = normalized_name.split()
        if len(parts) == 2:
            aliases.add(" ".join(reversed(parts)))
        return aliases

    @staticmethod
    def _unique_matches(matches: list[FighterMatch]) -> list[FighterMatch]:
        unique = []
        seen = set()
        for match in matches:
            if match.normalized_name in seen:
                continue
            unique.append(match)
            seen.add(match.normalized_name)
        return unique

    def _build_fighter_section(self, match: FighterMatch) -> str:
        row = match.row
        recent_fights = self._last_five_fights(match)
        finish_profile = (
            f"Wins KO/Sub/Dec {int(row['Win_KO'])}/{int(row['Win_Sub'])}/{int(row['Win_Decision'])}; "
            f"Losses KO/Sub/Dec {int(row['Loss_KO'])}/{int(row['Loss_Sub'])}/{int(row['Loss_Decision'])}"
        )
        lines = [
            f"{match.fighter_name}: {int(row['Wins'])}-{int(row['Losses'])}, {row['Weight Class']}, "
            f"stance {row['Stance']}, reach {row['Reach']}, team {row['Association']}, nationality {row['Nationality']}.",
            finish_profile,
        ]
        if recent_fights:
            lines.append("Last 5 fights:")
            lines.extend(recent_fights)
        return "\n".join(lines)

    def _last_five_fights(self, match: FighterMatch) -> list[str]:
        fighter_id = match.fighter_id
        normalized_name = match.normalized_name
        event_rows = self.events[
            (self.events["fighter_1_id_str"] == fighter_id)
            | (self.events["fighter_2_id_str"] == fighter_id)
            | (self.events["normalized_fighter_1"] == normalized_name)
            | (self.events["normalized_fighter_2"] == normalized_name)
        ].head(5)

        fights = []
        for _, event in event_rows.iterrows():
            fighter_1 = normalize_text(event["Fighter 1"])
            is_fighter_1 = fighter_1 == normalized_name or event["fighter_1_id_str"] == fighter_id
            opponent = event["Fighter 2"] if is_fighter_1 else event["Fighter 1"]
            won = normalize_text(event["Winning Fighter"]) == normalized_name
            result = "W" if won else "L"
            event_date = event["event_date_dt"]
            date_text = event_date.strftime("%Y-%m-%d") if pd.notna(event_date) else str(event["Event Date"])[:10]
            fights.append(
                f"- {date_text}: {result} vs {opponent} by {event['Winning Method']} "
                f"(R{event['Winning Round']} {event['Winning Time']}) at {event['Event Name']}"
            )
        return fights

    def _build_comparison_section(self, first: FighterMatch, second: FighterMatch) -> str:
        head_to_head = self.events[
            (
                (self.events["normalized_fighter_1"] == first.normalized_name)
                & (self.events["normalized_fighter_2"] == second.normalized_name)
            )
            | (
                (self.events["normalized_fighter_1"] == second.normalized_name)
                & (self.events["normalized_fighter_2"] == first.normalized_name)
            )
        ].head(3)

        first_record = first.row
        second_record = second.row
        lines = [
            f"Comparison: {first.fighter_name} is {int(first_record['Wins'])}-{int(first_record['Losses'])}; "
            f"{second.fighter_name} is {int(second_record['Wins'])}-{int(second_record['Losses'])}.",
        ]
        if head_to_head.empty:
            lines.append("Head-to-head: no prior meeting found in local event data.")
        else:
            lines.append("Head-to-head:")
            for _, fight in head_to_head.iterrows():
                lines.append(
                    f"- {fight['Event Name']}: winner {fight['Winning Fighter']} by {fight['Winning Method']}"
                )
        return "\n".join(lines)
