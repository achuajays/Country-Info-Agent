"""LangGraph node functions for the Country Information Agent.

Three-node pipeline:
  1. parse_intent  — Groq LLM extracts country + fields from user question
  2. fetch_country — httpx calls REST Countries API
  3. synthesize_answer — Groq LLM composes a natural-language answer
"""

import json
import logging

from dotenv import load_dotenv

# Load .env BEFORE any Groq imports so the API key is available
load_dotenv()

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from .state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared LLM instance (Groq)
# ---------------------------------------------------------------------------
_llm = ChatGroq(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    temperature=0.2,
    max_tokens=1024,
)

# ---------------------------------------------------------------------------
# REST Countries API config
# ---------------------------------------------------------------------------
REST_COUNTRIES_BASE = "https://restcountries.com/v3.1/name"
HTTP_TIMEOUT = 10.0

# ---------------------------------------------------------------------------
# Supported fields mapping   API path → human label
# ---------------------------------------------------------------------------
FIELD_KEYS = [
    "capital", "population", "currency", "currencies",
    "language", "languages", "region", "subregion",
    "area", "flag", "timezone", "timezones", "borders",
    "continent", "continents",
]


# ===================================================================
# Node 1: Parse Intent
# ===================================================================
INTENT_SYSTEM_PROMPT = """\
You are a strict JSON extractor. Given a user question about a country, extract:
1. "country" — the country name mentioned (use the common English name).
2. "fields" — a list of information fields the user is asking about.

Valid field values: capital, population, currency, language, region, subregion, area, flag, timezone, borders, continent.

If the user asks a general question (e.g. "Tell me about France"), set fields to ["capital", "population", "currency", "language"].

If you cannot identify a country in the question, set "country" to "" and "fields" to [].

Respond ONLY with valid JSON. No explanation, no markdown.

Example input: "What is the population of Germany?"
Example output: {"country": "Germany", "fields": ["population"]}

Example input: "What currency does Japan use?"
Example output: {"country": "Japan", "fields": ["currency"]}

Example input: "Tell me about Brazil"
Example output: {"country": "Brazil", "fields": ["capital", "population", "currency", "language"]}
"""


async def parse_intent(state: AgentState) -> dict:
    """Use Groq LLM to extract country name and requested fields."""
    question = state["question"].strip()

    if not question:
        return {
            "country": "",
            "fields": [],
            "error": "Please ask a question about a country. For example: 'What is the capital of France?'",
            "answer": "Please ask a question about a country. For example: 'What is the capital of France?'",
        }

    messages = [
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=question),
    ]

    try:
        response = await _llm.ainvoke(messages)
        content = response.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        parsed = json.loads(content)
        country = parsed.get("country", "").strip()
        fields = parsed.get("fields", [])

        # Validate fields
        fields = [f for f in fields if f in FIELD_KEYS or f.rstrip("s") in FIELD_KEYS or f + "s" in FIELD_KEYS]

        if not country:
            return {
                "country": "",
                "fields": [],
                "error": "I couldn't identify a country in your question. Please mention a specific country, like 'What is the population of Germany?'",
                "answer": "I couldn't identify a country in your question. Please mention a specific country, like 'What is the population of Germany?'",
            }

        return {"country": country, "fields": fields if fields else ["capital", "population", "currency", "language"]}

    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Intent parse failed: %s", exc)
        return {
            "country": "",
            "fields": [],
            "error": "I had trouble understanding your question. Could you rephrase it?",
            "answer": "I had trouble understanding your question. Could you rephrase it?",
        }
    except Exception as exc:
        logger.error("LLM call failed in parse_intent: %s", exc)
        return {
            "country": "",
            "fields": [],
            "error": f"Sorry, I'm experiencing a service issue. Please try again. ({type(exc).__name__})",
            "answer": f"Sorry, I'm experiencing a service issue. Please try again. ({type(exc).__name__})",
        }


# ===================================================================
# Node 2: Fetch Country Data
# ===================================================================
from async_lru import alru_cache

@alru_cache(maxsize=128)
async def _do_httpx_fetch(country: str) -> dict:
    """Cached raw API request."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(
            f"{REST_COUNTRIES_BASE}/{country}",
            params={"fullText": "false"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_country(state: AgentState) -> dict:
    """Call the REST Countries API and return raw data."""
    country = state["country"]

    try:
        data = await _do_httpx_fetch(country)

        # API returns a list; take the first (best) match
        if isinstance(data, list) and len(data) > 0:
            country_data = data[0]
        else:
            country_data = data

        # Extract flag URL
        flag_url = ""
        flags = country_data.get("flags", {})
        if isinstance(flags, dict):
            flag_url = flags.get("png", flags.get("svg", ""))

        return {
            "api_data": country_data,
            "flag_url": flag_url,
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {
                "api_data": None,
                "flag_url": "",
                "error": f"I couldn't find a country called '{country}'. Please check the spelling and try again.",
                "answer": f"I couldn't find a country called '{country}'. Please check the spelling and try again.",
            }
        logger.error("REST Countries API error: %s", exc)
        return {
            "api_data": None,
            "flag_url": "",
            "error": "The country data service is temporarily unavailable. Please try again later.",
            "answer": "The country data service is temporarily unavailable. Please try again later.",
        }
    except httpx.TimeoutException:
        logger.error("REST Countries API timeout for: %s", country)
        return {
            "api_data": None,
            "flag_url": "",
            "error": "The country data service is taking too long to respond. Please try again in a moment.",
            "answer": "The country data service is taking too long to respond. Please try again in a moment.",
        }
    except Exception as exc:
        logger.error("REST Countries API generic error: %s", exc)
        return {
            "api_data": None,
            "flag_url": "",
            "error": "The country data service is temporarily unavailable. Please try again later.",
            "answer": "The country data service is temporarily unavailable. Please try again later.",
        }


# ===================================================================
# Node 3: Synthesize Answer
# ===================================================================
SYNTHESIS_SYSTEM_PROMPT = """\
You are a knowledgeable and friendly assistant that answers questions about countries.
Given the user's original question and factual data from an API, compose a clear, concise, and natural answer.

Rules:
- ONLY use the data provided. Do NOT make up facts.
- Format large numbers with commas (e.g., 83,491,249).
- For currencies, include the symbol if available.
- Keep the answer to 2-4 sentences unless the user asked for multiple fields.
- Be conversational but informative.
- If some requested data is not available, mention that gracefully.
"""


async def synthesize_answer(state: AgentState) -> dict:
    """Use Groq LLM to compose a natural-language answer from API data."""
    api_data = state.get("api_data")

    if not api_data:
        # Error already set by fetch_country
        return {}

    # Build a concise data summary for the LLM
    fields = state.get("fields", [])
    data_summary = _extract_fields(api_data, fields)

    messages = [
        SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"User question: {state['question']}\n\n"
            f"Country: {api_data.get('name', {}).get('common', state['country'])}\n"
            f"Data:\n{json.dumps(data_summary, indent=2, ensure_ascii=False)}"
        )),
    ]

    try:
        response = await _llm.ainvoke(messages)
        return {"answer": response.content.strip(), "error": None}
    except Exception as exc:
        logger.error("LLM call failed in synthesize_answer: %s", exc)
        # Fallback: return raw data formatted simply
        fallback = _format_fallback(api_data, fields)
        return {"answer": fallback, "error": None}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_fields(data: dict, fields: list[str]) -> dict:
    """Pick requested fields from the REST Countries API response."""
    result = {}

    field_set = set(fields)

    if "capital" in field_set:
        caps = data.get("capital", [])
        result["capital"] = caps[0] if caps else "N/A"

    if "population" in field_set:
        result["population"] = data.get("population", "N/A")

    if "currency" in field_set or "currencies" in field_set:
        currencies = data.get("currencies", {})
        if currencies:
            parts = []
            for code, info in currencies.items():
                name = info.get("name", code)
                symbol = info.get("symbol", "")
                parts.append(f"{name} ({symbol})" if symbol else name)
            result["currencies"] = ", ".join(parts)
        else:
            result["currencies"] = "N/A"

    if "language" in field_set or "languages" in field_set:
        langs = data.get("languages", {})
        result["languages"] = ", ".join(langs.values()) if langs else "N/A"

    if "region" in field_set:
        result["region"] = data.get("region", "N/A")

    if "subregion" in field_set:
        result["subregion"] = data.get("subregion", "N/A")

    if "area" in field_set:
        area = data.get("area")
        result["area_km2"] = f"{area:,.0f}" if area else "N/A"

    if "timezone" in field_set or "timezones" in field_set:
        tzs = data.get("timezones", [])
        result["timezones"] = ", ".join(tzs) if tzs else "N/A"

    if "borders" in field_set:
        borders = data.get("borders", [])
        result["borders"] = ", ".join(borders) if borders else "No bordering countries (island nation)"

    if "continent" in field_set or "continents" in field_set:
        conts = data.get("continents", [])
        result["continents"] = ", ".join(conts) if conts else "N/A"

    if "flag" in field_set:
        flags = data.get("flags", {})
        result["flag_url"] = flags.get("png", flags.get("svg", "N/A"))

    return result


def _format_fallback(data: dict, fields: list[str]) -> str:
    """Simple fallback formatting when LLM synthesis fails."""
    extracted = _extract_fields(data, fields)
    name = data.get("name", {}).get("common", "Unknown")
    lines = [f"Here's what I found about {name}:"]
    for key, value in extracted.items():
        label = key.replace("_", " ").title()
        lines.append(f"• {label}: {value}")
    return "\n".join(lines)
