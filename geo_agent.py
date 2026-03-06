import json
import os

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

client = boto3.client("bedrock-runtime", region_name="us-east-1")


def fetch_news():
    api_key = os.getenv("NEWS_API_KEY")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "sanctions OR conflict OR war OR supply disruption OR geopolitical",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 10,
        "apiKey": api_key,
    }
    res = requests.get(url, params=params)
    articles = res.json().get("articles", [])
    return [{"title": a["title"], "source": a["source"]["name"]} for a in articles]


def analyze(articles):
    prompt = f"""You are a geopolitical risk analyst.
Given these recent news headlines: {json.dumps(articles)}
1. Score geopolitical stress level 0-100
2. Identify the top risk event
3. Give a 2-sentence explanation of market implications

Respond in JSON: {{"stress_score": int, "top_risk": str, "explanation": str}}
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
    articles = fetch_news()
    analysis = analyze(articles)
    return {"articles": articles, "analysis": analysis}
