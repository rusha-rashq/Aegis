import json

import boto3
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

client = boto3.client("bedrock-runtime", region_name="us-east-1")

COMMODITIES = {
    "Oil": "CL=F",
    "Gold": "GC=F",
    "Wheat": "ZW=F",
    "Copper": "HG=F",
    "Natural Gas": "NG=F",
}


def fetch_commodity_data():
    results = {}
    for name, ticker in COMMODITIES.items():
        hist = yf.Ticker(ticker).history(period="30d")
        if len(hist) >= 2:
            latest = hist["Close"].iloc[-1]
            avg_30d = hist["Close"].mean()
            pct_change = (
                (latest - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2]
            ) * 100
            deviation = ((latest - avg_30d) / avg_30d) * 100
            results[name] = {
                "price": round(latest, 2),
                "pct_change": round(pct_change, 2),
                "deviation_from_30d_avg": round(deviation, 2),
            }
    return results


def analyze(data):
    prompt = f"""You are a commodity market stress analyst.
Given this commodity data: {json.dumps(data)}
1. Score overall stress level 0-100
2. Identify the most concerning commodity
3. Give a 2-sentence explanation

Respond in JSON: {{"stress_score": int, "top_concern": str, "explanation": str}}
Return only JSON, no extra text."""

    response = client.invoke_model(
        modelId="amazon.nova-pro-v1:0",
        body=json.dumps(
            {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": 300},
            }
        ),
    )
    text = json.loads(response["body"].read())["output"]["message"]["content"][0][
        "text"
    ]
    return json.loads(text.strip())


def run():
    data = fetch_commodity_data()
    analysis = analyze(data)
    return {"raw_data": data, "analysis": analysis}
