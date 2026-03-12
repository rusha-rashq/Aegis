import json

import streamlit as st

from agents.orchestrator import run

# ── Page config ──────────────────────────────────────────────────────────────
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


def safe_parse(text):
    import re

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse response: {text}")


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

# ── Session state ─────────────────────────────────────────────────────────────
if "result" not in st.session_state:
    st.session_state.result = None

if run_analysis:
    status_box = st.empty()

    with status_box.container():
        st.markdown(
            """
        <div style='background:#0b1120;border:1px solid #1e2d4a;border-radius:12px;padding:1.5rem;'>
            <div style='font-family:Space Mono,monospace;font-size:11px;color:#6a7fa8;letter-spacing:0.15em;margin-bottom:16px'>
                INITIALIZING MULTI-AGENT PIPELINE
            </div>
            <div id='log' style='font-family:Space Mono,monospace;font-size:12px;line-height:2'>
                <div style='color:#ffcc00'>⟳ &nbsp;Commodity Agent — fetching live market data...</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    import time

    time.sleep(1)

    with status_box.container():
        st.markdown(
            """
        <div style='background:#0b1120;border:1px solid #1e2d4a;border-radius:12px;padding:1.5rem;'>
            <div style='font-family:Space Mono,monospace;font-size:11px;color:#6a7fa8;letter-spacing:0.15em;margin-bottom:16px'>
                INITIALIZING MULTI-AGENT PIPELINE
            </div>
            <div style='font-family:Space Mono,monospace;font-size:12px;line-height:2'>
                <div style='color:#7fff5f'>✓ &nbsp;Commodity Agent — complete</div>
                <div style='color:#ff6b35'>⟳ &nbsp;Geo Agent — scanning geopolitical headlines...</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    time.sleep(1)

    with status_box.container():
        st.markdown(
            """
        <div style='background:#0b1120;border:1px solid #1e2d4a;border-radius:12px;padding:1.5rem;'>
            <div style='font-family:Space Mono,monospace;font-size:11px;color:#6a7fa8;letter-spacing:0.15em;margin-bottom:16px'>
                INITIALIZING MULTI-AGENT PIPELINE
            </div>
            <div style='font-family:Space Mono,monospace;font-size:12px;line-height:2'>
                <div style='color:#7fff5f'>✓ &nbsp;Commodity Agent — complete</div>
                <div style='color:#7fff5f'>✓ &nbsp;Geo Agent — complete</div>
                <div style='color:#00d4ff'>⟳ &nbsp;Orchestrator — computing Global Stress Index...</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    time.sleep(1)

    with status_box.container():
        st.markdown(
            """
        <div style='background:#0b1120;border:1px solid #1e2d4a;border-radius:12px;padding:1.5rem;'>
            <div style='font-family:Space Mono,monospace;font-size:11px;color:#6a7fa8;letter-spacing:0.15em;margin-bottom:16px'>
                INITIALIZING MULTI-AGENT PIPELINE
            </div>
            <div style='font-family:Space Mono,monospace;font-size:12px;line-height:2'>
                <div style='color:#7fff5f'>✓ &nbsp;Commodity Agent — complete</div>
                <div style='color:#7fff5f'>✓ &nbsp;Geo Agent — complete</div>
                <div style='color:#7fff5f'>✓ &nbsp;Orchestrator — complete</div>
                <div style='color:#7fff5f'>⟳ &nbsp;Hedge Agent — generating strategies...</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    try:
        result = run()
        st.session_state.result = result
        status_box.empty()
    except Exception as e:
        st.error(f"Pipeline error: {e}")

# ── Placeholder ───────────────────────────────────────────────────────────────
if st.session_state.result is None:
    st.write("")
    st.info(
        "👆 Click **Run Analysis** to start the multi-agent pipeline. This takes ~30 seconds as all agents call Amazon Nova."
    )
    st.markdown(
        """
**How it works:**
1. 🔍 **Commodity Agent** — fetches live prices for Oil, Gold, Wheat, Copper, Natural Gas
2. 🌍 **Geo Agent** — scans geopolitical headlines and scores risk
3. ⚡ **Orchestrator** — combines scores into a Global Stress Index
4. 🛡️ **Hedge Agent** — generates dynamic hedging strategies via Amazon Nova
    """
    )

if st.session_state.result is not None:
    result = st.session_state.result
    gsi = result["global_stress_index"]
    commodity = result["commodity"]
    geo = result["geo"]
    hedging = result["hedging"]
    color = stress_color(gsi)
    label = stress_label(gsi)

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
        c_score = commodity["analysis"]["stress_score"]
        c_color = stress_color(c_score)
        st.markdown(
            f"""
        <div class='agent-card'>
            <div class='agent-title' style='color:#ffcc00'>📦 Commodity Agent</div>
            <div class='agent-sub'>AMAZON NOVA PRO</div>
            <div class='agent-score' style='color:{c_color}'>{c_score}<span style='font-size:16px;color:#6a7fa8'>/100</span></div>
            <div class='spacer'></div>
            <div style='font-size:11px;color:#9bb0d4'>⚠️ Top concern: <b style='color:#ffcc00'>{commodity["analysis"]["top_concern"]}</b></div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        g_score = geo["analysis"]["stress_score"]
        g_color = stress_color(g_score)
        st.markdown(
            f"""
        <div class='agent-card'>
            <div class='agent-title' style='color:#ff6b35'>🌍 Geo Agent</div>
            <div class='agent-sub'>AMAZON NOVA PRO</div>
            <div class='agent-score' style='color:{g_color}'>{g_score}<span style='font-size:16px;color:#6a7fa8'>/100</span></div>
            <div class='spacer'></div>
            <div style='font-size:11px;color:#9bb0d4'>⚠️ Top risk: <b style='color:#ff6b35'>{geo["analysis"]["top_risk"][:45]}...</b></div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.write("")

    # ── Commodity Prices ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'>LIVE COMMODITY PRICES</div>",
        unsafe_allow_html=True,
    )
    raw = commodity["raw_data"]
    cols = st.columns(len(raw))
    for i, (name, data) in enumerate(raw.items()):
        pct = data["pct_change"]
        dev = data["deviation_from_30d_avg"]
        arrow = "▲" if pct > 0 else "▼"
        c = change_color(pct)
        if abs(dev) > 20:
            border = "#ff3b5c"
        elif abs(dev) > 10:
            border = "#ff6b35"
        elif abs(dev) > 5:
            border = "#ffcc00"
        else:
            border = "#1e2d4a"
        with cols[i]:
            st.markdown(
                f"""
            <div class='commodity-card' style='border-color:{border}'>
                <div class='commodity-name'>{name}</div>
                <div class='commodity-price' style='color:{border}'>${data["price"]:,.2f}</div>
                <div class='commodity-change' style='color:{c}'>{arrow} {abs(pct):.2f}%</div>
                <div style='font-family:Space Mono,monospace;font-size:9px;color:#6a7fa8;margin-top:4px'>
                    {'+' if dev > 0 else ''}{dev:.1f}% vs 30d avg
                </div>
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
        for article in geo["articles"][:6]:
            st.markdown(
                f"""
            <div class='headline-item'>
                <span style='color:#e2eaf8'>{article["title"]}</span><br>
                <span style='font-family:Space Mono,monospace;font-size:9px;color:#00d4ff'>{article["source"]}</span>
            </div>
            """,
                unsafe_allow_html=True,
            )
        st.write("")
        st.markdown(
            "<div class='nova-label'>Nova Analysis</div>", unsafe_allow_html=True
        )
        st.markdown(
            f"""
        <div class='overall-rec'>{geo["analysis"]["explanation"]}</div>
        """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            "<div class='section-header'>COMMODITY RISK ANALYSIS</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
        <div class='overall-rec'>{commodity["analysis"]["explanation"]}</div>
        """,
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
    st.markdown(
        "<div class='section-header'>DYNAMIC HEDGING STRATEGIES</div>",
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
            for key, val in trace.get("hedge", {}).items():
                st.markdown(
                    f"""
                <div style='font-family:Space Mono,monospace;font-size:11px;padding:8px 12px;
                margin-bottom:6px;background:#0b1120;border-left:3px solid #7fff5f;border-radius:4px;color:#9bb0d4'>
                    <span style='color:#7fff5f'>{key.upper()}</span> &nbsp;→&nbsp; {val}
                </div>""",
                    unsafe_allow_html=True,
                )
