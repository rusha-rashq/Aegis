import math
import time

import streamlit as st

from agents.orchestrator import run

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AEGIS — Global Stress Monitor", page_icon="⚡", layout="wide"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

  html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
  .block-container { padding: 2rem 2.5rem; }

  .gsi-box {
    background: linear-gradient(135deg, #0b1120, #111827);
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    border: 1px solid #1e2d4a;
  }
  .gsi-label {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.2em;
    color: #6a7fa8;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .gsi-number {
    font-size: 80px;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 8px;
  }
  .gsi-status {
    font-family: 'Space Mono', monospace;
    font-size: 13px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    font-weight: 700;
  }
  .agent-card {
    background: #0b1120;
    border-radius: 12px;
    padding: 1.2rem;
    border: 1px solid #1e2d4a;
    height: 100%;
  }
  .agent-title {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
  }
  .agent-sub {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    color: #6a7fa8;
    margin-bottom: 12px;
  }
  .agent-score {
    font-size: 36px;
    font-weight: 800;
    line-height: 1;
  }
  .commodity-card {
    background: #0b1120;
    border-radius: 10px;
    padding: 1rem;
    border: 1px solid #1e2d4a;
    text-align: center;
  }
  .commodity-name {
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.15em;
    color: #6a7fa8;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .commodity-price {
    font-size: 18px;
    font-weight: 800;
    margin-bottom: 2px;
  }
  .commodity-change {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    font-weight: 700;
  }
  .headline-item {
    background: #0b1120;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    border-left: 3px solid #1e2d4a;
    font-size: 12px;
    color: #9bb0d4;
    line-height: 1.5;
  }
  .strategy-card {
    background: #0b1120;
    border-radius: 12px;
    padding: 1.2rem;
    border: 1px solid #1e2d4a;
    margin-bottom: 12px;
  }
  .strategy-name {
    font-size: 14px;
    font-weight: 700;
    color: #7fff5f;
    margin-bottom: 6px;
  }
  .strategy-action {
    font-size: 12px;
    color: #e2eaf8;
    margin-bottom: 8px;
    line-height: 1.5;
  }
  .strategy-rationale {
    font-size: 11px;
    color: #6a7fa8;
    line-height: 1.5;
    font-style: italic;
  }
  .urgency-high {
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.1em;
    padding: 2px 8px;
    border-radius: 3px;
    background: rgba(255,59,92,0.12);
    color: #ff3b5c;
    border: 1px solid rgba(255,59,92,0.3);
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .urgency-medium {
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.1em;
    padding: 2px 8px;
    border-radius: 3px;
    background: rgba(255,204,0,0.1);
    color: #ffcc00;
    border: 1px solid rgba(255,204,0,0.3);
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .urgency-low {
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.1em;
    padding: 2px 8px;
    border-radius: 3px;
    background: rgba(127,255,95,0.1);
    color: #7fff5f;
    border: 1px solid rgba(127,255,95,0.3);
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .section-header {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.2em;
    color: #6a7fa8;
    text-transform: uppercase;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1e2d4a;
  }
  .overall-rec {
    background: linear-gradient(135deg, rgba(0,212,255,0.05), rgba(0,212,255,0.02));
    border: 1px solid rgba(0,212,255,0.2);
    border-radius: 12px;
    padding: 1.2rem;
    font-size: 13px;
    color: #e2eaf8;
    line-height: 1.7;
  }
  .nova-label {
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.15em;
    color: #00d4ff;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .spacer { margin-top: 24px; }

  /* Portfolio panel */
  .portfolio-panel {
    background: linear-gradient(135deg, #0b1120, #0d1628);
    border: 1px solid #1e2d4a;
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
  }
  .portfolio-exposure-bar {
    height: 6px;
    border-radius: 3px;
    background: #1e2d4a;
    margin-top: 6px;
    overflow: hidden;
  }
  .portfolio-exposure-fill {
    height: 100%;
    border-radius: 3px;
    background: linear-gradient(90deg, #00d4ff, #7fff5f);
  }
  .exposure-tag {
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.08em;
    padding: 3px 10px;
    border-radius: 4px;
    background: rgba(0,212,255,0.08);
    color: #00d4ff;
    border: 1px solid rgba(0,212,255,0.2);
    margin: 2px 4px 2px 0;
  }
  .portfolio-summary-card {
    background: rgba(0,212,255,0.04);
    border: 1px solid rgba(0,212,255,0.15);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 1.5rem;
  }
</style>
""",
    unsafe_allow_html=True,
)


# ── Helper functions ──────────────────────────────────────────────────────────
def stress_color(score):
    if score < 30:
        return "#7fff5f"
    elif score < 60:
        return "#ffcc00"
    elif score < 80:
        return "#ff6b35"
    else:
        return "#ff3b5c"


def stress_label(score):
    if score < 30:
        return "LOW RISK"
    elif score < 60:
        return "ELEVATED"
    elif score < 80:
        return "HIGH RISK"
    else:
        return "CRITICAL"


def change_color(val):
    return "#ff3b5c" if val > 0 else "#7fff5f"


def sigmoid_normalize(raw_score, k=0.25):
    """Normalize unbounded geo score to [0, 100] via sigmoid."""
    return round(100 / (1 + math.exp(-k * raw_score)))


# ── Header ────────────────────────────────────────────────────────────────────
col_logo, col_spacer, col_btn = st.columns([3, 6, 2])
with col_logo:
    st.markdown("## ⚡ AEGIS")
    st.markdown(
        "<span style='font-family:Space Mono,monospace;font-size:10px;color:#6a7fa8;letter-spacing:0.15em'>AGENTIC GLOBAL INTELLIGENCE SYSTEM</span>",
        unsafe_allow_html=True,
    )
with col_btn:
    st.write("")
    run_analysis = st.button(
        "🔄 Run Analysis", use_container_width=True, type="primary"
    )

st.divider()

# ── Portfolio Input Panel ─────────────────────────────────────────────────────
st.markdown(
    "<div class='section-header'>YOUR PORTFOLIO — OPTIONAL: PROVIDE EXPOSURES FOR TAILORED HEDGING STRATEGIES</div>",
    unsafe_allow_html=True,
)

with st.container():
    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)

    with p_col1:
        oil_exposure = st.number_input(
            "Oil ($M notional)", min_value=0.0, value=0.0, step=1.0, format="%.1f"
        )
    with p_col2:
        gas_exposure = st.number_input(
            "Natural Gas ($M)", min_value=0.0, value=0.0, step=1.0, format="%.1f"
        )
    with p_col3:
        wheat_exposure = st.number_input(
            "Wheat ($M)", min_value=0.0, value=0.0, step=1.0, format="%.1f"
        )
    with p_col4:
        copper_exposure = st.number_input(
            "Copper ($M)", min_value=0.0, value=0.0, step=1.0, format="%.1f"
        )
    with p_col5:
        gold_exposure = st.number_input(
            "Gold ($M)", min_value=0.0, value=0.0, step=1.0, format="%.1f"
        )

    notes_col, _ = st.columns([3, 1])
    with notes_col:
        portfolio_notes = st.text_area(
            "Additional context (optional)",
            placeholder="e.g. Long physical wheat inventory, short crude futures expiring Q3, airline fuel hedges, natural gas producer with fixed-price contracts...",
            height=68,
            label_visibility="visible",
        )

total_notional = oil_exposure + gas_exposure + wheat_exposure + copper_exposure + gold_exposure

portfolio = {
    "exposures": {
        "Oil": oil_exposure,
        "Natural Gas": gas_exposure,
        "Wheat": wheat_exposure,
        "Copper": copper_exposure,
        "Gold": gold_exposure,
    },
    "notes": portfolio_notes.strip(),
    "total_notional": total_notional,
}

# Show portfolio summary bar if user entered anything
if total_notional > 0:
    active_exposures = {k: v for k, v in portfolio["exposures"].items() if v > 0}
    tags_html = "".join(
        f"<span class='exposure-tag'>{k}: ${v:.0f}M</span>"
        for k, v in active_exposures.items()
    )
    st.markdown(
        f"""
    <div class='portfolio-summary-card'>
        <div style='font-family:Space Mono,monospace;font-size:9px;color:#00d4ff;letter-spacing:0.15em;margin-bottom:8px'>
            PORTFOLIO LOADED · TOTAL NOTIONAL ${total_notional:.0f}M
        </div>
        <div>{tags_html}</div>
        {f"<div style='font-size:11px;color:#6a7fa8;margin-top:8px;font-style:italic'>{portfolio_notes}</div>" if portfolio_notes else ""}
    </div>
    """,
        unsafe_allow_html=True,
    )

st.divider()

# ── Session state ─────────────────────────────────────────────────────────────
if "result" not in st.session_state:
    st.session_state.result = None
if "portfolio_used" not in st.session_state:
    st.session_state.portfolio_used = None

# ── Run pipeline ──────────────────────────────────────────────────────────────
if run_analysis:
    status_box = st.empty()

    stages = [
        ("#ffcc00", "⟳", "Commodity Agent", "fetching live market data...", [], ""),
        ("#ff6b35", "⟳", "Geo Agent", "scanning geopolitical headlines...",
         [("#ffcc00", "✓", "Commodity Agent", "complete")], ""),
        ("#00d4ff", "⟳", "Orchestrator", "computing Global Stress Index...",
         [("#ffcc00", "✓", "Commodity Agent", "complete"),
          ("#ff6b35", "✓", "Geo Agent", "complete")], ""),
        ("#7fff5f", "⟳", "Hedge Agent", "generating tailored strategies...",
         [("#ffcc00", "✓", "Commodity Agent", "complete"),
          ("#ff6b35", "✓", "Geo Agent", "complete"),
          ("#00d4ff", "✓", "Orchestrator", "complete")], ""),
    ]

    def render_status(done_stages, active_color, active_icon, active_name, active_detail):
        done_html = "".join(
            f"<div style='color:{c}; font-family:Space Mono,monospace; font-size:12px; line-height:2'>"
            f"{icon} &nbsp;{name} — {detail}</div>"
            for c, icon, name, detail in done_stages
        )
        active_html = (
            f"<div style='color:{active_color}; font-family:Space Mono,monospace; font-size:12px; line-height:2'>"
            f"{active_icon} &nbsp;{active_name} — {active_detail}</div>"
        )
        portfolio_note = (
            f"<div style='font-family:Space Mono,monospace;font-size:10px;color:#00d4ff;margin-top:8px'>"
            f"📋 Portfolio loaded: ${total_notional:.0f}M notional across "
            f"{sum(1 for v in portfolio['exposures'].values() if v > 0)} commodities</div>"
            if total_notional > 0 else ""
        )
        return f"""
        <div style='background:#0b1120;border:1px solid #1e2d4a;border-radius:12px;padding:1.5rem;'>
            <div style='font-family:Space Mono,monospace;font-size:11px;color:#6a7fa8;
            letter-spacing:0.15em;margin-bottom:16px'>INITIALIZING MULTI-AGENT PIPELINE</div>
            {done_html}{active_html}{portfolio_note}
        </div>"""

    for i, (a_color, a_icon, a_name, a_detail, done, _) in enumerate(stages):
        with status_box.container():
            st.markdown(render_status(done, a_color, a_icon, a_name, a_detail), unsafe_allow_html=True)
        time.sleep(1)

    try:
        result = run(portfolio=portfolio)
        st.session_state.result = result
        st.session_state.portfolio_used = portfolio
        status_box.empty()
    except Exception as e:
        st.error(f"Pipeline error: {e}")

# ── Placeholder ───────────────────────────────────────────────────────────────
if st.session_state.result is None:
    st.write("")
    st.info(
        "👆 Fill in your portfolio exposures (optional), then click **Run Analysis** to start the multi-agent pipeline. This takes ~30 seconds."
    )
    st.markdown(
        """
**How it works:**
1. 🔍 **Commodity Agent** — CMSI from live prices (Oil, Gold, Wheat, Copper, Natural Gas)
2. 🌍 **News Agent** — fetches and classifies headlines, scores geopolitical risk
3. ⚡ **Orchestrator** — combines scores into a Global Stress Index
4. 🛡️ **Hedge Agent** — generates hedging strategies via Amazon Nova, tailored to YOUR portfolio
    """
    )

# ── Results ───────────────────────────────────────────────────────────────────
if st.session_state.result is not None:
    result = st.session_state.result
    portfolio_used = st.session_state.portfolio_used or {}

    gsi = result["global_stress_index"]
    commodity = result["commodity"]
    geo = result["geo"]
    hedging = result["hedging"]
    color = stress_color(gsi)
    label = stress_label(gsi)

    c_score = commodity["analysis"].get(
        "cmsi_score", commodity["analysis"].get("stress_score", 0)
    )
    summary = geo.get("summary", {})

    # Sigmoid-normalized geo score (fixes the raw unbounded score bug)
    raw_geo = summary.get("risk_bias_weighted_score", 0)
    g_score = sigmoid_normalize(raw_geo)

    commodity_counts = summary.get("commodity_counts", {})
    top_risk = (
        max(
            (k for k in commodity_counts if k != "None" and k),
            key=lambda k: commodity_counts.get(k, 0),
            default="N/A",
        )
        if commodity_counts
        else "N/A"
    )

    # ── Portfolio context banner (if provided) ────────────────────────────────
    pu_exposures = portfolio_used.get("exposures", {})
    pu_total = portfolio_used.get("total_notional", 0)
    if pu_total > 0:
        active = {k: v for k, v in pu_exposures.items() if v > 0}
        tags = "".join(
            f"<span class='exposure-tag'>{k}: ${v:.0f}M</span>" for k, v in active.items()
        )
        st.markdown(
            f"""
        <div class='portfolio-summary-card'>
            <div style='font-family:Space Mono,monospace;font-size:9px;color:#00d4ff;
            letter-spacing:0.15em;margin-bottom:6px'>
                ✓ ANALYSIS TAILORED TO YOUR PORTFOLIO · ${pu_total:.0f}M TOTAL NOTIONAL
            </div>
            <div>{tags}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ── Global Stress Index ───────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'>GLOBAL STRESS INDEX</div>", unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown(
            f"""
        <div class='gsi-box'>
            <div class='gsi-label'>Global Stress Index</div>
            <div class='gsi-number' style='color:{color}'>{gsi}</div>
            <div class='gsi-status' style='color:{color}'>{label}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        c_color = stress_color(c_score)
        st.markdown(
            f"""
        <div class='agent-card'>
            <div class='agent-title' style='color:#ffcc00'>📦 Commodity Agent</div>
            <div class='agent-sub'>AMAZON NOVA PRO</div>
            <div class='agent-score' style='color:{c_color}'>{c_score}<span style='font-size:16px;color:#6a7fa8'>/100</span></div>
            <div class='spacer'></div>
            <div style='font-size:11px;color:#9bb0d4'>⚠️ Top concern: <b style='color:#ffcc00'>{commodity["analysis"].get("top_concern", "N/A")}</b></div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        g_color = stress_color(g_score)
        top_risk_display = (top_risk[:45] + "...") if len(str(top_risk)) > 45 else top_risk
        st.markdown(
            f"""
        <div class='agent-card'>
            <div class='agent-title' style='color:#ff6b35'>🌍 News Agent</div>
            <div class='agent-sub'>AMAZON NOVA PRO</div>
            <div class='agent-score' style='color:{g_color}'>{g_score}<span style='font-size:16px;color:#6a7fa8'>/100</span></div>
            <div class='spacer'></div>
            <div style='font-size:11px;color:#9bb0d4'>⚠️ Top in news: <b style='color:#ff6b35'>{top_risk_display}</b></div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.write("")

    # ── Live Commodity Prices ─────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'>LIVE COMMODITY PRICES</div>",
        unsafe_allow_html=True,
    )
    raw = commodity["raw_data"]
    cols = st.columns(len(raw))
    for i, (name, data) in enumerate(raw.items()):
        pct = data.get("pct_change_1d", data.get("pct_change", 0))
        dev = data.get("z_score_30d", data.get("deviation_from_30d_avg", 0))
        arrow = "▲" if pct > 0 else "▼"
        c = change_color(pct)
        if abs(dev) > 2.0:
            border = "#ff3b5c"
        elif abs(dev) > 1.0:
            border = "#ff6b35"
        elif abs(dev) > 0.5:
            border = "#ffcc00"
        else:
            border = "#1e2d4a"

        # Highlight if user has exposure in this commodity
        user_exp = pu_exposures.get(name, 0) if pu_exposures else 0
        exposure_badge = (
            f"<div style='font-family:Space Mono,monospace;font-size:9px;color:#00d4ff;"
            f"margin-top:4px'>📋 ${user_exp:.0f}M exposure</div>"
            if user_exp > 0 else ""
        )

        with cols[i]:
            st.markdown(
                f"""
            <div class='commodity-card' style='border-color:{border}'>
                <div class='commodity-name'>{name}</div>
                <div class='commodity-price' style='color:{border}'>${data.get("price", 0):,.2f}</div>
                <div class='commodity-change' style='color:{c}'>{arrow} {abs(pct):.2f}%</div>
                <div style='font-family:Space Mono,monospace;font-size:9px;color:#6a7fa8;margin-top:4px'>
                    z = {dev:+.2f} vs 30d
                </div>
                {exposure_badge}
            </div>
            """,
                unsafe_allow_html=True,
            )

    st.write("")
    st.write("")

    # ── Geo + Analysis columns ────────────────────────────────────────────────
    left, right = st.columns([1, 1])

    with left:
        st.markdown(
            "<div class='section-header'>GEOPOLITICAL SIGNALS</div>",
            unsafe_allow_html=True,
        )
        raw_headlines = summary.get("top_headlines", geo.get("articles", []))

        seen_titles = set()
        headlines = []

        for h in raw_headlines:
            title = h.get("title", "").strip().lower()
            if title and title not in seen_titles:
                headlines.append(h)
                seen_titles.add(title)

        headlines = headlines[:6]
        for article in headlines:
            title = article.get("title", "")
            source = article.get("source", article.get("source_name", ""))
            bucket = article.get("bucket", "")
            relevance = article.get("relevance", "")
            relevance_color = {"high": "#ff3b5c", "medium": "#ffcc00", "low": "#6a7fa8"}.get(relevance, "#6a7fa8")
            st.markdown(
                f"""
            <div class='headline-item'>
                <a href="{article.get('url', '#')}" target="_blank" style="color:#e2eaf8;text-decoration:none">
                    {title}
                </a>
                <span style='font-family:Space Mono,monospace;font-size:9px;color:#00d4ff'>
                    {source}{f' · {bucket}' if bucket else ''}
                </span>
                {f"<span style='font-family:Space Mono,monospace;font-size:9px;color:{relevance_color};margin-left:8px'>{relevance.upper()}</span>" if relevance else ""}
            </div>
            """,
                unsafe_allow_html=True,
            )
        st.write("")
        st.markdown("<div class='nova-label'>News risk summary</div>", unsafe_allow_html=True)
        risk_bias = summary.get("risk_bias", "N/A")
        headline_titles = "; ".join(h.get("title", "") for h in headlines[:3] if h.get("title"))
        geo_explanation = f"Risk bias: {risk_bias} (normalized score: {g_score}/100). Top signals: {headline_titles or 'none'}"
        st.markdown(
            f"<div class='overall-rec'>{geo_explanation}</div>",
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            "<div class='section-header'>COMMODITY RISK ANALYSIS</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='overall-rec'>{commodity['analysis'].get('explanation', 'N/A')}</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        st.write("")
        st.markdown(
            "<div class='section-header'>NOVA OVERALL RECOMMENDATION</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
        <div class='overall-rec'>
            <div class='nova-label'>Amazon Nova Pro</div>
            {hedging["overall_recommendation"]}
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.write("")

    # ── Hedging Strategies ────────────────────────────────────────────────────
    tailored_note = (
        f" <span style='color:#00d4ff;font-size:10px'>(tailored to your ${pu_total:.0f}M portfolio)</span>"
        if pu_total > 0 else ""
    )
    st.markdown(
        f"<div class='section-header'>DYNAMIC HEDGING STRATEGIES{tailored_note}</div>",
        unsafe_allow_html=True,
    )
    scols = st.columns(len(hedging["strategies"]))
    for i, strategy in enumerate(hedging["strategies"]):
        urgency = strategy.get("urgency", "medium").lower()
        with scols[i]:
            st.markdown(
                f"""
            <div class='strategy-card'>
                <div class='strategy-name'>{strategy["name"]}</div>
                <div class='urgency-{urgency}'>{urgency.upper()} URGENCY</div>
                <div class='strategy-action'>{strategy["action"]}</div>
                <div class='strategy-rationale'>💡 {strategy["rationale"]}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        """
    <div style='text-align:center;font-family:Space Mono,monospace;font-size:9px;color:#6a7fa8;letter-spacing:0.15em'>
        AEGIS · POWERED BY AMAZON NOVA PRO · MULTI-AGENT AGENTIC AI SYSTEM
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ── Agent Reasoning Trace ─────────────────────────────────────────────────
    st.write("")
    with st.expander("🧠 Agent Reasoning Trace — See how Nova thinks", expanded=False):
        trace = result.get("trace", {})

        t1, t2, t3, t4 = st.tabs(
            ["📦 Commodity Agent", "🌍 Geo Agent", "⚡ Orchestrator", "🛡️ Hedge Agent"]
        )

        with t1:
            for key, val in trace.get("commodity", {}).items():
                if key != "reasoning":
                    st.markdown(
                        f"""
                    <div style='font-family:Space Mono,monospace;font-size:11px;padding:8px 12px;
                    margin-bottom:6px;background:#0b1120;border-left:3px solid #ffcc00;border-radius:4px;color:#9bb0d4'>
                        <span style='color:#ffcc00'>{key.upper()}</span> &nbsp;→&nbsp; {val}
                    </div>""",
                        unsafe_allow_html=True,
                    )
            st.markdown(
                f"""
            <div style='margin-top:12px;padding:12px;background:rgba(255,204,0,0.05);
            border:1px solid rgba(255,204,0,0.2);border-radius:8px;font-size:12px;color:#e2eaf8;line-height:1.7'>
                <span style='font-family:Space Mono,monospace;font-size:9px;color:#ffcc00;
                letter-spacing:0.15em'>NOVA REASONING</span><br><br>
                {trace.get("commodity", {}).get("reasoning", "")}
            </div>""",
                unsafe_allow_html=True,
            )

        with t2:
            for key, val in trace.get("geo", {}).items():
                if key != "reasoning":
                    st.markdown(
                        f"""
                    <div style='font-family:Space Mono,monospace;font-size:11px;padding:8px 12px;
                    margin-bottom:6px;background:#0b1120;border-left:3px solid #ff6b35;border-radius:4px;color:#9bb0d4'>
                        <span style='color:#ff6b35'>{key.upper()}</span> &nbsp;→&nbsp; {val}
                    </div>""",
                        unsafe_allow_html=True,
                    )
            st.markdown(
                f"""
            <div style='margin-top:12px;padding:12px;background:rgba(255,107,53,0.05);
            border:1px solid rgba(255,107,53,0.2);border-radius:8px;font-size:12px;color:#e2eaf8;line-height:1.7'>
                <span style='font-family:Space Mono,monospace;font-size:9px;color:#ff6b35;
                letter-spacing:0.15em'>NOVA REASONING</span><br><br>
                {trace.get("geo", {}).get("reasoning", "")}
            </div>""",
                unsafe_allow_html=True,
            )

        with t3:
            for key, val in trace.get("orchestrator", {}).items():
                st.markdown(
                    f"""
                <div style='font-family:Space Mono,monospace;font-size:11px;padding:8px 12px;
                margin-bottom:6px;background:#0b1120;border-left:3px solid #00d4ff;border-radius:4px;color:#9bb0d4'>
                    <span style='color:#00d4ff'>{key.upper()}</span> &nbsp;→&nbsp; {val}
                </div>""",
                    unsafe_allow_html=True,
                )

        with t4:
            # Show portfolio context used in hedge agent
            if pu_total > 0:
                active_exp = {k: v for k, v in pu_exposures.items() if v > 0}
                exp_str = ", ".join(f"{k}: ${v:.0f}M" for k, v in active_exp.items())
                st.markdown(
                    f"""
                <div style='font-family:Space Mono,monospace;font-size:11px;padding:8px 12px;
                margin-bottom:6px;background:#0b1120;border-left:3px solid #00d4ff;border-radius:4px;color:#9bb0d4'>
                    <span style='color:#00d4ff'>PORTFOLIO INPUT</span> &nbsp;→&nbsp; {exp_str}
                    {f" | Notes: {portfolio_used.get('notes')}" if portfolio_used.get('notes') else ""}
                </div>""",
                    unsafe_allow_html=True,
                )
            for key, val in trace.get("hedge", {}).items():
                st.markdown(
                    f"""
                <div style='font-family:Space Mono,monospace;font-size:11px;padding:8px 12px;
                margin-bottom:6px;background:#0b1120;border-left:3px solid #7fff5f;border-radius:4px;color:#9bb0d4'>
                    <span style='color:#7fff5f'>{key.upper()}</span> &nbsp;→&nbsp; {val}
                </div>""",
                    unsafe_allow_html=True,
                )