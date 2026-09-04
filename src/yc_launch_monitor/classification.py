from __future__ import annotations

from dataclasses import replace
import re

from .domain import Signal, SignalStatus


_YC_PROGRAM = r"(?:yc|y combinator)"
_SPEEDRUN_PROGRAM = r"(?:(?:@?a16z\s+)?@?speedrun)"

_YC_PATTERNS = (
    rf"\baccepted (?:in|into|to) {_YC_PROGRAM}\b",
    rf"\bjoin(?:ed|ing)? {_YC_PROGRAM}\b",
    rf"\bgot into {_YC_PROGRAM}\b",
    r"\bwe(?:'re| are) (?:a )?y combinator company\b",
    r"\byc\s+(?:s|w|f)\d{2}\b",
)
_SPEEDRUN_PATTERNS = (
    rf"\baccepted (?:in|into|to) {_SPEEDRUN_PROGRAM}\b",
    rf"\bjoin(?:ed|ing)? {_SPEEDRUN_PROGRAM}\b",
    rf"\bgot into {_SPEEDRUN_PROGRAM}\b",
    r"\bsr\d{3}\b",
)
_DISCUSSION = re.compile(
    r"\b(?:discuss(?:ion|ing)?|thoughts?\s+(?:about|on)|trend|why do|how do|news about|congrats to)\b",
    re.I,
)
_META_MONITORING = re.compile(
    r"\b(?:want to know which|which startup founders?|founders?\s+(?:say|saying)|find founders?|monitor(?:ing)?)\b",
    re.I,
)
_HISTORICAL_CONTEXT = re.compile(
    r"\b(?:remember(?:ing)?\s+when|before\s+(?:i|we)|after\s+(?:i|we)|back\s+in\s+\d{4}|(?:months?|years?)\s+ago)\b"
    r".{0,140}\b(?:accepted|got into|join(?:ed|ing))\b",
    re.I | re.S,
)
_NEGATED_ACCEPTANCE = re.compile(
    r"\b(?:not|never|haven't|hasn't|hadn't|wasn't|weren't|didn't)\b.{0,35}\b(?:accepted|got into|joining|joined)\b",
    re.I,
)
_REJECTION = re.compile(
    r"\b(?:reject(?:ed|ion)|did(?:n't| not) make it|did(?:n't| not) get in|not selected|turned down|no from (?:yc|y combinator|speedrun))\b",
    re.I,
)
_SELF_ANNOUNCEMENT = re.compile(
    rf"(?:"
    rf"\b(?:i|we)(?:(?:'ve|'re|'d)|\s+(?:have|are|had|was|were))?\s+"
    rf"(?:just\s+)?(?:been\s+)?"
    rf"(?:accepted\s+(?:in|into|to)\s+(?:{_YC_PROGRAM}|{_SPEEDRUN_PROGRAM})"
    rf"|got\s+into\s+(?:{_YC_PROGRAM}|{_SPEEDRUN_PROGRAM})"
    rf"|join(?:ed|ing)\s+(?:{_YC_PROGRAM}|{_SPEEDRUN_PROGRAM}))"
    r"|\b(?:excited|thrilled|happy)\s+to\s+(?:announce|share)\b.{0,180}"
    r"(?:accepted\s+(?:in|into|to)|join(?:ed|ing)|got\s+into).{0,50}"
    r"(?:yc|y combinator|@?speedrun)"
    r")",
    re.I | re.S,
)
_COMPANY_PATTERNS = (
    r"\b(?:all[- ]in|working)\s+on\s+([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3})\s*\(\s*YC\s+[SWF]\d{2}\s*\)",
    r"\b(?:building|launching|working on)\s+(@[A-Za-z0-9_]{2,30})\b",
)


def normalize_company(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _infer_company_name(text: str) -> str | None:
    for pattern in _COMPANY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" .,-")
    return None


def classify_social_signal(
    item: Signal,
    *,
    yc_company_names: set[str] | None = None,
    speedrun_company_names: set[str] | None = None,
) -> Signal:
    text = item.text.strip()
    lowered = text.lower()
    if normalize_company(item.company_name) in {"", "unknown company"}:
        inferred = _infer_company_name(text)
        if inferred:
            item = replace(item, company_name=inferred)
    company = normalize_company(item.company_name)
    yc_names = {normalize_company(name) for name in (yc_company_names or set())}
    speedrun_names = {normalize_company(name) for name in (speedrun_company_names or set())}

    if company and company in yc_names:
        return replace(item, status=SignalStatus.CONFIRMED_YC, program="Y Combinator", confidence=0.98)
    if company and company in speedrun_names:
        return replace(item, status=SignalStatus.CONFIRMED_SPEEDRUN, program="a16z Speedrun", confidence=0.98)

    yc_match = any(re.search(pattern, lowered, re.I) for pattern in _YC_PATTERNS)
    speedrun_match = any(re.search(pattern, lowered, re.I) for pattern in _SPEEDRUN_PATTERNS)
    discussion = bool(_DISCUSSION.search(text) or _META_MONITORING.search(text))
    historical = bool(_HISTORICAL_CONTEXT.search(text))
    negated = bool(_NEGATED_ACCEPTANCE.search(text))
    rejection = bool(_REJECTION.search(text))
    self_announcement = bool(_SELF_ANNOUNCEMENT.search(lowered.replace("’", "'")))
    is_reply = text.lstrip().startswith("@")

    if (
        self_announcement
        and not is_reply
        and not discussion
        and not historical
        and not negated
        and not rejection
        and (yc_match or speedrun_match)
    ):
        program = "a16z Speedrun" if speedrun_match and not yc_match else "Y Combinator"
        confidence = 0.86 if re.search(r"accepted|got into|join", lowered) else 0.8
        return replace(item, status=SignalStatus.EARLY_SIGNAL, program=program, confidence=confidence)
    return replace(item, status=SignalStatus.NEEDS_REVIEW, confidence=0.25 if yc_match or speedrun_match else 0.1)
