import json
from typing import Any, Dict, Optional

import boto3
from dotenv import load_dotenv

load_dotenv()

client = boto3.client("bedrock-runtime", region_name="us-east-1")


def run(
    stress_score: int,
    commodity_analysis: Dict[str, Any],
    geo_analysis: Dict[str, Any],
    portfolio: Optional[Dict[str, Any]] = None,
):
    """
    Generate hedging strategies.

    Parameters
    ----------
    stress_score : int
        Global Stress Index (0-100), computed by the orchestrator.

    commodity_analysis : dict
        commodity_agent.run()["analysis"] — output of analyze_with_nova().
        Relevant fields:
            cmsi_score          : float  (0-100)
            risk_level          : str    "Low" | "Elevated" | "High" | "Crisis"
            top_concern         : str    e.g. "Oil"
            top_concern_driver  : str    e.g. "volatility_regime"
            sub_indices         : dict   {"PDI": float, "VRI": float,
                                          "MSI": float, "CCI": float}
            explanation         : str    3-5 sentence narrative from Nova
            hedging_note        : str    instrument-level suggestions from Nova

    geo_analysis : dict
        news_agent.run_news_agent()["summary"] — asdict(NewsSummary).
        Relevant fields:
            risk_bias                 : str   "elevated" | "easing" | "neutral"
            risk_bias_weighted_score  : float
            bucket_counts             : dict  e.g. {"war_conflict": 3, ...}
            commodity_counts          : dict  e.g. {"Oil": 5, "Wheat": 2}
            top_headlines             : list  of headline dicts, each with:
                                            "title", "bucket", "relevance",
                                            "affected_commodities", "region"

    portfolio : dict, optional
        User portfolio context from the Streamlit app.
        Expected shape:
            {
                "exposures": {
                    "Oil": float,         # $M notional
                    "Natural Gas": float,
                    "Wheat": float,
                    "Copper": float,
                    "Gold": float,
                },
                "notes": str,             # free-text context
                "total_notional": float,
            }
        If None or empty, Nova generates generic market-level strategies.
    """

    # ------------------------------------------------------------------
    # Portfolio fields
    # ------------------------------------------------------------------
    portfolio = portfolio or {}
    portfolio_exposures = portfolio.get("exposures", {})
    portfolio_notes = portfolio.get("notes", "").strip()
    portfolio_total = portfolio.get("total_notional", 0)

    active_exposures = {k: v for k, v in portfolio_exposures.items() if v > 0}

    if active_exposures:
        # Sort by size descending so Nova sees the biggest risks first
        sorted_exposures = sorted(active_exposures.items(), key=lambda x: x[1], reverse=True)
        exposure_lines = "\n".join(
            f"  {k}: ${v:.0f}M notional" for k, v in sorted_exposures
        )
        portfolio_section = f"""
=== USER PORTFOLIO ===
Total notional: ${portfolio_total:.0f}M
Commodity exposures (largest first):
{exposure_lines}
Additional context: {portfolio_notes or 'None provided'}

IMPORTANT: Strategies MUST be tailored to this specific portfolio.
Prioritise the commodities with the largest exposures.
Reference the dollar amounts when explaining position sizing.
"""
    else:
        portfolio_section = """
=== USER PORTFOLIO ===
No portfolio provided. Generate generic market-level hedging strategies
based on the commodity and geopolitical conditions below.
"""

    # ------------------------------------------------------------------
    # Commodity fields
    # ------------------------------------------------------------------
    cmsi_score = commodity_analysis.get("cmsi_score", "N/A")
    risk_level = commodity_analysis.get("risk_level", "N/A")
    top_concern = commodity_analysis.get("top_concern", "N/A")
    top_concern_driver = commodity_analysis.get("top_concern_driver", "N/A")
    sub_indices = commodity_analysis.get("sub_indices", {})
    commodity_explanation = commodity_analysis.get("explanation", "N/A")
    commodity_hedging_note = commodity_analysis.get("hedging_note", "")

    # ------------------------------------------------------------------
    # Geo / news fields
    # ------------------------------------------------------------------
    risk_bias = geo_analysis.get("risk_bias", "N/A")
    risk_bias_score = geo_analysis.get("risk_bias_weighted_score", "N/A")
    bucket_counts = geo_analysis.get("bucket_counts", {})
    commodity_counts = geo_analysis.get("commodity_counts", {})
    top_headlines = geo_analysis.get("top_headlines", [])

    headline_lines = "\n".join(
        f"  - [{h.get('relevance', '?').upper()}] {h.get('title', '')}"
        f" ({h.get('bucket', '')}, {h.get('region', '')})"
        for h in top_headlines[:3]
    )

    bucket_str = ", ".join(
        f"{k}: {v}" for k, v in bucket_counts.items() if v > 0
    ) or "none"

    commodity_exposure_str = ", ".join(
        f"{k} ({v} articles)"
        for k, v in commodity_counts.items()
        if k != "None" and v > 0
    ) or "none identified"

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------
    prompt = f"""You are a senior portfolio risk manager generating hedging strategies.

Global Stress Index: {stress_score}/100
=== JURISDICTION ===
Jurisdiction: United States
Exchanges: CME/NYMEX/CBOT/COMEX
Benchmarks: WTI crude, Henry Hub gas, CBOT wheat, COMEX copper/gold
Currency: USD
Instruments available: CME futures, listed options, OTC swaps, basis swaps
{portfolio_section}
=== COMMODITY MARKET CONDITIONS ===
CMSI Score: {cmsi_score}/100 ({risk_level})
Top concern: {top_concern} (primary driver: {top_concern_driver})
Sub-indices — PDI: {sub_indices.get("PDI", "N/A")}, VRI: {sub_indices.get("VRI", "N/A")}, MSI: {sub_indices.get("MSI", "N/A")}, CCI: {sub_indices.get("CCI", "N/A")}
Analysis: {commodity_explanation}
Commodity agent hedging note: {commodity_hedging_note}

=== GEOPOLITICAL / NEWS CONDITIONS ===
News risk bias: {risk_bias} (weighted score: {risk_bias_score})
Signal breakdown: {bucket_str}
Commodity exposure in news: {commodity_exposure_str}
Top headlines:
{headline_lines}

=== TASK ===
Based on all of the above, suggest 3 specific hedging strategies.
{"Tailor each strategy to the USER PORTFOLIO above — reference specific commodities and dollar exposures." if active_exposures else "Generate strategies based on current market conditions."}
For each strategy explain WHY it is recommended given the specific commodity
stress drivers and geopolitical signals described above.
Be specific about instruments (futures, options, swaps, cross-commodity spreads).

Respond in JSON:
{{
  "strategies": [
    {{"name": str, "action": str, "rationale": str, "urgency": "low|medium|high"}}
  ],
  "overall_recommendation": str
}}
Return only JSON, no extra text."""

    # ------------------------------------------------------------------
    # Invoke Nova
    # ------------------------------------------------------------------
    response = client.invoke_model(
        modelId="amazon.nova-pro-v1:0",
        body=json.dumps(
            {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": 700},
            }
        ),
    )

    text = json.loads(response["body"].read())["output"]["message"]["content"][0]["text"]

    # Strip markdown fences Nova occasionally adds despite instructions
    clean = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    result = json.loads(clean)
    print(f"✅ Hedge Agent complete — {len(result['strategies'])} strategies generated")
    return result
