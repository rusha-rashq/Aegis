# ⚡ AEGIS — Agentic Global Intelligence System

> A multi-agent AI system that monitors commodity markets and geopolitical events in real time, computes a **Global Stress Index**, and generates dynamic hedging strategies — powered by **Amazon Nova Pro** on AWS Bedrock.

---

## 🧠 What is AEGIS?

AEGIS is a multi-agent agentic AI system built for the **Agentic AI** category. Rather than using a single AI model, AEGIS coordinates four specialized agents that each focus on a distinct domain. The agents communicate through a central orchestrator, which synthesizes their findings into a unified risk assessment and clear, plain-English hedging recommendations.

This architecture mirrors how real-world risk desks operate — specialists gather domain-specific signals, and a senior analyst synthesizes them into actionable strategy.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│              (Coordinates all agents)                    │
│         Computes Global Stress Index (0–100)             │
└────────┬──────────────┬──────────────┬──────────────────┘
         │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌───▼──────┐
    │Commodity│   │    Geo    │  │  Hedge   │
    │ Agent   │   │  Agent    │  │  Agent   │
    │         │   │           │  │          │
    │ yfinance│   │ NewsAPI   │  │Nova Pro  │
    │ + Nova  │   │ + Nova    │  │          │
    └─────────┘   └───────────┘  └──────────┘
```

### Agent Descriptions

**📦 Commodity Agent**
Fetches 30-day price history for Oil, Gold, Wheat, Copper, and Natural Gas using `yfinance`. Computes deviation from 30-day moving averages and percentage changes. Sends this data to Amazon Nova Pro, which scores commodity market stress from 0–100 and identifies the top concern.

**🌍 Geo Agent**
Queries NewsAPI for the latest geopolitical headlines using targeted keywords (sanctions, war, conflict, supply disruption). Filters out noise and irrelevant articles, then sends the cleaned headlines to Amazon Nova Pro, which scores geopolitical risk from 0–100 and explains market implications.

**⚡ Orchestrator**
Receives scores from the Commodity and Geo agents. Computes the Global Stress Index as a weighted average: `GSI = 0.5 × commodity_score + 0.5 × geo_score`. Classifies the result as Low Risk / Elevated / High Risk / Critical.

**🛡️ Hedge Agent**
Receives the Global Stress Index and full analysis context from both agents. Sends everything to Amazon Nova Pro, which generates 3 prioritized, context-aware hedging strategies — each with a specific action, rationale, and urgency level.

---

## ✨ Features

- **Real-time commodity monitoring** — Oil, Gold, Wheat, Copper, Natural Gas with 30-day deviation tracking
- **Geopolitical news analysis** — Live headlines filtered for relevance, scored by Nova
- **Global Stress Index** — A composite 0–100 score, color-coded by severity
- **Dynamic hedging strategies** — 3 tailored recommendations that adapt to current stress levels
- **Agent reasoning trace** — Judges and users can see exactly what each agent did and why
- **Live pipeline animation** — Visual indicator showing each agent firing in sequence
- **Plain-English explanations** — Nova explains the *why* behind every recommendation

---

## 🖥️ Dashboard

The Streamlit dashboard shows:

| Section | Description |
|---|---|
| Global Stress Index | Large score with color coding (green → yellow → orange → red) |
| Agent Cards | Individual scores from Commodity and Geo agents |
| Live Commodity Prices | 5 commodities with price, % change, and 30d deviation |
| Geopolitical Signals | Filtered live headlines with Nova's analysis |
| Commodity Risk Analysis | Nova's explanation of market stress |
| Nova Recommendation | Overall portfolio recommendation |
| Dynamic Hedging Strategies | 3 strategies with urgency levels and rationale |
| Agent Reasoning Trace | Expandable step-by-step view of each agent's thinking |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| AI Models | Amazon Nova Pro via AWS Bedrock |
| Agent Orchestration | Custom Python multi-agent framework |
| Market Data | yfinance |
| News Data | NewsAPI |
| Frontend | Streamlit |
| Cloud | AWS (Bedrock, IAM) |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.14+
- AWS account with Bedrock access (Amazon Nova Pro enabled)
- NewsAPI key — free at [newsapi.org](https://newsapi.org)

### Installation

```bash
git clone https://github.com/yourusername/aegis.git
cd aegis
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

### Enable Amazon Nova on AWS

1. Log into [AWS Console](https://console.aws.amazon.com)
2. Navigate to **Bedrock → Foundation Models**
3. Find **Amazon Nova Pro** and enable access
4. Make sure your region is set to `us-east-1`

### Run

```bash
# Test Nova connection
python3 test_nova.py

# Test the full agent pipeline
python3 -c "from agents.orchestrator import run; import json; print(json.dumps(run(), indent=2))"

# Launch the dashboard
streamlit run app.py
```

---

## 📁 Project Structure

```
aegis/
├── agents/
│   ├── __init__.py          # Package init
│   ├── orchestrator.py      # Coordinates agents, computes GSI, builds reasoning trace
│   ├── commodity_agent.py   # Fetches market data, scores commodity stress via Nova
│   ├── geo_agent.py         # Fetches news, filters noise, scores geopolitical risk via Nova
│   └── hedge_agent.py       # Generates hedging strategies via Nova
├── app.py                   # Streamlit dashboard
├── requirements.txt         # Python dependencies
├── .env                     # Secret credentials (never commit)
├── .gitignore
└── README.md
```

---

## 📊 Global Stress Index Scoring

| Score | Level | Color | Description |
|---|---|---|---|
| 0–29 | Low Risk | 🟢 Green | Markets calm, minimal hedging needed |
| 30–59 | Elevated | 🟡 Yellow | Moderate stress, monitor closely |
| 60–79 | High Risk | 🟠 Orange | Significant stress, active hedging recommended |
| 80–100 | Critical | 🔴 Red | Extreme stress, maximum defensive posture |

---

## 🔍 Agent Reasoning Trace

One of AEGIS's key features is full transparency into agent decision-making. After each analysis run, users can expand the **Agent Reasoning Trace** panel to see:

- What data each agent received
- What it sent to Amazon Nova Pro
- What score Nova returned and why
- How the orchestrator combined scores into the final GSI
- What context the Hedge Agent used to generate strategies

This makes AEGIS auditable and explainable — critical for real-world financial applications.

---

## 👥 Team

Built at **Amazon Nova AI Hackathon** by:

- **Rushali Dhar** — Purdue University, MS Software Engineering
- **Anoushka Sinha** — University of Southern California, MS Computer Science

---

## 📄 License

MIT License — feel free to use, modify, and distribute.
