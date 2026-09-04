from __future__ import annotations

from datetime import UTC, datetime
from html.parser import HTMLParser
import json
import re
import time
from typing import Any
from urllib.parse import urlparse

from .domain import CollectorHealth, CollectorResult, Signal, SignalStatus, Source
from .http import HttpError


def _safe_diagnostic(exc: Exception) -> str:
    return f"{type(exc).__name__}: collector request or parsing failed"


def _dedupe(items: list[Signal]) -> list[Signal]:
    return list({item.key: item for item in items}.values())


def _has_allowed_host(url: str, allowed_hosts: set[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def _extract_company_name(text: str) -> str:
    patterns = (
        r"\bannounce(?:\s+that)?\s+(@?[A-Za-z][A-Za-z0-9_.-]{1,40})\s+(?:will\s+be|is)\s+joining\b",
        r"\b(?:build(?:ing)?|launch(?:ing)?|start(?:ing)?|working on)\s+(@[A-Za-z0-9_]{2,30})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return "Unknown company"


class YCDirectoryCollector:
    name = Source.YC_DIRECTORY
    page_url = "https://www.ycombinator.com/companies"

    def __init__(self, transport, limit: int = 50):
        self.transport = transport
        self.limit = limit

    def collect(self) -> CollectorResult:
        try:
            html = self.transport.get_text(self.page_url)
            match = re.search(r"window\.AlgoliaOpts\s*=\s*(\{.*?\})\s*;", html, re.S)
            if not match:
                raise ValueError("Public Algolia configuration not found")
            config = json.loads(match.group(1))
            app_id = config.get("app") or config.get("appId") or config.get("applicationId")
            api_key = config.get("key") or config.get("apiKey") or config.get("searchApiKey")
            if not app_id or not api_key:
                raise ValueError("Incomplete public Algolia configuration")
            endpoint = f"https://{str(app_id).lower()}-dsn.algolia.net/1/indexes/YCCompany_By_Launch_Date_production/query"
            payload = {"params": f"hitsPerPage={self.limit}&page=0"}
            data = self.transport.post_json(
                endpoint,
                payload,
                headers={"X-Algolia-Application-Id": app_id, "X-Algolia-API-Key": api_key},
            )
            signals = []
            for hit in data.get("hits", []):
                slug = str(hit.get("slug") or hit.get("id") or hit.get("objectID") or "").strip()
                if not slug:
                    continue
                launched = hit.get("launched_at")
                occurred = datetime.fromtimestamp(launched, UTC).isoformat() if isinstance(launched, (int, float)) else None
                signals.append(Signal(
                    source=self.name,
                    source_id=slug,
                    source_url=f"https://www.ycombinator.com/companies/{slug}",
                    company_name=str(hit.get("name") or slug),
                    text=str(hit.get("one_liner") or hit.get("long_description") or "New YC Directory listing"),
                    program="Y Combinator",
                    batch_or_cohort=str(hit.get("batch") or ""),
                    occurred_at=occurred,
                    status=SignalStatus.CONFIRMED_YC,
                    confidence=1.0,
                    metadata={"website": hit.get("website"), "regions": hit.get("regions", [])},
                ))
            if not signals:
                raise ValueError("YC Directory returned no company records")
            return CollectorResult(self.name, CollectorHealth.ACTIVE, signals)
        except Exception as exc:
            return CollectorResult(self.name, CollectorHealth.DEGRADED, diagnostic=_safe_diagnostic(exc))


class _NextDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.content: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("id") == "__NEXT_DATA__":
            self.capture = True

    def handle_endtag(self, tag):
        if tag == "script" and self.capture:
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.content.append(data)


def _find_companies(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        candidate = value.get("companies")
        if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
            return candidate
        if isinstance(candidate, dict):
            results = candidate.get("results")
            if isinstance(results, list) and all(isinstance(item, dict) for item in results):
                return results
        for nested in value.values():
            found = _find_companies(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_companies(nested)
            if found:
                return found
    return []


class SpeedrunCollector:
    """Collects a16z Speedrun companies; Speedrun is not a YC program."""

    name = Source.SPEEDRUN
    page_url = "https://speedrun.a16z.com/companies"

    def __init__(self, transport):
        self.transport = transport

    def collect(self) -> CollectorResult:
        try:
            parser = _NextDataParser()
            parser.feed(self.transport.get_text(self.page_url))
            if not parser.content:
                raise ValueError("Next.js data not found")
            companies = _find_companies(json.loads("".join(parser.content)))
            signals = []
            for company in companies:
                source_id = str(company.get("id") or company.get("slug") or "").strip()
                if not source_id:
                    continue
                founders = company.get("founder_set") or []
                founder_name = ", ".join(
                    " ".join(filter(None, [str(f.get("first_name") or ""), str(f.get("last_name") or "")])).strip()
                    for f in founders if isinstance(f, dict)
                )
                slug = str(company.get("slug") or source_id)
                signals.append(Signal(
                    source=self.name,
                    source_id=source_id,
                    source_url=f"https://speedrun.a16z.com/companies/{slug}",
                    company_name=str(company.get("name") or slug),
                    founder_name=founder_name,
                    text=str(company.get("preamble") or company.get("description") or "New Speedrun company"),
                    program="a16z Speedrun",
                    batch_or_cohort=str(company.get("cohort") or ""),
                    status=SignalStatus.CONFIRMED_SPEEDRUN,
                    confidence=1.0,
                    metadata={
                        "program_owner": "a16z",
                        "website": company.get("website_url"),
                        "x_url": company.get("x_url"),
                        "linkedin_url": company.get("linkedin_url"),
                    },
                ))
            if not signals:
                raise ValueError("a16z Speedrun returned no company records")
            return CollectorResult(self.name, CollectorHealth.ACTIVE, signals)
        except Exception as exc:
            return CollectorResult(self.name, CollectorHealth.DEGRADED, diagnostic=_safe_diagnostic(exc))


class XCollector:
    name = Source.X
    endpoint = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    queries = (
        '("accepted into YC" OR "accepted to YC" OR "joining YC" OR "got into YC" OR "accepted into Y Combinator" OR "got into Y Combinator") -filter:retweets lang:en',
        '("accepted into Speedrun" OR "accepted to Speedrun" OR "joining a16z Speedrun" OR "joining @speedrun" OR "got into Speedrun" OR "got into @speedrun") -filter:retweets lang:en',
    )

    def __init__(
        self,
        transport,
        api_key: str,
        queries: tuple[str, ...] | None = None,
        *,
        sleep=time.sleep,
    ):
        self.transport = transport
        self.api_key = api_key.strip()
        self.queries = queries or type(self).queries
        self.sleep = sleep

    def _search(self, query: str) -> dict[str, Any]:
        def request() -> dict[str, Any]:
            return self.transport.get_json(
                self.endpoint,
                headers={"X-API-Key": self.api_key, "Accept": "application/json"},
                params={"query": query, "queryType": "Latest"},
            )

        try:
            return request()
        except HttpError as exc:
            if exc.status_code != 429:
                raise
            self.sleep(max(2.0, exc.retry_after or 0.0))
        return request()

    def collect(self) -> CollectorResult:
        if not self.api_key:
            return CollectorResult(self.name, CollectorHealth.NOT_CONFIGURED, diagnostic="TWITTERAPIIO_API_KEY is not configured")
        signals = []
        failures: list[str] = []
        for index, query in enumerate(self.queries):
            if index:
                self.sleep(6.0)
            try:
                data = self._search(query)
                if not isinstance(data, dict):
                    raise ValueError("X response is not an object")
                nested = data.get("data")
                nested_tweets = nested.get("tweets") if isinstance(nested, dict) else None
                tweets = data.get("tweets") or nested_tweets or []
                if not isinstance(tweets, list):
                    raise ValueError("X tweets field is not a list")
                for tweet in tweets:
                    if not isinstance(tweet, dict):
                        continue
                    author = tweet.get("author")
                    if not isinstance(author, dict):
                        author = {}
                    source_id = str(tweet.get("id") or tweet.get("tweet_id") or "").strip()
                    if not source_id:
                        continue
                    username = str(author.get("userName") or author.get("username") or "")
                    url = f"https://x.com/{username}/status/{source_id}" if username else f"https://x.com/i/status/{source_id}"
                    text = str(tweet.get("text") or "")
                    signals.append(Signal(
                        source=self.name,
                        source_id=source_id,
                        source_url=str(url),
                        company_name=str(tweet.get("company") or _extract_company_name(text)),
                        founder_name=str(author.get("name") or username),
                        text=text,
                        occurred_at=tweet.get("createdAt") or tweet.get("created_at"),
                        metadata={"username": username},
                    ))
            except Exception as exc:
                failures.append(type(exc).__name__)
        health = CollectorHealth.DEGRADED if failures else CollectorHealth.ACTIVE
        diagnostic = f"{len(failures)} of {len(self.queries)} X queries failed ({', '.join(sorted(set(failures)))})" if failures else ""
        return CollectorResult(self.name, health, _dedupe(signals), diagnostic)


class LinkedInCollector:
    name = Source.LINKEDIN
    endpoint = "https://api.search.tinyfish.ai"
    queries = (
        'site:linkedin.com/posts ("accepted into Y Combinator" OR "joining YC" OR "YC S26")',
        'site:linkedin.com/posts ("accepted into Speedrun" OR "joining a16z Speedrun" OR "SR006")',
    )

    def __init__(self, transport, api_key: str, queries: tuple[str, ...] | None = None):
        self.transport = transport
        self.api_key = api_key.strip()
        self.queries = queries or type(self).queries

    def collect(self) -> CollectorResult:
        if not self.api_key:
            return CollectorResult(self.name, CollectorHealth.NOT_CONFIGURED, diagnostic="TINYFISH_API_KEY is not configured")
        try:
            signals = []
            for query in self.queries:
                data = self.transport.get_json(
                    self.endpoint,
                    headers={"X-API-Key": self.api_key},
                    params={"query": query},
                )
                for result in data.get("results", []):
                    url = str(result.get("url") or "")
                    if not url or not _has_allowed_host(url, {"linkedin.com"}):
                        continue
                    source_id = urlparse(url).path.strip("/") or url
                    title = str(result.get("title") or "LinkedIn announcement")
                    signals.append(Signal(
                        source=self.name,
                        source_id=source_id,
                        source_url=url,
                        company_name="Unknown company",
                        founder_name=title.split(" on LinkedIn", 1)[0],
                        text=str(result.get("snippet") or title),
                        metadata={"search_title": title},
                    ))
            return CollectorResult(self.name, CollectorHealth.ACTIVE, _dedupe(signals))
        except Exception as exc:
            return CollectorResult(self.name, CollectorHealth.DEGRADED, diagnostic=_safe_diagnostic(exc))
