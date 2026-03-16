# ⚡ AEGIS — Agentic Global Intelligence System

> A production-grade multi-agent AI system that monitors commodity markets and geopolitical events in real time, computes a **Global Stress Index (0–100)**, and generates dynamic, portfolio-aware hedging strategies — powered by **Amazon Nova Pro** on AWS Bedrock.

---

## 🧠 What is AEGIS?

AEGIS coordinates three specialized AI agents through a central orchestrator. Each agent focuses on a distinct domain of global risk, producing structured outputs that the orchestrator synthesizes into a unified stress assessment and actionable portfolio recommendations.

This architecture mirrors how real-world risk desks operate — a commodity quant, a geopolitical analyst, and a portfolio risk manager each contribute domain-specific intelligence, and a senior strategist synthesizes it into strategy.

---

🚀 **Live Demo**: [agenticglobalintelligencesystemaegis1.streamlit.app](https://agenticglobalintelligencesystemaegis1.streamlit.app/)

## 🏗️ System Architecture

```
                    ┌──────────────────────────────────┐
                    │           ORCHESTRATOR            │
                    │   Computes Global Stress Index    │
                    │   Sigmoid-normalizes geo score    │
                    │   Builds full reasoning trace     │
                    └────────┬──────────┬──────────────┘
                             │          │
              ┌──────────────▼──┐   ┌───▼──────────────────┐
              │  Commodity Agent │   │     News Agent        │
              │    (CMSI)        │   │  (News Intelligence)  │
              │                  │   │                       │
              │  4-component     │   │  Tier 1: NewsAPI      │
              │  stress index    │   │  Tier 2: Institutional│
              │  via yfinance    │   │  Nova classification  │
              │  + Nova Pro      │   │  + risk scoring       │
              └──────────────────┘   └───────────────────────┘
                             │          │
                    ┌────────▼──────────▼────────┐
                    │        Hedge Agent          │
                    │                             │
                    │  Nova Pro → 3 portfolio-    │
                    │  tailored strategies        │
                    └─────────────────────────────┘
```

---

## 🔬 Agent Deep-Dives

### 📦 Commodity Agent — CMSI (Commodity Market Stress Index)

A four-component composite stress index inspired by BIS-style monitoring methodology:

| Sub-Index | Weight | Description |
|---|---|---|
| **PDI** — Price Deviation Index | 40% | \|z-score\| of current price vs. 30-day rolling mean, capped at 3σ |
| **VRI** — Volatility Regime Index | 30% | Ratio of 10-day realized vol to 60-day baseline + vol percentile rank |
| **MSI** — Momentum Stress Index | 15% | Heuristic RSI-based overstretch score (overbought OR oversold) |
| **CCI** — Correlation Contagion Index | 15% | Absolute increase in avg pairwise cross-commodity correlation (20d vs 60d baseline) |

**Commodity universe with economic significance weights:**

| Commodity | Ticker | Weight | Rationale |
|---|---|---|---|
| Oil | CL=F | 35% | Primary energy input; documented cross-commodity spillover |
| Gold | GC=F | 20% | Safe-haven and inflation signal |
| Natural Gas | NG=F | 20% | Energy market stress indicator |
| Wheat | ZW=F | 15% | Food security and agricultural supply signal |
| Copper | HG=F | 10% | Industrial demand bellwether |

**Term structure** (contango/backwardation) is computed for narrative context using Working's (1949) storage theory but is **not included in the CMSI score**.

**Academic references:**
- Aldasoro, Hördahl & Zhu (BIS Quarterly Review, Sep 2022) — composite stress monitoring
- Avalos & Huang (BIS Quarterly Review, Sep 2022) — commodity spillovers
- Gorton & Rouwenhorst (Financial Analysts Journal, 2006) — commodity futures risk premiums
- Billio, Getmansky, Lo & Pelizzon (JFE, 2012) — connectedness and systemic risk
- Working (American Economic Review, 1949) — theory of the price of storage

---

### 🌍 News Agent — Geopolitical Intelligence

A two-tier news intelligence system:

**Tier 1 — Real-time wire services (NewsAPI)**
Trusted sources: Reuters, Bloomberg, Associated Press, BBC News, Financial Times, Wall Street Journal, The Guardian, CNBC, S&P Global Commodity Insights, Argus Media, ICIS, EIA, USDA

**Tier 2 — Institutional research (web-scraped public pages)**
J.P. Morgan Global Research, Goldman Sachs Insights, BlackRock Investment Institute, UBS Chief Investment Office, Morgan Stanley Research, Vanguard Economic & Market Outlook

> **Note:** Full institutional research (e.g. Goldman Sachs Commodity Views, JPM Global Commodities Strategy) requires Bloomberg Terminal or authenticated client portal access. AEGIS scrapes public insights pages only.

**Nova Pro classifies each article into signal buckets:**

| Bucket | Description |
|---|---|
| `war_conflict` | Armed conflict, military strikes, invasions |
| `shipping_disruption` | Blockades, Red Sea, Hormuz, Suez, piracy |
| `sanctions_trade` | Sanctions, trade wars, export bans, embargoes |
| `opec_policy` | OPEC+ production decisions, quota changes |
| `energy_infrastructure` | Pipeline, refinery, grid attacks or outages |
| `export_restriction` | Unilateral export bans, grain corridor disruption |
| `deescalation` | Ceasefire, peace talks, sanctions lifted |
| `institutional_view` | Bank/asset manager market outlook or forecast |

**Risk bias scoring** uses weighted relevance × confidence scoring (not raw article counts), so a single high-confidence invasion article correctly outweighs ten low-confidence OPEC policy notes.

**Academic references:**
- Caldara & Iacoviello (AER, 2022) — measuring geopolitical risk
- Baker, Bloom & Davis (QJE, 2016) — economic policy uncertainty
- Kilian (Annual Review of Resource Economics, 2014) — oil price shocks

---

### ⚡ Orchestrator — Global Stress Index

Combines both agent outputs into a single GSI using sigmoid normalization:

```
# Geo score: sigmoid-normalizes unbounded raw score to [0, 100]
# raw = 0  → 50 (neutral)
# raw = 5  → 73 (elevated)
# raw = 10 → 92 (high)
g_score = round(100 / (1 + exp(-0.25 × raw_geo_score)))

# Global Stress Index: equal-weight composite
GSI = round(0.5 × CMSI_score + 0.5 × g_score)
```

The orchestrator also builds a full **reasoning trace** — a step-by-step log of every decision each agent made, exposed in the dashboard.

---

### 🛡️ Hedge Agent — Portfolio-Aware Strategies

Receives the GSI, full CMSI analysis, and geopolitical signals from the news agent. If a user portfolio is provided (commodity exposures in $M notional), Nova generates strategies **tailored to that specific portfolio** — referencing dollar amounts and prioritizing the largest exposures.

Without a portfolio, it generates generic market-level strategies.

**Instruments Nova may recommend:** CME/NYMEX/CBOT futures, listed options, OTC swaps, basis swaps, cross-commodity spreads.

---

## 📊 Global Stress Index Reference

| Score | Classification | Color | Posture |
|---|---|---|---|
| 0–29 | Low Risk | 🟢 Green | Minimal hedging needed |
| 30–59 | Elevated | 🟡 Yellow | Monitor closely |
| 60–79 | High Risk | 🟠 Orange | Active hedging recommended |
| 80–100 | Critical | 🔴 Red | Maximum defensive posture |

---

## ✨ Features

- **CMSI** — 4-component commodity stress index (PDI + VRI + MSI + CCI) with academic grounding
- **Dual-tier news intelligence** — wire services + institutional research, parallel scraping
- **Per-article Nova classification** — 8 signal buckets, weighted risk bias scoring
- **Sigmoid-normalized geo score** — properly commensurable with CMSI on [0, 100]
- **Portfolio-aware hedging** — strategies reference your actual dollar exposures
- **Agent reasoning trace** — full transparency into every agent decision
- **Live pipeline animation** — visual step-by-step indicator as each agent fires
- **Fallback handling** — rule-based explanations if Nova is unavailable

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| AI Models | Amazon Nova Pro via AWS Bedrock |
| Agent Orchestration | Custom Python multi-agent framework |
| Market Data | yfinance (Yahoo Finance futures) |
| News — Tier 1 | NewsAPI |
| News — Tier 2 | BeautifulSoup4 (institutional public pages) |
| Parallel processing | ThreadPoolExecutor |
| Frontend | Streamlit |
| Cloud | AWS Bedrock + IAM |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- AWS account with Bedrock access (Amazon Nova Pro enabled in `us-east-1`)
- NewsAPI key — free at [newsapi.org](https://newsapi.org)

### Installation

```bash
git clone https://github.com/rusha-rashq/Aegis.git
cd Aegis
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the root directory:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
NEWS_API_KEY=your_newsapi_key
```

### Enable Amazon Nova Pro on AWS

1. Log into [AWS Console](https://console.aws.amazon.com)
2. Search **Bedrock** → **Foundation Models**
3. Find **Amazon Nova Pro** → enable model access
4. Confirm region is `us-east-1`
5. Go to **IAM** → create a user with `AmazonBedrockFullAccess` → generate access keys

### Run

```bash
# Test the full agent pipeline
python3 -c "from agents.orchestrator import run; import json; print(json.dumps(run(), indent=2, default=str))"

# Launch the dashboard
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) and click **Run Analysis**.

---

## 📁 Project Structure

```
Aegis/
├── agents/
│   ├── __init__.py          # Package init
│   ├── orchestrator.py      # GSI computation, sigmoid normalization, reasoning trace
│   ├── commodity_agent.py   # CMSI: PDI + VRI + MSI + CCI + Nova narrative
│   ├── news_agent.py        # Dual-tier fetch, Nova classification, risk bias scoring
│   └── hedge_agent.py       # Portfolio-aware strategy generation via Nova
├── app.py                   # Streamlit dashboard
├── requirements.txt         # Python dependencies
├── .env                     # Secret credentials (never committed)
├── .gitignore
└── README.md
```

---

## 👥 Team

Built for the **Amazon Nova Hackathon** by:

- **[Rushali Dhar](https://github.com/rusha-rashq)** — Purdue University, MS Software Engineering
- **[Anoushka Sinha](https://github.com/A-S-inha)** — University of Southern California, MS Computer Science

---

## 📄 License

MIT License — free to use, modify, and distribute.
