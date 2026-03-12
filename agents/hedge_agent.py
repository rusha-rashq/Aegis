import json

import boto3
from dotenv import load_dotenv

load_dotenv()

client = boto3.client("bedrock-runtime", region_name="us-east-1")


def run(stress_score, commodity_analysis, geo_analysis):
    prompt = f"""You are a portfolio risk manager generating hedging strategies.

Global Stress Index: {stress_score}/100
Commodity concerns: {commodity_analysis}
Geopolitical concerns: {geo_analysis}

Based on this stress level, suggest 3 specific hedging strategies.
For each strategy explain WHY it's recommended given current conditions.

Respond in JSON:
{{
  "strategies": [
    {{"name": str, "action": str, "rationale": str, "urgency": "low|medium|high"}}
  ],
  "overall_recommendation": str
}}
Return only JSON, no extra text."""

    response = client.invoke_model(
        modelId="amazon.nova-pro-v1:0",
        body=json.dumps(
            {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": 600},
            }
        ),
    )
    text = json.loads(response["body"].read())["output"]["message"]["content"][0][
        "text"
    ]
    return json.loads(text.strip())
