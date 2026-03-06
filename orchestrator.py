from agents import commodity_agent, geo_agent, hedge_agent


def run():
    print("🔍 Running Commodity Agent...")
    commodity_result = commodity_agent.run()

    print("🌍 Running Geo Agent...")
    geo_result = geo_agent.run()

    # Combine scores into Global Stress Index
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

    return {
        "global_stress_index": global_stress,
        "commodity": commodity_result,
        "geo": geo_result,
        "hedging": hedge_result,
    }
