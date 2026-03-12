from agents import commodity_agent, geo_agent, hedge_agent


def run():
    print("🔍 Running Commodity Agent...")
    commodity_result = commodity_agent.run()

    print("🌍 Running Geo Agent...")
    geo_result = geo_agent.run()

    c_score = commodity_result["analysis"]["stress_score"]
    g_score = geo_result["analysis"]["stress_score"]
    global_stress = round(0.5 * c_score + 0.5 * g_score)

    print(f"⚡ Global Stress Index: {global_stress}/100")
    print("🛡️ Running Hedge Agent...")

    hedge_result = hedge_agent.run(
        stress_score=global_stress,
        commodity_analysis=commodity_result["analysis"],
        geo_analysis=geo_result["analysis"],
    )

    # Build reasoning trace for each agent
    trace = {
        "commodity": {
            "step1": "Fetched 30-day price history for Oil, Gold, Wheat, Copper, Natural Gas via yfinance",
            "step2": f"Detected anomaly: Oil deviation from 30d avg = {commodity_result['raw_data']['Oil']['deviation_from_30d_avg']}%",
            "step3": "Sent price data to Amazon Nova Pro for stress scoring",
            "step4": f"Nova returned stress score: {c_score}/100, top concern: {commodity_result['analysis']['top_concern']}",
            "reasoning": commodity_result["analysis"]["explanation"],
        },
        "geo": {
            "step1": f"Fetched {len(geo_result['articles'])} geopolitical headlines from NewsAPI",
            "step2": "Filtered noise keywords, kept only geopolitical signals",
            "step3": "Sent headlines to Amazon Nova Pro for risk scoring",
            "step4": f"Nova returned stress score: {g_score}/100, top risk: {geo_result['analysis']['top_risk']}",
            "reasoning": geo_result["analysis"]["explanation"],
        },
        "orchestrator": {
            "step1": f"Received commodity score: {c_score}/100",
            "step2": f"Received geo score: {g_score}/100",
            "step3": f"Computed Global Stress Index: (0.5 × {c_score}) + (0.5 × {g_score}) = {global_stress}",
            "step4": f"Classified as: {'LOW RISK' if global_stress < 30 else 'ELEVATED' if global_stress < 60 else 'HIGH RISK' if global_stress < 80 else 'CRITICAL'}",
        },
        "hedge": {
            "step1": f"Received Global Stress Index: {global_stress}/100",
            "step2": "Passed commodity + geo analysis context to Amazon Nova Pro",
            "step3": f"Nova generated {len(hedge_result['strategies'])} hedging strategies",
            "step4": hedge_result["overall_recommendation"],
        },
    }

    return {
        "global_stress_index": global_stress,
        "commodity": commodity_result,
        "geo": geo_result,
        "hedging": hedge_result,
        "trace": trace,
    }
