import math
import sys
from typing import Dict, Any, Optional

from agents import commodity_agent_new, news_agent, hedge_agent


def _fix_stdout_encoding():
    """Allow emoji output on Windows console (cp1252)."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _sigmoid_normalize(raw_score: float, k: float = 0.25) -> int:
    """
    Normalize an unbounded geo risk score to [0, 100] via sigmoid.

    The raw risk_bias_weighted_score from news_agent is an unbounded
    weighted difference (disruptive_weight - deescalation_weight).
    It cannot be directly averaged with CMSI which is natively [0, 100].

    Sigmoid calibration (k=0.25):
        raw =  0  ->  50  (neutral)
        raw =  5  ->  73  (elevated)
        raw = 10  ->  92  (high)
        raw = 15  ->  98  (crisis)
        raw = -5  ->  27  (easing)

    Tune k against your actual score distribution once you have 30+ days
    of data, then migrate to rolling-percentile normalization (BIS/Fed
    methodology) for production.
    """
    return round(100 / (1 + math.exp(-k * raw_score)))


def run(portfolio: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute the full multi-agent pipeline and return a structured result.

    Parameters
    ----------
    portfolio : dict, optional
        User portfolio context passed through to the hedge agent.
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
                "total_notional": float,  # sum of all exposures
            }
        If None or empty, the hedge agent generates generic strategies.
    """
    _fix_stdout_encoding()
    portfolio = portfolio or {}

    # ------------------------------------------------------------------
    # Guard: validate commodity agent result before accessing ["analysis"]
    # ------------------------------------------------------------------
    print("🔍 Running Commodity Agent...")
    commodity_result = commodity_agent_new.run()

    if commodity_result.get("status") == "error":
        raise RuntimeError(
            f"Commodity Agent failed: {commodity_result.get('message', 'unknown error')}. "
            f"Failed commodities: {commodity_result.get('failed_commodities', {})}"
        )

    # ------------------------------------------------------------------
    # Commodity score (CMSI) — natively bounded [0, 100]
    # ------------------------------------------------------------------
    c_score = commodity_result["analysis"]["cmsi_score"]

    # ------------------------------------------------------------------
    # Geo score — sigmoid-normalized from unbounded raw score to [0, 100]
    # ------------------------------------------------------------------
    print("🌍 Running News Agent...")
    news_result = news_agent.run_news_agent()
    news_summary = news_result["summary"]

    raw_geo_score = news_summary["risk_bias_weighted_score"]

    # Sigmoid normalization: maps unbounded raw score to [0, 100].
    # This replaces the previous min(100, max(0, round(...))) which was
    # financially invalid — it clipped an already small number rather
    # than normalizing it, making c_score and g_score incommensurable.
    g_score = _sigmoid_normalize(raw_geo_score)

    # ------------------------------------------------------------------
    # Global Stress Index — equal-weight composite of both dimensions.
    # Both inputs are now on [0, 100], making the blend meaningful.
    # ------------------------------------------------------------------
    global_stress = round(0.5 * c_score + 0.5 * g_score)

    print(f"⚡ Global Stress Index: {global_stress}/100")
    print("🛡️ Running Hedge Agent...")

    # ------------------------------------------------------------------
    # Hedge Agent — pass portfolio for tailored strategies
    # ------------------------------------------------------------------
    hedge_result = hedge_agent.run(
        stress_score=global_stress,
        commodity_analysis=commodity_result["analysis"],
        geo_analysis=news_summary,
        portfolio=portfolio,
        
    )

    # ------------------------------------------------------------------
    # Reasoning trace fields
    # ------------------------------------------------------------------
    oil_raw = commodity_result.get("raw_data", {}).get("Oil", {})
    oil_deviation = oil_raw.get("z_score_30d", "N/A")

    commodity_counts = news_summary.get("commodity_counts", {})
    top_risk = (
        max(
            (k for k in commodity_counts if k != "None"),
            key=lambda k: commodity_counts[k],
            default="N/A",
        )
        if commodity_counts else "N/A"
    )

    top_headlines = news_summary.get("top_headlines", [])
    headline_titles = "; ".join(h["title"] for h in top_headlines[:3] if h.get("title"))
    geo_explanation = (
        f"News risk bias is {news_summary.get('risk_bias', 'N/A')} "
        f"(raw weighted score: {raw_geo_score}, normalized: {g_score}/100). "
        f"Top headlines: {headline_titles or 'none'}"
    )

    # Portfolio trace line (shown in hedge agent tab)
    portfolio_exposures = portfolio.get("exposures", {})
    active_exposures = {k: v for k, v in portfolio_exposures.items() if v > 0}
    portfolio_trace = (
        ", ".join(f"{k}: ${v:.0f}M" for k, v in active_exposures.items())
        if active_exposures else "No portfolio provided — generic strategies generated"
    )

    trace = {
        "commodity": {
            "step1": "Fetched 90-day price history for Oil, Gold, Wheat, Copper, Natural Gas via yfinance",
            "step2": f"Oil z-score vs 30d avg = {oil_deviation}",
            "step3": "Sent price data to Amazon Nova Pro for stress scoring",
            "step4": f"Nova returned CMSI score: {c_score}/100, top concern: {commodity_result['analysis']['top_concern']}",
            "reasoning": commodity_result["analysis"]["explanation"],
        },
        "geo": {
            "step1": f"Fetched {news_summary.get('n_articles_fetched', 0)} headlines from NewsAPI + institutional sources",
            "step2": f"Retained {news_summary.get('n_articles_retained', 0)} trusted-source articles, classified {news_summary.get('n_articles_classified', 0)}",
            "step3": "Classified articles via Amazon Nova Pro into geopolitical signal buckets",
            "step4": f"Risk bias: {news_summary.get('risk_bias', 'N/A')} (raw: {raw_geo_score}, normalized: {g_score}/100), top commodity in news: {top_risk}",
            "reasoning": geo_explanation,
        },
        "orchestrator": {
            "step1": f"Received commodity CMSI score: {c_score}/100",
            "step2": f"Received news geo score: {g_score}/100 (sigmoid-normalized from raw {raw_geo_score})",
            "step3": f"Computed Global Stress Index: (0.5 × {c_score}) + (0.5 × {g_score}) = {global_stress}",
            "step4": f"Classified as: {'LOW RISK' if global_stress < 30 else 'ELEVATED' if global_stress < 60 else 'HIGH RISK' if global_stress < 80 else 'CRITICAL'}",
        },
        "hedge": {
            "step1": f"Received Global Stress Index: {global_stress}/100",
            "step2": f"Portfolio context: {portfolio_trace}",
            "step3": "Passed commodity + news analysis + portfolio context to Amazon Nova Pro",
            "step4": f"Nova generated {len(hedge_result['strategies'])} hedging strategies",
            "step5": hedge_result["overall_recommendation"],
        },
    }

    return {
        "global_stress_index": global_stress,
        "commodity": commodity_result,
        "geo": news_result,
        "hedging": hedge_result,
        "portfolio": portfolio,
        "trace": trace,
    }