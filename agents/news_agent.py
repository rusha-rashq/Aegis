"""
News Intelligence Agent
========================

Role in the Multi-Agent System
-------------------------------
This module is a COLLABORATOR agent in the Amazon Bedrock multi-agent
collaboration framework. It sits in the parallel intelligence layer:

    ┌─────────────────────────────────────┐
    │         Market Stress Agent          │
    │              (CMSI)                  │
    └────────────────┬────────────────────┘
                     │ Stress State
         ┌───────────┴───────────┐
         ▼                       ▼
  ┌─────────────┐      ┌──────────────────┐
  │ News Agent  │      │ Historical Analog │
  │ (this file) │      │     Agent         │
  └──────┬──────┘      └────────┬─────────┘
         └──────────┬───────────┘
                    ▼
          Signal Fusion Agent
                    │
                    ▼
         Risk Interpretation Agent (Nova)
                    │
                    ▼
          Hedging Strategy Agent

Bedrock Collaboration Model
-----------------------------
This agent is registered in Bedrock with agentCollaboration = COLLABORATOR.
The Signal Fusion Agent (supervisor) invokes it via invoke_agent() in
PARALLEL with the Historical Analog Agent.

The agent exposes three action groups backed by Lambda functions:
  1. fetch_and_filter_news    -> fetches from Tier 1 + Tier 2 sources
  2. classify_articles        -> Nova-based per-article classification
  3. summarise_news_signals   -> produces NewsSummary for Signal Fusion

For local development / unit testing, call run_news_agent() directly.

Source Tiers
------------
Tier 1 — Real-time wire services (NewsAPI)
    Reuters, Bloomberg, Associated Press, BBC News, Financial Times,
    Wall Street Journal, The Guardian, CNBC,
    S&P Global Commodity Insights, Argus Media, ICIS

Tier 2 — Institutional research commentary (web-scraped public pages)
    J.P. Morgan Global Research
        https://www.jpmorgan.com/insights/global-research
    Goldman Sachs Insights
        https://www.goldmansachs.com/insights
    BlackRock Investment Institute
        https://www.blackrock.com/corporate/insights/blackrock-investment-institute
    UBS Chief Investment Office
        https://www.ubs.com/global/en/wealthmanagement/insights/chief-investment-office
    Morgan Stanley Research (public commentary)
        https://www.morganstanley.com/ideas
    Vanguard Economic & Market Outlook
        https://corporate.vanguard.com/content/corporatesite/us/en/corp/articles-insights.html

    ACCESS MODEL NOTE:
    None of these institutions publish real-time public APIs or RSS feeds.
    Full research (e.g. Goldman Sachs Commodity Views, JPM Global
    Commodities Strategy, BlackRock Global Insights, UBS CIO Daily)
    requires Bloomberg Terminal or authenticated client portal access.
    This module scrapes PUBLIC insights pages only — it does not bypass
    authentication or reproduce paywalled research. If your organisation
    has Bloomberg or JPM Markets access, replace Tier 2 scraping with
    the appropriate authenticated feed.

Research Foundations
---------------------
Caldara, D. and Iacoviello, M. (2022). "Measuring Geopolitical Risk."
    American Economic Review, 112(4), 1194-1225.
    DOI: 10.1257/aer.20191823

Baker, S.R., Bloom, N. and Davis, S.J. (2016). "Measuring Economic
    Policy Uncertainty." The Quarterly Journal of Economics, 131(4),
    1593-1636. DOI: 10.1093/qje/qjw024

Kilian, L. (2014). "Oil Price Shocks: Causes and Consequences."
    Annual Review of Resource Economics, 6(1), 133-154.
    DOI: 10.1146/annurev-resource-083013-114701
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import boto3
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

NEWSAPI_URL = "https://newsapi.org/v2/everything"
NOVA_MODEL_ID = "amazon.nova-pro-v1:0"
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Minimum filtered article count for reliable frequency-share scores.
# Below this threshold, score reliability is flagged False.
# (Calibrated against Caldara-Iacoviello (2022) minimum corpus guidance.)
MIN_ARTICLES_FOR_RELIABLE_SCORE = 15

# Max parallel Nova classification calls.
# Keeps Bedrock invocation rate within service limits.
MAX_CLASSIFICATION_WORKERS = 5

# HTTP timeout for all external requests (seconds)
REQUEST_TIMEOUT = 20

# -------------------------------------------------------------------
# Bedrock client
# -------------------------------------------------------------------

bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# -------------------------------------------------------------------
# Tier 1: Trusted wire service sources
#
# Filtered by BOTH source_id AND source_name because NewsAPI frequently
# returns source.id = null for Reuters, Bloomberg, FT, and WSJ even
# when source.name is correct. Filtering on ID alone silently drops
# legitimate institutional articles.
#
# Source selection rationale:
#   Reuters, Bloomberg, AP    : Primary real-time financial wires used
#                               by trading desks globally
#   FT, WSJ                   : Institutional-quality financial press
#   BBC, Guardian, CNBC       : Broad geopolitical coverage
#   S&P Global Commodity
#     Insights (Platts)       : Industry standard for energy/ag pricing
#   Argus Media               : Industry standard for energy/commodities
#   ICIS                      : Industry standard for petrochemicals
# -------------------------------------------------------------------

TRUSTED_SOURCE_IDS = {
    "reuters",
    "bloomberg",
    "associated-press",
    "bbc-news",
    "financial-times",
    "the-wall-street-journal",
    "the-guardian-uk",
    "cnbc",
    "the-hill",          # add
    "axios",             # add
}

TRUSTED_SOURCE_NAMES = {
    "reuters",
    "bloomberg",
    "associated press",
    "bbc news",
    "financial times",
    "wall street journal",
    "the guardian",
    "cnbc",
    "s&p global commodity insights",
    "argus media",
    "icis",
    "eia",               # add — US Energy Information Administration
    "usda",              # add — US Dept of Agriculture crop reports
    "the hill",          # add
    "axios",             # add
    "dow jones",         # add
}
# -------------------------------------------------------------------
# Tier 2: Institutional research public pages
#
# These are the publicly accessible insights pages for each institution.
# Headlines and summaries are scraped; no paywalled content is accessed.
# Full research requires Bloomberg Terminal or authenticated portals.
# -------------------------------------------------------------------

INSTITUTIONAL_SOURCES: List[Dict[str, str]] = [
    {
        "name": "J.P. Morgan Global Research",
        "url": "https://www.jpmorgan.com/insights/global-research",
        "tier": "institutional",
    },
    {
        "name": "Goldman Sachs Insights",
        "url": "https://www.goldmansachs.com/insights",
        "tier": "institutional",
    },
    {
        "name": "BlackRock Investment Institute",
        "url": "https://www.blackrock.com/corporate/insights/blackrock-investment-institute",
        "tier": "institutional",
    },
    {
        "name": "UBS Chief Investment Office",
        "url": "https://www.ubs.com/global/en/wealthmanagement/insights/chief-investment-office.html",
        "tier": "institutional",
    },
    {
        "name": "Morgan Stanley Research",
        "url": "https://www.morganstanley.com/ideas",
        "tier": "institutional",
    },
    {
        "name": "Vanguard Economic & Market Outlook",
        "url": "https://corporate.vanguard.com/content/corporatesite/us/en/corp/articles-insights.html",
        "tier": "institutional",
    },
]

# -------------------------------------------------------------------
# NewsAPI query
# Covers all 8 Caldara-Iacoviello GPR event categories plus
# commodity-specific supply-chain terms.
# -------------------------------------------------------------------

# NewsAPI enforces a 500-character limit on the q parameter.
# The full keyword set exceeds this, so it is split across two queries
# that are each fetched separately and merged in fetch_wire_news().

# Query A: geopolitical / supply-chain disruption terms (~430 chars)
DEFAULT_QUERY_A = (
    '(war OR invasion OR missile OR sanctions OR embargo OR '
    '"strait of hormuz" OR "red sea" OR "black sea" OR suez OR '
    'opec OR pipeline OR refinery OR "export ban" OR '
    '"grain corridor" OR ceasefire OR "peace talks" OR '
    'coup OR blockade OR "drone attack" OR nuclear)'
)

# Query B: US macro, energy policy, agriculture, and dollar terms (~430 chars)
DEFAULT_QUERY_B = (
    '("federal reserve" OR "interest rates" OR "US inflation" OR '
    '"SPR" OR "strategic petroleum reserve" OR '
    '"US energy" OR "US sanctions" OR "US tariffs" OR '
    '"gulf of mexico" OR "permian basin" OR shale OR '
    'USDA OR "US crop" OR "US wheat" OR "US corn" OR "farm bill" OR '
    '"dollar index" OR DXY OR "US treasury" OR "fed funds")'
)

DEFAULT_QUERIES = [DEFAULT_QUERY_A, DEFAULT_QUERY_B]

# -------------------------------------------------------------------
# Allowed vocabularies for Nova classification output validation
# -------------------------------------------------------------------

ALLOWED_BUCKETS = {
    "war_conflict",
    "shipping_disruption",
    "sanctions_trade",
    "opec_policy",
    "energy_infrastructure",
    "export_restriction",
    "deescalation",
    "institutional_view",   # For Tier 2 institutional commentary
    "other",
}

# Commodity universe — exactly five tradeable markets tracked by this system.
# Tickers are Yahoo Finance futures symbols used by the Market Data Agent
# and CMSI to pull real-time price data. Any commodity Nova returns that
# is NOT in this dict is invalid and will be replaced with "None".
# Keeping this list short and exact also reduces Nova hallucination risk —
# a shorter allowed list means fewer wrong answers to choose from.
COMMODITY_TICKERS: Dict[str, str] = {
    "Oil":         "CL=F",   # WTI Crude Oil front-month futures
    "Gold":        "GC=F",   # Gold front-month futures
    "Wheat":       "ZW=F",   # CBOT Wheat front-month futures
    "Copper":      "HG=F",   # Copper front-month futures
    "Natural Gas": "NG=F",   # Henry Hub Natural Gas front-month futures
}

# Set used for O(1) validation of Nova classification output.
# "None" is the explicit fallback when no tracked commodity is affected.
ALLOWED_COMMODITIES = set(COMMODITY_TICKERS.keys()) | {"None"}

RELEVANCE_RANK = {"high": 3, "medium": 2, "low": 1}


# -------------------------------------------------------------------
# Data models
# -------------------------------------------------------------------

@dataclass
class RawArticle:
    article_id: str
    title: str
    description: str
    content: str
    source_id: str
    source_name: str
    source_tier: str       # "wire" | "institutional"
    url: str
    published_at: str


@dataclass
class ClassifiedArticle:
    article_id: str
    title: str
    source_id: str
    source_name: str
    source_tier: str
    url: str
    published_at: str
    bucket: str
    region: str
    countries_involved: List[str]
    affected_commodities: List[str]
    threat_or_act: str
    relevance: str
    confidence: float
    rationale: str
    is_deescalation: bool
    classification_error: Optional[str] = None


@dataclass
class NewsSummary:
    n_articles_fetched: int
    n_articles_retained: int
    n_articles_classified: int
    n_institutional: int
    n_wire: int
    bucket_counts: Dict[str, int]
    commodity_counts: Dict[str, int]
    source_counts: Dict[str, int]
    risk_bias: str                          # "elevated" | "easing" | "neutral"
    risk_bias_weighted_score: float         # Continuous score for Signal Fusion
    low_sample_warning: bool
    # Full commodity->ticker mapping passed to Signal Fusion and Market Data
    # Agent so they never need a separate lookup. Always the same five entries.
    commodity_tickers: Dict[str, str] = field(default_factory=dict)
    top_headlines: List[Dict[str, Any]] = field(default_factory=list)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _make_article_id(title: str, url: str) -> str:
    raw = f"{title.strip()}|{url.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _normalize_text(text: Optional[str]) -> str:
    return (text or "").strip()


def _clean_newsapi_content(text: str) -> str:
    """
    Strip the NewsAPI [+N chars] truncation artefact before passing
    content to Nova. Leaving it in causes Nova to treat the artefact
    as meaningful text.
    """
    return re.sub(r"\s*\[\+\d+ chars\]\s*$", "", text).strip()


def _deduplicate_articles(articles: List[RawArticle]) -> List[RawArticle]:
    seen: set = set()
    deduped: List[RawArticle] = []
    for article in articles:
        key = (article.title.lower().strip(), article.url.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    return deduped


def _is_trusted_wire_source(source_id: str, source_name: str) -> bool:
    """
    Check BOTH source_id and source_name.

    NewsAPI returns source.id = null for many institutional publishers
    including Reuters, Bloomberg, FT, and WSJ. Checking only source_id
    would silently drop the majority of trusted articles.
    """
    if (source_id or "").strip().lower() in TRUSTED_SOURCE_IDS:
        return True
    return (source_name or "").strip().lower() in TRUSTED_SOURCE_NAMES


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _risk_weight(article: ClassifiedArticle) -> float:
    """
    Weight an article by relevance tier and Nova confidence score.
    Used for risk_bias computation to avoid raw count comparisons.

    A single high-confidence invasion article outweighs ten
    low-confidence OPEC policy articles — which is the correct
    financial behaviour.
    """
    relevance_multiplier = RELEVANCE_RANK.get(article.relevance, 0.5)
    return relevance_multiplier * article.confidence


# -------------------------------------------------------------------
# Tier 1: Fetch wire news via NewsAPI
# -------------------------------------------------------------------

def _fetch_wire_news_single(
    api_key: str,
    query: str,
    from_iso: str,
    page_size: int,
    language: str,
) -> List[RawArticle]:
    """
    Internal helper: run one NewsAPI request and return trusted RawArticles.
    NewsAPI enforces a 500-character limit on the q parameter — callers are
    responsible for ensuring each query fits within that limit.
    """
    params = {
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": min(page_size, 100),
        "from": from_iso,
        "apiKey": api_key,
    }

    response = requests.get(NEWSAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    payload = response.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {payload}")

    results: List[RawArticle] = []
    for item in payload.get("articles", []):
        source = item.get("source") or {}
        title = _normalize_text(item.get("title"))
        url = _normalize_text(item.get("url"))

        if not title or not url:
            continue

        source_id = _normalize_text(source.get("id"))
        source_name = _normalize_text(source.get("name"))

        if not _is_trusted_wire_source(source_id, source_name):
            continue

        results.append(RawArticle(
            article_id=_make_article_id(title, url),
            title=title,
            description=_normalize_text(item.get("description")),
            content=_clean_newsapi_content(_normalize_text(item.get("content"))),
            source_id=source_id,
            source_name=source_name,
            source_tier="wire",
            url=url,
            published_at=_normalize_text(item.get("publishedAt")),
        ))

    return results


def fetch_wire_news(
    api_key: Optional[str] = None,
    queries: List[str] = None,
    days_back: int = 3,
    page_size: int = 50,
    language: str = "en",
) -> List[RawArticle]:
    """
    Fetch recent geopolitical and commodity headlines from NewsAPI,
    filtered to trusted institutional wire sources.

    NewsAPI enforces a 500-character limit on the ``q`` parameter. The full
    keyword set exceeds this limit, so it is split across DEFAULT_QUERY_A and
    DEFAULT_QUERY_B (see module constants). Both queries are run in parallel
    and their results are merged and deduplicated before being returned.

    Parameters
    ----------
    api_key   : NewsAPI key (falls back to NEWS_API_KEY env var)
    queries   : list of NewsAPI q strings, each ≤ 500 chars;
                defaults to DEFAULT_QUERIES (the two-part split)
    days_back : lookback window in days
    page_size : max articles to request per query (NewsAPI cap: 100)
    language  : ISO 639-1 language code

    Returns
    -------
    List[RawArticle] — deduplicated, trusted-source-only wire articles
    """
    api_key = api_key or os.getenv("NEWS_API_KEY")
    if not api_key:
        raise ValueError("Missing NEWS_API_KEY environment variable.")

    if queries is None:
        queries = DEFAULT_QUERIES

    now = datetime.now(timezone.utc)
    from_iso = (now - timedelta(days=days_back)).isoformat()

    all_results: List[RawArticle] = []
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        futures = {
            executor.submit(
                _fetch_wire_news_single,
                api_key, q, from_iso, page_size, language
            ): q
            for q in queries
        }
        for future in as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception as exc:
                logger.warning("NewsAPI query failed: %s — %s", futures[future], exc)

    return _deduplicate_articles(all_results)


# -------------------------------------------------------------------
# Tier 2: Scrape institutional research public pages
# -------------------------------------------------------------------

def _scrape_institutional_page(source: Dict[str, str]) -> List[RawArticle]:
    """
    Scrape the public insights page of an institutional research publisher.

    Extracts article titles and descriptions from anchor tags, headings,
    and paragraph elements. This is a best-effort extraction — page
    structure varies across institutions and may change without notice.

    Only publicly visible content is scraped. Paywalled or
    authenticated content is not accessed.

    Parameters
    ----------
    source : dict with keys 'name', 'url', 'tier'

    Returns
    -------
    List[RawArticle] — scraped articles from this institution
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; CommodityRiskBot/1.0; "
            "+https://your-org-domain.com/bot)"
        )
    }

    try:
        response = requests.get(
            source["url"], headers=headers, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", source["name"], exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles: List[RawArticle] = []
    seen_titles: set = set()

    # Extract from anchor tags with descriptive text (length > 30 chars)
    for tag in soup.find_all(["a", "h2", "h3", "h4"]):
        title = _normalize_text(tag.get_text())

        if len(title) < 30 or title.lower() in seen_titles:
            continue

        # Skip nav/footer noise
        if any(skip in title.lower() for skip in [
            "cookie", "privacy", "terms", "sign in", "log in",
            "subscribe", "newsletter", "contact us", "about us"
        ]):
            continue

        seen_titles.add(title.lower())

        # Attempt to extract sibling or child description text
        description = ""
        sibling = tag.find_next_sibling("p")
        if sibling:
            description = _normalize_text(sibling.get_text())[:300]

        # Build absolute URL if href present
        href = tag.get("href", "")
        article_url = urljoin(source["url"], href) if href else source["url"]

        articles.append(RawArticle(
            article_id=_make_article_id(title, article_url),
            title=title,
            description=description,
            content="",   # Full content requires authenticated access
            source_id=source["name"].lower().replace(" ", "-"),
            source_name=source["name"],
            source_tier="institutional",
            url=article_url,
            published_at=datetime.now(timezone.utc).isoformat(),
        ))

        if len(articles) >= 10:  # Cap per institution to control volume
            break

    logger.info("Scraped %d articles from %s", len(articles), source["name"])
    return articles


def fetch_institutional_news() -> List[RawArticle]:
    """
    Fetch public commentary from all Tier 2 institutional sources in parallel.

    Uses ThreadPoolExecutor to scrape all institutions concurrently,
    reducing total latency from ~sum(timeouts) to ~max(timeout).

    Returns
    -------
    List[RawArticle] — deduplicated institutional articles
    """
    all_articles: List[RawArticle] = []

    with ThreadPoolExecutor(max_workers=len(INSTITUTIONAL_SOURCES)) as executor:
        futures = {
            executor.submit(_scrape_institutional_page, source): source["name"]
            for source in INSTITUTIONAL_SOURCES
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                all_articles.extend(future.result())
            except Exception as exc:
                logger.warning("Institutional scrape failed for %s: %s", name, exc)

    return _deduplicate_articles(all_articles)


# -------------------------------------------------------------------
# Nova classification
# -------------------------------------------------------------------

def _build_classification_prompt(article: RawArticle) -> str:
    tier_note = (
        "This article is from an institutional research publisher "
        "(bank, asset manager, or investment house). Classify the "
        "market view or research signal it represents."
        if article.source_tier == "institutional"
        else "This article is from a real-time wire service."
    )

    return f"""
You are a commodity-market geopolitical news classifier.

{tier_note}

Classify the article into exactly ONE bucket relevant to commodity markets.

Allowed buckets:
  war_conflict          - armed conflict, military strikes, invasions
  shipping_disruption   - blockades, Red Sea, Hormuz, Suez, piracy
  sanctions_trade       - sanctions, trade wars, export bans, embargoes
  opec_policy           - OPEC+ production decisions, quota changes
  energy_infrastructure - pipeline, refinery, grid attacks/outages
  export_restriction    - unilateral export bans, grain corridor disruption
  deescalation          - ceasefire, peace talks, sanctions lifted
  institutional_view    - bank/asset manager market outlook or forecast
  other                 - not relevant to commodity markets

Tracked commodities — use ONLY these exact strings, nothing else:
  Oil, Natural Gas, Wheat, Copper, Gold, None

  Oil         = crude oil (WTI/Brent)
  Natural Gas = Henry Hub natural gas
  Wheat       = CBOT wheat
  Copper      = LME/COMEX copper
  Gold        = spot/futures gold
  None        = use this if the article does not clearly affect any of the above

  Do NOT use: LNG, Corn, Soybeans, Aluminum, Coal, Freight, or any other commodity.
  If you think LNG is affected, map it to Natural Gas.
  If you think food commodities are affected, map to Wheat if applicable, else None.

Allowed threat_or_act values:
  threat    - potential or anticipated event
  act       - confirmed/realized event
  neutral   - institutional view or de-escalation

Allowed relevance values:
  high    - direct supply or price impact, near-term
  medium  - indirect or uncertain impact
  low     - tangential or very uncertain relevance

Rules:
  1. Return valid JSON only — no preamble, no markdown fences.
  2. Use exactly one bucket from the allowed list.
  3. Only include commodities from the allowed list.
  4. If no commodity is clearly affected, use ["None"].
  5. Rationale must be under 40 words.
  6. Confidence is a float between 0.0 and 1.0.
  7. Do not infer beyond the text.
  8. Focus on commodity transmission channels, not general politics.
  9. For institutional_view: treat the analyst view as the signal.

Article:
  Title:       {article.title}
  Description: {article.description}
  Content:     {article.content}
  Source:      {article.source_name} ({article.source_tier})
  Published:   {article.published_at}

Return JSON in exactly this shape:
{{
  "bucket": "one allowed bucket",
  "region": "short region string e.g. Middle East, Eastern Europe",
  "countries_involved": ["country1", "country2"],
  "affected_commodities": ["Oil"],
  "threat_or_act": "threat|act|neutral",
  "relevance": "high|medium|low",
  "confidence": 0.85,
  "rationale": "brief explanation under 40 words",
  "is_deescalation": false
}}
""".strip()


def _invoke_nova(prompt: str, max_new_tokens: int = 400) -> Dict[str, Any]:
    """
    Invoke Amazon Nova Pro for article classification.

    Strips markdown fences from response before JSON parsing — Nova
    occasionally wraps JSON output in ```json ... ``` even when
    instructed not to.
    """
    response = bedrock_runtime.invoke_model(
        modelId=NOVA_MODEL_ID,
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"max_new_tokens": max_new_tokens},
        }),
    )

    payload = json.loads(response["body"].read())
    text = payload["output"]["message"]["content"][0]["text"]

    clean = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return json.loads(clean)


def _validate_classification(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce closed vocabularies and clamp numeric values on Nova output.

    Nova occasionally returns values outside allowed sets. Validation
    ensures downstream scoring never receives unexpected inputs.
    """
    bucket = str(raw.get("bucket", "other")).strip()
    if bucket not in ALLOWED_BUCKETS:
        bucket = "other"

    region = str(raw.get("region", "")).strip() or "Unknown"

    countries = raw.get("countries_involved", [])
    if not isinstance(countries, list):
        countries = []
    countries = [str(x).strip() for x in countries if str(x).strip()]

    commodities = raw.get("affected_commodities", ["None"])
    if not isinstance(commodities, list):
        commodities = ["None"]
    cleaned_commodities = [
        str(c).strip() for c in commodities
        if str(c).strip() in ALLOWED_COMMODITIES
    ]
    if not cleaned_commodities:
        cleaned_commodities = ["None"]

    threat_or_act = str(raw.get("threat_or_act", "neutral")).strip().lower()
    if threat_or_act not in {"threat", "act", "neutral"}:
        threat_or_act = "neutral"

    relevance = str(raw.get("relevance", "low")).strip().lower()
    if relevance not in {"high", "medium", "low"}:
        relevance = "low"

    confidence = max(0.0, min(1.0, _safe_float(raw.get("confidence", 0.0))))

    rationale = str(raw.get("rationale", "")).strip()[:200]

    is_deescalation = bool(raw.get("is_deescalation", False))
    if bucket == "deescalation":
        is_deescalation = True

    return {
        "bucket": bucket,
        "region": region,
        "countries_involved": countries,
        "affected_commodities": cleaned_commodities,
        "threat_or_act": threat_or_act,
        "relevance": relevance,
        "confidence": confidence,
        "rationale": rationale,
        "is_deescalation": is_deescalation,
    }


def _classify_single(article: RawArticle) -> ClassifiedArticle:
    """Classify one article; returns a fallback record on any failure."""
    try:
        prompt = _build_classification_prompt(article)
        raw = _invoke_nova(prompt)
        validated = _validate_classification(raw)
        error = None
    except Exception as exc:
        validated = {
            "bucket": "other",
            "region": "Unknown",
            "countries_involved": [],
            "affected_commodities": ["None"],
            "threat_or_act": "neutral",
            "relevance": "low",
            "confidence": 0.0,
            "rationale": "",
            "is_deescalation": False,
        }
        error = f"{type(exc).__name__}: {exc}"
        logger.warning("Classification failed for '%s': %s", article.title[:60], error)

    return ClassifiedArticle(
        article_id=article.article_id,
        title=article.title,
        source_id=article.source_id,
        source_name=article.source_name,
        source_tier=article.source_tier,
        url=article.url,
        published_at=article.published_at,
        bucket=validated["bucket"],
        region=validated["region"],
        countries_involved=validated["countries_involved"],
        affected_commodities=validated["affected_commodities"],
        threat_or_act=validated["threat_or_act"],
        relevance=validated["relevance"],
        confidence=validated["confidence"],
        rationale=validated["rationale"],
        is_deescalation=validated["is_deescalation"],
        classification_error=error,
    )


def classify_articles_parallel(
    articles: List[RawArticle],
    max_workers: int = MAX_CLASSIFICATION_WORKERS,
) -> List[ClassifiedArticle]:
    """
    Classify all articles in parallel using a thread pool.

    Parallelism is bounded by max_workers to stay within Bedrock
    invocation rate limits. Each call is independent — Nova has no
    session state between classification calls.

    Returns results in the same order as the input list.
    """
    results: Dict[int, ClassifiedArticle] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(_classify_single, article): i
            for i, article in enumerate(articles)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            results[idx] = future.result()

    return [results[i] for i in range(len(articles))]


# -------------------------------------------------------------------
# Summarisation
# -------------------------------------------------------------------

def summarise_news_signals(
    fetched_count: int,
    retained_articles: List[RawArticle],
    classified_articles: List[ClassifiedArticle],
    max_headlines: int = 8,
) -> NewsSummary:
    """
    Aggregate classified articles into a NewsSummary for the Signal
    Fusion Agent.

    Risk Bias Calculation
    ---------------------
    Uses WEIGHTED scoring (relevance × confidence) rather than raw
    article counts. This prevents ten low-confidence OPEC policy
    articles from outweighing one high-confidence invasion article —
    the correct behaviour for a financial risk system.

        risk_bias_weighted_score =
            sum(weight for disruptive articles) -
            sum(weight for de-escalation articles)

        Positive score → "elevated"
        Negative score → "easing"
        Zero           → "neutral"

    Top Headline Ranking
    --------------------
    Articles ranked by (relevance_tier, confidence) descending.
    Relevance tiers: high=3, medium=2, low=1.
    This ensures a medium-confidence invasion article ranks above
    a low-confidence OPEC note.

    Parameters
    ----------
    fetched_count        : total articles fetched before filtering
    retained_articles    : articles passing trusted-source filter
    classified_articles  : Nova-classified articles
    max_headlines        : number of top headlines to include

    Returns
    -------
    NewsSummary — structured signal package for Signal Fusion Agent
    """
    bucket_counts = Counter(a.bucket for a in classified_articles)
    commodity_counts: Counter = Counter()
    source_counts = Counter(a.source_name for a in classified_articles)

    for article in classified_articles:
        for commodity in article.affected_commodities:
            commodity_counts[commodity] += 1

    n_institutional = sum(
        1 for a in classified_articles if a.source_tier == "institutional"
    )
    n_wire = len(classified_articles) - n_institutional

    # Weighted risk bias
    disruptive_weight = sum(
        _risk_weight(a) for a in classified_articles
        if a.bucket not in {"deescalation", "other", "institutional_view"}
        and not a.is_deescalation
    )
    deescalation_weight = sum(
        _risk_weight(a) for a in classified_articles
        if a.is_deescalation or a.bucket == "deescalation"
    )

    risk_bias_weighted_score = round(disruptive_weight - deescalation_weight, 3)

    if disruptive_weight == 0 and deescalation_weight == 0:
        risk_bias = "neutral"
    elif deescalation_weight > disruptive_weight:
        risk_bias = "easing"
    else:
        risk_bias = "elevated"

    low_sample_warning = len(classified_articles) < MIN_ARTICLES_FOR_RELIABLE_SCORE

    # Rank by (relevance_tier, confidence)
    ranked = sorted(
        classified_articles,
        key=lambda x: (RELEVANCE_RANK.get(x.relevance, 0), x.confidence),
        reverse=True,
    )[:max_headlines]

    top_headlines = [
        {
            "title": a.title,
            "bucket": a.bucket,
            "source": a.source_name,
            "source_tier": a.source_tier,
            "published_at": a.published_at,
            "affected_commodities": a.affected_commodities,
            # Ticker symbols resolved here so Signal Fusion and Market Data
            # Agent can immediately look up price data without a separate
            # mapping step. Only the five tracked commodities produce tickers;
            # "None" is excluded from the ticker list.
            "affected_tickers": [
                COMMODITY_TICKERS[c]
                for c in a.affected_commodities
                if c in COMMODITY_TICKERS
            ],
            "threat_or_act": a.threat_or_act,
            "region": a.region,
            "relevance": a.relevance,
            "confidence": a.confidence,
            "rationale": a.rationale,
            "url": a.url,
        }
        for a in ranked
    ]

    return NewsSummary(
        n_articles_fetched=fetched_count,
        n_articles_retained=len(retained_articles),
        n_articles_classified=len(classified_articles),
        n_institutional=n_institutional,
        n_wire=n_wire,
        bucket_counts=dict(bucket_counts),
        commodity_counts=dict(commodity_counts),
        source_counts=dict(source_counts),
        risk_bias=risk_bias,
        risk_bias_weighted_score=risk_bias_weighted_score,
        low_sample_warning=low_sample_warning,
        commodity_tickers=COMMODITY_TICKERS,
        top_headlines=top_headlines,
    )


# -------------------------------------------------------------------
# Bedrock Action Group Handlers
#
# Each function below is the Lambda handler for one action group.
# The Signal Fusion supervisor agent invokes these via the Bedrock
# multi-agent collaboration framework.
#
# Action groups registered in Bedrock:
#   1. fetch_and_filter_news
#   2. classify_articles
#   3. summarise_news_signals
#
# The supervisor invokes action groups 1-3 in sequence within this
# agent, then passes NewsSummary to Signal Fusion in parallel with
# the Historical Analog Agent's output.
# -------------------------------------------------------------------

def action_fetch_and_filter_news(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bedrock action group: fetch_and_filter_news

    Fetches from Tier 1 (wire) and Tier 2 (institutional) sources
    in parallel, merges, and returns combined RawArticle list.

    Input parameters (from Bedrock action group schema):
        days_back  : int (default 3)
        page_size  : int (default 50)

    Returns:
        articles   : list of RawArticle dicts
        n_fetched  : int
    """
    params = event.get("parameters", {})
    days_back = int(params.get("days_back", 3))
    page_size = int(params.get("page_size", 50))

    # Fetch Tier 1 and Tier 2 in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        wire_future = executor.submit(
            fetch_wire_news, days_back=days_back, page_size=page_size
        )
        institutional_future = executor.submit(fetch_institutional_news)

        wire_articles = wire_future.result()
        institutional_articles = institutional_future.result()

    all_articles = _deduplicate_articles(wire_articles + institutional_articles)

    logger.info(
        "Fetched %d wire + %d institutional = %d total articles",
        len(wire_articles), len(institutional_articles), len(all_articles)
    )

    return {
        "articles": [asdict(a) for a in all_articles],
        "n_fetched": len(all_articles),
        "n_wire": len(wire_articles),
        "n_institutional": len(institutional_articles),
    }


def action_classify_articles(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bedrock action group: classify_articles

    Classifies a list of RawArticle dicts using Nova in parallel.

    Input parameters:
        articles : list of RawArticle dicts

    Returns:
        classified_articles : list of ClassifiedArticle dicts
    """
    raw_dicts = event.get("parameters", {}).get("articles", [])
    articles = [RawArticle(**d) for d in raw_dicts]

    classified = classify_articles_parallel(articles)

    return {
        "classified_articles": [asdict(a) for a in classified],
        "n_classified": len(classified),
        "n_errors": sum(1 for a in classified if a.classification_error),
    }


def action_summarise(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bedrock action group: summarise_news_signals

    Builds NewsSummary from classified articles for Signal Fusion.

    Input parameters:
        fetched_count        : int
        retained_articles    : list of RawArticle dicts
        classified_articles  : list of ClassifiedArticle dicts

    Returns:
        summary : NewsSummary dict
    """
    params = event.get("parameters", {})
    fetched_count = int(params.get("fetched_count", 0))
    retained = [RawArticle(**d) for d in params.get("retained_articles", [])]
    classified = [ClassifiedArticle(**d) for d in params.get("classified_articles", [])]

    summary = summarise_news_signals(fetched_count, retained, classified)
    return {"summary": asdict(summary)}


# -------------------------------------------------------------------
# Lambda handler (entry point for Bedrock action groups)
# -------------------------------------------------------------------

ACTION_HANDLERS = {
    "fetch_and_filter_news": action_fetch_and_filter_news,
    "classify_articles": action_classify_articles,
    "summarise_news_signals": action_summarise,
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for Bedrock action group invocations.

    Bedrock passes the action name and parameters in the event.
    Routes to the correct action handler and returns the result
    in the format expected by Bedrock Agents.

    Event shape (from Bedrock):
    {
        "actionGroup": "NewsIntelligenceActions",
        "function": "fetch_and_filter_news",
        "parameters": { ... }
    }
    """
    action = event.get("function") or event.get("action", "")

    handler = ACTION_HANDLERS.get(action)
    if not handler:
        return {
            "error": f"Unknown action: {action}",
            "available_actions": list(ACTION_HANDLERS.keys()),
        }

    try:
        result = handler(event)
        return {
            "actionGroup": event.get("actionGroup", "NewsIntelligenceActions"),
            "function": action,
            "functionResponse": {
                "responseBody": {
                    "TEXT": {"body": json.dumps(result)}
                }
            },
        }
    except Exception as exc:
        logger.error("Action %s failed: %s", action, exc, exc_info=True)
        return {
            "actionGroup": event.get("actionGroup", "NewsIntelligenceActions"),
            "function": action,
            "functionResponse": {
                "responseBody": {
                    "TEXT": {"body": json.dumps({"error": str(exc)})}
                }
            },
        }


# -------------------------------------------------------------------
# Local development entry point
#
# Runs the full pipeline directly without Bedrock infrastructure.
# Use this for local testing and unit tests.
# In production, the Lambda handler is the entry point.
# -------------------------------------------------------------------

def run_news_agent(
    days_back: int = 3,
    page_size: int = 50,
) -> Dict[str, Any]:
    """
    Full pipeline for local testing (bypasses Lambda/Bedrock routing).

    Equivalent to the Signal Fusion Agent calling all three action
    groups in sequence on this agent.

    Returns
    -------
    dict:
        articles   : list of ClassifiedArticle dicts
        summary    : NewsSummary dict
    """
    # Step 1: Fetch
    fetch_result = action_fetch_and_filter_news({
        "parameters": {"days_back": days_back, "page_size": page_size}
    })
    raw_articles_dicts = fetch_result["articles"]

    # Step 2: Classify
    classify_result = action_classify_articles({
        "parameters": {"articles": raw_articles_dicts}
    })
    classified_dicts = classify_result["classified_articles"]

    # Step 3: Summarise
    summarise_result = action_summarise({
        "parameters": {
            "fetched_count": fetch_result["n_fetched"],
            "retained_articles": raw_articles_dicts,
            "classified_articles": classified_dicts,
        }
    })

    return {
        "articles": classified_dicts,
        "summary": summarise_result["summary"],
    }


if __name__ == "__main__":
    result = run_news_agent()
    print(json.dumps(result, indent=2))