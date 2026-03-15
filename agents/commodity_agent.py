"""
Commodity Market Stress Index (CMSI)
=====================================

Project-specific methodology inspired by:

  - Aldasoro, I., Hördahl, P. & Zhu, S. (BIS Quarterly Review, Sep 2022),
    "Under pressure: market conditions and stress"
    -> Motivates the composite multi-signal monitoring approach: the authors show
       that combining price, volatility, and market-structure signals into a single
       dashboard indicator provides earlier and more reliable stress warnings than
       any single metric alone.

  - Avalos, F. & Huang, W. (BIS Quarterly Review, Sep 2022),
    "Commodity markets: shocks and spillovers"
    -> Justifies treating commodities as an interconnected system rather than
       monitoring each market in isolation. Energy price shocks spill into
       agricultural and metals markets via substitution and input-cost channels,
       which is exactly what the CCI is designed to detect.

  - Gorton, G. & Rouwenhorst, K.G. (Financial Analysts Journal, 2006),
    "Facts and Fantasies About Commodity Futures"
    -> Establishes commodity futures as a distinct macro/financial asset class
       with risk-premium dynamics driven by hedging pressure, basis, and roll yield.
       Motivates tracking futures prices rather than spot prices.

  - Billio, M., Getmansky, M., Lo, A.W. & Pelizzon, L.
    (Journal of Financial Economics, vol. 104(3), 2012),
    "Econometric measures of connectedness and systemic risk in the
     finance and insurance sectors"
    -> Supports the CCI design: the authors show that rising pairwise
       connectedness across asset classes is a measurable leading indicator
       of systemic stress. The CCI operationalises this idea by tracking
       increases in average cross-commodity correlation versus a baseline.
       NOTE: The CCI here is a simplified proxy. Billio et al. use formal
       Granger-causality networks; this code uses rolling Pearson correlation.

  - Working, H. (American Economic Review, 1949),
    "The Theory of the Price of Storage"
    -> Foundational reference for the term-structure (contango / backwardation)
       analysis. Working showed that the basis between nearby and deferred
       futures contracts reflects storage costs plus a convenience yield,
       and that its sign carries information about supply tightness.


Important
---------
This CMSI is NOT a published institutional benchmark.
It is a project-specific composite dashboard that combines interpretable market signals.

Components
----------
The CMSI combines four sub-indices:

    1. Price Deviation Index (PDI)
       - |z-score| of the current futures price vs. its 30-day rolling mean.
       - Captures abnormal price dislocations relative to recent history.
       - Mapped to [0, 100] with a 3-sigma cap (3sigma -> 100).

    2. Volatility Regime Index (VRI)
       - Ratio of 10-day realized volatility to 60-day historical volatility.
       - Detects volatility regime changes independently of price direction.
       - 70% weight on the ratio score + 30% weight on the vol percentile rank.

    3. Momentum Stress Index (MSI)
       - Heuristic overstretch score derived from the 14-period RSI.
       - Stress is high when RSI is in extreme zones (overbought OR oversold).
       - Explicitly a heuristic, not a canonical institutional metric.

    4. Correlation Contagion Index (CCI)
       - Measures the absolute increase in average pairwise cross-commodity
         correlation over a recent 20-day window versus a 60-day baseline.
       - A rising CCI indicates co-movement stress.
       - Mapped to [0, 100]: +0.00 increase -> 0, +0.30 increase -> 100.
       - This is a simplified proxy. It is NOT a formal contagion test.

Portfolio-level CMSI aggregation weights:
    PDI: 40% | VRI: 30% | MSI: 15% | CCI: 15%

Notes
-----
- PDI and VRI are the most defensible, institutionally grounded components.
- MSI is a technical heuristic; treat its readings as supplementary context.
- CCI is a simplified connectedness proxy; a spike signals co-movement stress
  but should not be interpreted as proof of structural contagion.
- Term structure is computed for narrative context only and is NOT in the CMSI score.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import boto3
import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("cmsi")

# ---------------------------------------------------------------------------
# Universe & weights
# ---------------------------------------------------------------------------

# Nearby (front-month) continuous futures contracts via Yahoo Finance.
# Using futures rather than spot prices is consistent with Gorton &
# Rouwenhorst (2006): futures prices embed hedging pressure and storage
# economics that spot prices do not capture.
COMMODITIES: Dict[str, str] = {
    "Oil": "CL=F",
    "Gold": "GC=F",
    "Wheat": "ZW=F",
    "Copper": "HG=F",
    "Natural Gas": "NG=F",
}

# Front-month vs. deferred-month ticker pairs for term-structure context.
# Positive basis (front > deferred) = backwardation (supply tightness).
# Negative basis (front < deferred) = contango (storage surplus).
# Theoretical grounding: Working (1949).
TERM_STRUCTURE_PAIRS: Dict[str, Tuple[str, str]] = {
    "Oil": ("CL=F", "CLZ25.NYM"),
    "Natural Gas": ("NG=F", "NGZ25.NYM"),
    "Gold": ("GC=F", "GCZ25.CMX"),
}

# Economic-significance weights reflecting each commodity's share of
# global trade flows and macro sensitivity.
# Oil dominates (0.35) given its role as a primary energy input and its
# documented cross-commodity spillover effects (Avalos & Huang, 2022).
WEIGHTS: Dict[str, float] = {
    "Oil": 0.35,
    "Gold": 0.20,
    "Natural Gas": 0.20,
    "Wheat": 0.15,
    "Copper": 0.10,
}

# Portfolio-level aggregation weights for the four sub-indices.
# PDI (0.40) is highest: price z-scores are the most directly interpretable
# stress signal and the most defensible institutionally.
# VRI (0.30) is second: volatility regime shifts are a strong and
# well-documented stress precursor.
# MSI and CCI (0.15 each) are heuristic / proxy signals with lower weight.
SUBINDEX_WEIGHTS: Dict[str, float] = {
    "price_deviation": 0.40,
    "volatility_regime": 0.30,
    "momentum_stress": 0.15,
    "correlation_contagion": 0.15,
}

DEFAULT_CONFIG: Dict[str, Any] = {
    # Fetch 90 days so we have enough history for the 60-day vol baseline
    # and the 60-day correlation baseline to be computed simultaneously.
    "history_period": "90d",
    # Minimum data points required. Set to 30 (not 20) because with a
    # 60-day long_vol_window, fewer points make the vol_regime_ratio
    # unreliable.
    "min_history_points": 30,
    # Short realized-vol window (10 trading days ~= 2 calendar weeks).
    "short_vol_window": 10,
    # Long historical-vol baseline (60 trading days ~= 3 calendar months).
    "long_vol_window": 60,
    # Momentum return lookback windows in trading days.
    "momentum_short_window": 5,
    "momentum_long_window": 20,
    # CCI recent correlation window.
    "correlation_window": 20,
    # CCI baseline correlation window. Must be <= history_period days.
    "correlation_baseline_window": 60,
    # AWS / AI settings.
    "bedrock_region": os.getenv("AWS_REGION", "us-east-1"),
    "bedrock_model_id": os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
    "max_new_tokens": 512,
    "enable_ai_analysis": True,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VolatilityProfile:
    # Annualized realized vol over the past 10 trading days (%).
    # Formula: std(log(P_t / P_{t-1})) * sqrt(252) * 100
    realized_vol_10d: float
    # Annualized realized vol over the past 60 trading days (%) — the baseline.
    historical_vol_60d: float
    # Ratio of 10d to 60d vol.
    # > 1.0 = elevated; > 1.5 = vol spike (is_vol_spike flag fires).
    # This is the primary VRI input, contributing 70% of the VRI score.
    vol_regime_ratio: float
    # Percentile of the current 10d vol within the rolling 90d distribution.
    # 100th percentile = current vol is the highest seen in the past 90 days.
    # Contributes 30% of the VRI score to catch historically extreme vol levels
    # even when the ratio alone might not be elevated.
    vol_percentile_90d: float
    # Convenience flag: True when vol_regime_ratio > 1.5.
    is_vol_spike: bool


@dataclass
class MomentumProfile:
    # Simple price return over the past 5 trading days (%).
    return_5d: float
    # Simple price return over the past 20 trading days (%).
    return_20d: float
    # 14-period Wilder RSI. Range [0, 100]. >70 = overbought; <30 = oversold.
    rsi_14: float
    # Heuristic overstretch score [0, 100].
    # High when RSI is near either extreme; low near 50.
    # Formula: (|RSI - 50| / 50)^1.5 * 100
    momentum_stress: float


@dataclass
class TermStructureProfile:
    # False when deferred-contract data could not be fetched.
    available: bool
    # Latest closing price of the front-month contract.
    front_price: float
    # Latest closing price of the deferred (further-dated) contract.
    deferred_price: float
    # basis_pct = (front - deferred) / deferred * 100.
    # Positive = backwardation. Negative = contango.
    basis_pct: float
    # "Backwardation" | "Contango" | "Flat" (threshold: |basis_pct| <= 1%)
    regime: str


@dataclass
class CommoditySnapshot:
    name: str
    ticker: str

    # Latest futures price and prior-day close.
    price: float
    previous_close: float
    pct_change_1d: float

    # 30-day rolling price statistics used to compute PDI.
    mean_30d: float
    std_30d: float
    # z-score = (price - mean_30d) / std_30d.
    # Positive = price above recent average; negative = below.
    z_score_30d: float

    # Detailed sub-profiles.
    volatility: VolatilityProfile
    momentum: MomentumProfile
    term_structure: TermStructureProfile

    # Per-commodity sub-index scores [0, 100].
    pdi_score: float   # Price Deviation Index score for this commodity.
    vri_score: float   # Volatility Regime Index score for this commodity.
    msi_score: float   # Momentum Stress Index score for this commodity.
    # Weighted composite of PDI + VRI + MSI for this commodity.
    # CCI is portfolio-level and excluded from per-commodity composite.
    composite_score: float


@dataclass
class CorrelationContagionResult:
    # Average pairwise return correlation across all commodity pairs,
    # computed over the most recent 20 trading days.
    avg_pairwise_corr_20d: float
    # Same average computed over the 60-day baseline window.
    avg_pairwise_corr_60d: float
    # Absolute change: avg_recent - avg_baseline.
    # Positive = correlations are rising (co-movement increasing).
    # We use absolute change rather than a ratio to avoid ratio instability
    # when the baseline correlation is near zero.
    corr_change: float
    # CCI score [0, 100] linearly mapped from corr_change.
    # 0.00 change -> 0, 0.30 change -> 100.
    cci_score: float
    # Individual pair correlations for detailed inspection.
    pairs_recent: Dict[str, float] = field(default_factory=dict)
    pairs_baseline: Dict[str, float] = field(default_factory=dict)


@dataclass
class StressMetrics:
    # Final CMSI score [0, 100].
    cmsi_score: float
    # Qualitative risk tier: Low (<25) | Elevated (25-50) | High (50-75) | Crisis (>=75)
    risk_level: str

    # Portfolio-level sub-index scores [0, 100] after commodity weighting.
    pdi: float  # Weighted-average Price Deviation Index.
    vri: float  # Weighted-average Volatility Regime Index.
    msi: float  # Weighted-average Momentum Stress Index.
    cci: float  # Correlation Contagion Index (single portfolio-level value).

    # The commodity with the highest individual composite_score.
    top_concern: Optional[str]
    # Which sub-index (price_deviation / volatility_regime / momentum_stress)
    # is the primary driver for the top_concern commodity.
    top_concern_driver: str

    # Per-commodity breakdown: weights, scores, and weighted contributions.
    weighted_components: Dict[str, Dict[str, float]]
    # Full CCI result object for detailed inspection.
    correlation_contagion: CorrelationContagionResult


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely cast any value to float, returning `default` on failure, NaN, or Inf.
    Prevents silent propagation of bad numeric values through the pipeline.
    """
    try:
        if value is None:
            return default
        v = float(value)
        return default if (math.isnan(v) or math.isinf(v)) else v
    except Exception:
        return default


def annualized_vol(returns: pd.Series, trading_days: int = 252) -> float:
    """
    Annualized realized volatility from a series of log returns, in percent.

    Formula: std(log_returns) * sqrt(trading_days) * 100

    252 trading days is the standard convention in equity and commodity markets.
    Log returns are preferred over simple returns because they are time-additive
    and better approximated by a normal distribution.
    """
    if len(returns) < 2:
        return 0.0
    return safe_float(returns.std() * math.sqrt(trading_days) * 100.0)


def compute_rsi(closes: pd.Series, window: int = 14) -> float:
    """
    Wilder's Relative Strength Index (RSI) over `window` periods.

    Formula:
        RS  = avg_gain / avg_loss  (both computed over `window` days)
        RSI = 100 - 100 / (1 + RS)

    Returns 50.0 (neutral) when insufficient data is available.
    Conventional interpretation: >70 overbought, <30 oversold.
    """
    if len(closes) < window + 1:
        return 50.0

    delta = closes.diff().dropna()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)

    avg_gain = gains.rolling(window).mean().iloc[-1]
    avg_loss = losses.rolling(window).mean().iloc[-1]

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return safe_float(100.0 - 100.0 / (1.0 + rs))


def rsi_to_stress(rsi: float) -> float:
    """
    Heuristic mapping from RSI to a momentum stress score [0, 100].

    Score table:
        RSI = 50  (balanced)     -> stress = 0
        RSI = 70  (overbought)   -> stress ~= 28
        RSI = 80                 -> stress ~= 47
        RSI = 90                 -> stress ~= 73
        RSI = 30  (oversold)     -> stress ~= 28
        RSI = 20                 -> stress ~= 47
        RSI = 100 or 0 (extreme) -> stress = 100

    The exponent 1.5 gives a convex curve: stress rises slowly near the midpoint
    and accelerates toward the extremes, reflecting that RSI readings above 85
    or below 15 are disproportionately associated with sharp mean-reversions.

    This is explicitly a heuristic. No specific paper is cited for this formula.
    """
    distance_from_50 = abs(rsi - 50.0)
    return min(100.0, (distance_from_50 / 50.0) ** 1.5 * 100.0)


def normalize_z_to_score(z: float, cap: float = 3.0) -> float:
    """
    Map an absolute z-score to [0, 100], capped at `cap` standard deviations.

    A 3-sigma cap means prices more than 3 standard deviations from their
    30-day mean always return PDI = 100, preventing rare outlier events
    from dominating the composite index.
    """
    return min(100.0, (abs(z) / cap) * 100.0)


def normalize_ratio_to_score(
    ratio: float,
    low: float = 1.0,
    high: float = 1.8,
) -> float:
    """
    Linearly map a volatility ratio to [0, 100].

    Calibration:
    - ratio <= 1.0: current vol is at or below its 60d baseline -> score = 0
    - ratio >= 1.8: current vol is 80% above baseline -> score = 100
    - Intermediate values are interpolated linearly.

    The 1.8 upper bound is calibrated to correspond roughly to a 2-sigma
    vol spike in typical commodity markets. This threshold should be
    backtested against your specific universe.
    """
    if ratio <= low:
        return 0.0
    if ratio >= high:
        return 100.0
    return (ratio - low) / (high - low) * 100.0


def normalize_corr_change_to_score(
    corr_change: float,
    low: float = 0.0,
    high: float = 0.30,
) -> float:
    """
    Linearly map an absolute correlation increase to [0, 100].

    Calibration:
    - 0.00 increase: no change in co-movement -> score = 0
    - 0.30 increase: correlations rose by 0.30 -> score = 100

    A +0.30 shift is a large co-movement change and is consistent with levels
    observed during the 2022 commodity stress period (Avalos & Huang, 2022).
    Negative changes (falling correlations) are floored at 0.

    Note: using absolute change rather than a ratio avoids the instability
    that arises when the baseline correlation is near zero (a ratio would
    explode in that case).
    """
    if corr_change <= low:
        return 0.0
    if corr_change >= high:
        return 100.0
    return (corr_change - low) / (high - low) * 100.0


def validate_weights(weights: Dict[str, float], names: List[str]) -> Dict[str, float]:
    """
    Validate and normalize commodity weights to sum to 1.0.
    Falls back to equal weights if all supplied weights are zero or invalid.
    """
    normalized = {n: safe_float(weights.get(n, 0.0)) for n in names}
    total = sum(normalized.values())

    if total <= 0:
        eq = 1.0 / max(len(names), 1)
        logger.warning("Invalid weights; falling back to equal weights.")
        return {n: eq for n in names}

    if abs(total - 1.0) > 1e-6:
        logger.info("Weights do not sum to 1. Normalizing.")
        normalized = {n: w / total for n, w in normalized.items()}

    return normalized


def classify_risk_level(score: float) -> str:
    """
    Map a CMSI score to a qualitative risk tier.
    Thresholds inspired by the BIS multi-tier regime classification
    (Aldasoro, Hördahl & Zhu, 2022). Numeric cutoffs are heuristic.
    """
    if score < 25:
        return "Low"
    if score < 50:
        return "Elevated"
    if score < 75:
        return "High"
    return "Crisis"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_price_history(ticker: str, period: str) -> Optional[pd.Series]:
    """
    Fetch closing prices for a futures contract via Yahoo Finance.
    Returns None on any failure so the caller can handle gracefully.
    """
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty or "Close" not in hist:
            return None
        closes = hist["Close"].dropna()
        return closes if not closes.empty else None
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", ticker, exc)
        return None


def fetch_term_structure(
    front_ticker: str,
    deferred_ticker: str,
) -> TermStructureProfile:
    """
    Compute the futures basis between a front-month and a deferred contract.

    Interpretation (Working, 1949; Gorton & Rouwenhorst, 2006):
    - Backwardation (basis_pct > +1%): nearby demand exceeds supply; inventory
      is low; producers pay a premium for immediate delivery. Often signals
      physical market tightness.
    - Contango (basis_pct < -1%): storage surplus; deferred prices include
      full carry costs (storage + financing). Typical in oversupplied markets.
    - Flat (|basis_pct| <= 1%): market in rough equilibrium.

    IMPORTANT: Used for narrative context only. Does NOT feed into CMSI score.
    """
    try:
        front = fetch_price_history(front_ticker, "5d")
        deferred = fetch_price_history(deferred_ticker, "5d")

        if front is None or deferred is None or front.empty or deferred.empty:
            raise ValueError("Missing term-structure data")

        fp = safe_float(front.iloc[-1])
        dp = safe_float(deferred.iloc[-1])

        if dp == 0:
            raise ValueError("Deferred price is zero")

        basis_pct = (fp - dp) / dp * 100.0

        if basis_pct > 1.0:
            regime = "Backwardation"
        elif basis_pct < -1.0:
            regime = "Contango"
        else:
            regime = "Flat"

        return TermStructureProfile(
            available=True,
            front_price=round(fp, 2),
            deferred_price=round(dp, 2),
            basis_pct=round(basis_pct, 3),
            regime=regime,
        )

    except Exception:
        return TermStructureProfile(
            available=False,
            front_price=0.0,
            deferred_price=0.0,
            basis_pct=0.0,
            regime="N/A",
        )


# ---------------------------------------------------------------------------
# Snapshot computation
# ---------------------------------------------------------------------------

def compute_snapshot(
    name: str,
    ticker: str,
    closes: pd.Series,
    cfg: Dict[str, Any],
) -> Optional[CommoditySnapshot]:
    """
    Compute the full CommoditySnapshot for one commodity.

    Pipeline:
    1. Price statistics  -> 30d mean/std/z-score (PDI input).
    2. Log returns       -> used for all volatility calculations.
    3. Volatility profile -> 10d realized vs. 60d baseline ratio (VRI input).
    4. Momentum profile  -> RSI + short/long returns (MSI input).
    5. Term structure    -> basis and regime (context only, not in score).
    6. Sub-index scores  -> PDI, VRI, MSI, and per-commodity composite.
    """
    if closes is None or len(closes) < cfg["min_history_points"]:
        return None

    # --- 1. Price statistics ---
    latest = safe_float(closes.iloc[-1])
    previous = safe_float(closes.iloc[-2], default=latest)
    mean_30d = safe_float(closes.tail(30).mean(), default=latest)
    std_30d = safe_float(closes.tail(30).std(), default=0.0)
    pct_change_1d = ((latest - previous) / previous * 100.0) if previous else 0.0
    z_score = ((latest - mean_30d) / std_30d) if std_30d > 0 else 0.0

    # --- 2. Log returns ---
    # log(P_t / P_{t-1}) is time-additive and more normally distributed
    # than simple returns, making the vol estimates more stable.
    log_returns = np.log(closes / closes.shift(1)).dropna()

    # --- 3. Volatility profile ---
    sw = cfg["short_vol_window"]   # 10 trading days
    lw = cfg["long_vol_window"]    # 60 trading days
    rv_short = annualized_vol(log_returns.tail(sw))
    rv_long = annualized_vol(log_returns.tail(lw))
    # vol_ratio > 1.0: current short-run vol exceeds long-run baseline.
    vol_ratio = (rv_short / rv_long) if rv_long > 0 else 1.0

    # Rolling percentile: what fraction of 10d vol windows (over 90d) were
    # below the current level? High percentile = currently elevated vs history.
    rolling_rv = log_returns.rolling(sw).std() * math.sqrt(252) * 100.0
    vol_pct = safe_float(
        (rolling_rv < rv_short).mean() * 100.0 if len(rolling_rv.dropna()) > 0 else 50.0
    )

    vol_profile = VolatilityProfile(
        realized_vol_10d=round(rv_short, 2),
        historical_vol_60d=round(rv_long, 2),
        vol_regime_ratio=round(vol_ratio, 3),
        vol_percentile_90d=round(vol_pct, 1),
        is_vol_spike=vol_ratio > 1.5,
    )

    # --- 4. Momentum profile ---
    ms = cfg["momentum_short_window"]   # 5 trading days
    ml = cfg["momentum_long_window"]    # 20 trading days
    ret_short = (
        ((closes.iloc[-1] / closes.iloc[-(ms + 1)]) - 1) * 100.0
        if len(closes) > ms
        else 0.0
    )
    ret_long = (
        ((closes.iloc[-1] / closes.iloc[-(ml + 1)]) - 1) * 100.0
        if len(closes) > ml
        else 0.0
    )
    rsi_val = compute_rsi(closes)
    mom_stress = rsi_to_stress(rsi_val)

    mom_profile = MomentumProfile(
        return_5d=round(safe_float(ret_short), 2),
        return_20d=round(safe_float(ret_long), 2),
        rsi_14=round(rsi_val, 1),
        momentum_stress=round(mom_stress, 2),
    )

    # --- 5. Term structure (context only) ---
    if name in TERM_STRUCTURE_PAIRS:
        ts_profile = fetch_term_structure(*TERM_STRUCTURE_PAIRS[name])
    else:
        ts_profile = TermStructureProfile(
            available=False,
            front_price=latest,
            deferred_price=0.0,
            basis_pct=0.0,
            regime="N/A",
        )

    # --- 6. Sub-index scores ---
    # PDI: absolute z-score capped at 3 sigma mapped to [0, 100].
    pdi = normalize_z_to_score(z_score, cap=3.0)

    # VRI: blended score.
    # 70% from ratio score (relative vol regime vs. own history).
    # 30% from vol percentile (absolute level vs. 90-day distribution).
    # The blend ensures that both a regime shift AND a historically extreme
    # level contribute to the VRI, rather than relying on one signal alone.
    vri_ratio_score = normalize_ratio_to_score(vol_ratio, low=1.0, high=1.8)
    vri = 0.7 * vri_ratio_score + 0.3 * vol_pct

    # MSI: directly from the RSI-to-stress heuristic.
    msi = mom_stress

    # Per-commodity composite: PDI + VRI + MSI only (CCI is portfolio-level).
    # Re-normalise the three sub-index weights so they sum to 1.0 at this level.
    non_cci_total = (
        SUBINDEX_WEIGHTS["price_deviation"]
        + SUBINDEX_WEIGHTS["volatility_regime"]
        + SUBINDEX_WEIGHTS["momentum_stress"]
    )
    composite = (
        (SUBINDEX_WEIGHTS["price_deviation"] / non_cci_total) * pdi
        + (SUBINDEX_WEIGHTS["volatility_regime"] / non_cci_total) * vri
        + (SUBINDEX_WEIGHTS["momentum_stress"] / non_cci_total) * msi
    )

    return CommoditySnapshot(
        name=name,
        ticker=ticker,
        price=round(latest, 2),
        previous_close=round(previous, 2),
        pct_change_1d=round(pct_change_1d, 2),
        mean_30d=round(mean_30d, 2),
        std_30d=round(std_30d, 4),
        z_score_30d=round(z_score, 3),
        volatility=vol_profile,
        momentum=mom_profile,
        term_structure=ts_profile,
        pdi_score=round(pdi, 2),
        vri_score=round(vri, 2),
        msi_score=round(msi, 2),
        composite_score=round(composite, 2),
    )


def fetch_all_snapshots(
    commodities: Dict[str, str],
    cfg: Dict[str, Any],
) -> Tuple[Dict[str, CommoditySnapshot], Dict[str, str]]:
    """
    Fetch and compute snapshots for all commodities in the universe.
    Returns (snapshots_dict, failures_dict). Failures do not halt the pipeline;
    the CMSI is computed on whatever commodities are available.
    """
    snapshots: Dict[str, CommoditySnapshot] = {}
    failures: Dict[str, str] = {}

    for name, ticker in commodities.items():
        closes = fetch_price_history(ticker, cfg["history_period"])

        if closes is None:
            failures[name] = "No usable price history."
            continue

        if len(closes) < cfg["min_history_points"]:
            failures[name] = (
                f"Only {len(closes)} data points "
                f"(need {cfg['min_history_points']})."
            )
            continue

        snap = compute_snapshot(name, ticker, closes, cfg)
        if snap is None:
            failures[name] = "Snapshot computation failed."
        else:
            snapshots[name] = snap

    return snapshots, failures


# ---------------------------------------------------------------------------
# Correlation Contagion Index (CCI)
# ---------------------------------------------------------------------------

def compute_correlation_contagion(
    commodities: Dict[str, str],
    cfg: Dict[str, Any],
) -> CorrelationContagionResult:
    """
    Compute the Correlation Contagion Index (CCI).

    Conceptual basis (Billio et al., 2012):
    Rising pairwise connectedness across assets is a measurable leading indicator
    of systemic stress. This function operationalises that by comparing average
    cross-commodity return correlation over a recent 20-day window to a 60-day
    baseline. A rising CCI means commodities that normally trade independently
    are beginning to move together — a classic signature of common-factor stress.

    Method:
    1. Compute daily percentage returns for all available commodities.
    2. Compute all n*(n-1)/2 pairwise Pearson correlations for both windows.
    3. Average the pairwise correlations within each window.
    4. CCI = f(avg_recent - avg_baseline), linearly mapped to [0, 100].

    Important caveats:
    - This implementation does NOT apply the heteroskedasticity adjustment
      described in Forbes & Rigobon (2002). Their paper shows that during
      high-volatility episodes, raw Pearson correlations are upward biased,
      so correlation spikes can reflect volatility increases rather than true
      structural contagion. The CCI should therefore be treated as a
      co-movement monitoring signal, not a formal contagion test.
    - With 5 commodities there are only 10 pairs; the average is informative
      but noisy. A production system should use a broader commodity universe.
    """
    cw = cfg["correlation_window"]           # 20-day recent window
    bw = cfg["correlation_baseline_window"]  # 60-day baseline window
    period = cfg["history_period"]

    price_data: Dict[str, pd.Series] = {}
    for name, ticker in commodities.items():
        closes = fetch_price_history(ticker, period)
        if closes is not None and len(closes) >= bw:
            price_data[name] = closes

    if len(price_data) < 2:
        # Need at least 2 series to compute pairwise correlations.
        return CorrelationContagionResult(
            avg_pairwise_corr_20d=0.0,
            avg_pairwise_corr_60d=0.0,
            corr_change=0.0,
            cci_score=0.0,
        )

    # Convert to percentage returns (more stationary than price levels).
    df = pd.DataFrame(price_data).pct_change().dropna()
    names = list(df.columns)

    recent_corrs: List[float] = []
    baseline_corrs: List[float] = []
    pair_recent: Dict[str, float] = {}
    pair_baseline: Dict[str, float] = {}

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            pair_key = f"{a}/{b}"
            sa, sb = df[a], df[b]

            if len(sa) >= cw:
                rc = safe_float(sa.tail(cw).corr(sb.tail(cw)))
                recent_corrs.append(rc)
                pair_recent[pair_key] = round(rc, 3)

            if len(sa) >= bw:
                bc = safe_float(sa.tail(bw).corr(sb.tail(bw)))
                baseline_corrs.append(bc)
                pair_baseline[pair_key] = round(bc, 3)

    avg_recent = float(np.mean(recent_corrs)) if recent_corrs else 0.0
    avg_baseline = float(np.mean(baseline_corrs)) if baseline_corrs else 0.0
    # Absolute change is used (not ratio) to avoid instability when
    # baseline correlations are near zero.
    corr_change = avg_recent - avg_baseline

    cci_score = normalize_corr_change_to_score(corr_change, low=0.0, high=0.30)

    return CorrelationContagionResult(
        avg_pairwise_corr_20d=round(avg_recent, 4),
        avg_pairwise_corr_60d=round(avg_baseline, 4),
        corr_change=round(corr_change, 4),
        cci_score=round(cci_score, 2),
        pairs_recent=pair_recent,
        pairs_baseline=pair_baseline,
    )


# ---------------------------------------------------------------------------
# CMSI Aggregation
# ---------------------------------------------------------------------------

def compute_cmsi(
    snapshots: Dict[str, CommoditySnapshot],
    cci_result: CorrelationContagionResult,
    weights: Dict[str, float],
) -> StressMetrics:
    """
    Aggregate per-commodity sub-index scores into the final CMSI.

    Formula:
        PDI_portfolio = sum(w_i * PDI_i)        for all commodities i
        VRI_portfolio = sum(w_i * VRI_i)
        MSI_portfolio = sum(w_i * MSI_i)
        CCI           = portfolio-level single value

        CMSI = 0.40 * PDI_portfolio
             + 0.30 * VRI_portfolio
             + 0.15 * MSI_portfolio
             + 0.15 * CCI

    All inputs and output are bounded in [0, 100].
    """
    if not snapshots:
        empty_cci = CorrelationContagionResult(0.0, 0.0, 0.0, 0.0)
        return StressMetrics(
            cmsi_score=0.0,
            risk_level="Low",
            pdi=0.0,
            vri=0.0,
            msi=0.0,
            cci=0.0,
            top_concern=None,
            top_concern_driver="N/A",
            weighted_components={},
            correlation_contagion=empty_cci,
        )

    valid_w = validate_weights(weights, list(snapshots.keys()))

    # Portfolio-level weighted averages of each sub-index.
    pdi_agg = sum(valid_w[n] * s.pdi_score for n, s in snapshots.items())
    vri_agg = sum(valid_w[n] * s.vri_score for n, s in snapshots.items())
    msi_agg = sum(valid_w[n] * s.msi_score for n, s in snapshots.items())
    cci_val = cci_result.cci_score  # Already a portfolio-level value.

    cmsi = (
        SUBINDEX_WEIGHTS["price_deviation"] * pdi_agg
        + SUBINDEX_WEIGHTS["volatility_regime"] * vri_agg
        + SUBINDEX_WEIGHTS["momentum_stress"] * msi_agg
        + SUBINDEX_WEIGHTS["correlation_contagion"] * cci_val
    )

    # Identify the commodity under most stress and what is driving it.
    top_concern = max(snapshots, key=lambda n: snapshots[n].composite_score)
    top_snap = snapshots[top_concern]
    driver_scores = {
        "price_deviation": top_snap.pdi_score,
        "volatility_regime": top_snap.vri_score,
        "momentum_stress": top_snap.msi_score,
    }
    top_driver = max(driver_scores, key=driver_scores.get)

    weighted_components = {
        name: {
            "weight": round(valid_w[name], 4),
            "composite_score": snap.composite_score,
            "pdi_score": snap.pdi_score,
            "vri_score": snap.vri_score,
            "msi_score": snap.msi_score,
            # Approximate contribution to CMSI (excludes the CCI share).
            "weighted_contribution": round(valid_w[name] * snap.composite_score, 4),
        }
        for name, snap in snapshots.items()
    }

    return StressMetrics(
        cmsi_score=round(min(100.0, cmsi), 2),
        risk_level=classify_risk_level(cmsi),
        pdi=round(pdi_agg, 2),
        vri=round(vri_agg, 2),
        msi=round(msi_agg, 2),
        cci=round(cci_val, 2),
        top_concern=top_concern,
        top_concern_driver=top_driver,
        weighted_components=weighted_components,
        correlation_contagion=cci_result,
    )


# ---------------------------------------------------------------------------
# AWS Bedrock / AI analysis
# ---------------------------------------------------------------------------

def build_bedrock_client(region_name: str):
    """Build an AWS Bedrock runtime client. Returns None on failure."""
    try:
        return boto3.client("bedrock-runtime", region_name=region_name)
    except Exception as exc:
        logger.warning("Could not create Bedrock client: %s", exc)
        return None


def generate_fallback_explanation(
    snapshots: Dict[str, CommoditySnapshot],
    metrics: StressMetrics,
) -> Dict[str, Any]:
    """
    Rule-based fallback explanation used when Bedrock is unavailable
    or the model call fails. Derives a plain-language summary from the
    pre-computed StressMetrics without any external API calls.
    """
    tc = metrics.top_concern or "Unknown"
    snap = snapshots.get(tc)

    driver_detail = ""
    if snap:
        if metrics.top_concern_driver == "volatility_regime":
            driver_detail = (
                f" Realized volatility is {snap.volatility.vol_regime_ratio:.2f}x "
                f"its 60d baseline."
            )
        elif metrics.top_concern_driver == "momentum_stress":
            driver_detail = (
                f" RSI is {snap.momentum.rsi_14:.0f}, indicating an overstretched move."
            )
        elif metrics.top_concern_driver == "price_deviation":
            driver_detail = (
                f" Price is {snap.z_score_30d:+.2f} standard deviations "
                f"from its 30d mean."
            )

    cci_text = (
        f"Average pairwise correlation moved from "
        f"{metrics.correlation_contagion.avg_pairwise_corr_60d:.2f} (baseline) "
        f"to {metrics.correlation_contagion.avg_pairwise_corr_20d:.2f} (recent)."
    )

    return {
        "mode": "rule_based_fallback",
        "cmsi_score": metrics.cmsi_score,
        "risk_level": metrics.risk_level,
        "sub_indices": {
            "PDI": metrics.pdi,
            "VRI": metrics.vri,
            "MSI": metrics.msi,
            "CCI": metrics.cci,
        },
        "top_concern": tc,
        "top_concern_driver": metrics.top_concern_driver,
        "explanation": (
            f"CMSI is {metrics.cmsi_score:.1f}/100 ({metrics.risk_level}). "
            f"Primary stress is in {tc}, led by {metrics.top_concern_driver.replace('_', ' ')}."
            f"{driver_detail} {cci_text}"
        ),
        "hedging_note": (
            "Review directional exposure to the top concern commodity. "
            "If volatility is elevated, options may be preferable to simple delta hedges. "
            "If CCI is high, diversification benefits may be weakening across commodities."
        ),
    }


def analyze_with_nova(
    snapshots: Dict[str, CommoditySnapshot],
    metrics: StressMetrics,
    client=None,
    model_id: str = DEFAULT_CONFIG["bedrock_model_id"],
    max_new_tokens: int = DEFAULT_CONFIG["max_new_tokens"],
) -> Dict[str, Any]:
    """
    Generate an AI-powered narrative via AWS Bedrock (Nova model).

    The prompt instructs the model to:
    1. Explain the CMSI score using the pre-computed sub-indices.
    2. Use the CCI reading to assess idiosyncratic vs. systemic stress.
    3. Add macro/geopolitical context for the top concern commodity.
    4. Treat term structure as narrative colour only (not a scored input).
    5. Recommend hedging instruments (futures, options, swaps, spreads).

    Safeguard: key numeric fields (cmsi_score, risk_level, top_concern,
    top_concern_driver) are always overwritten after parsing with the
    ground-truth values from StressMetrics to prevent hallucination.
    """
    if client is None:
        return generate_fallback_explanation(snapshots, metrics)

    snap_dict = {n: asdict(s) for n, s in snapshots.items()}
    metrics_dict = asdict(metrics)

    prompt = f"""
You are a senior commodity market strategist writing for a risk committee.

IMPORTANT:
All numeric values below were computed by validated code.
Do not recalculate, modify, or contradict any numeric field.

Methodology summary:
- PDI = |z-score| of price vs 30d mean, capped at 3 sigma -> [0, 100]
- VRI = blend of (10d realized vol / 60d baseline vol) and vol percentile -> [0, 100]
- MSI = heuristic RSI-based overstretch proxy -> [0, 100]
- CCI = absolute increase in avg pairwise cross-commodity correlation vs 60d baseline -> [0, 100]
- CMSI = 0.40*PDI + 0.30*VRI + 0.15*MSI + 0.15*CCI

Current readings:
{json.dumps({"snapshots": snap_dict, "stress_metrics": metrics_dict}, indent=2)}

Tasks:
1. Explain which sub-index is most elevated and why it is driving the CMSI.
2. Use the CCI reading to assess whether stress looks idiosyncratic (one commodity)
   or systemic (broad co-movement across the complex).
3. Briefly mention plausible macro or geopolitical drivers for the top concern commodity.
4. Use term structure (contango/backwardation) as contextual colour only.
5. Suggest 2-3 practical hedging ideas with specific instruments
   (futures, options, swaps, cross-commodity spreads).

Return ONLY valid JSON — no markdown, no preamble:
{{
  "mode": "nova",
  "cmsi_score": <copy from stress_metrics.cmsi_score>,
  "risk_level": "<copy from stress_metrics.risk_level>",
  "sub_indices": {{"PDI": <number>, "VRI": <number>, "MSI": <number>, "CCI": <number>}},
  "top_concern": "<copy from stress_metrics.top_concern>",
  "top_concern_driver": "<copy from stress_metrics.top_concern_driver>",
  "explanation": "<3-5 sentence analytical narrative>",
  "hedging_note": "<2-3 specific hedging recommendations with instruments>"
}}
""".strip()

    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(
                {
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"max_new_tokens": max_new_tokens},
                }
            ),
        )

        text = json.loads(response["body"].read())["output"]["message"]["content"][0]["text"]
        # Strip any markdown fences the model may have added despite instructions.
        clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(clean)

        # Overwrite with ground-truth values to prevent hallucination.
        parsed["cmsi_score"] = metrics.cmsi_score
        parsed["risk_level"] = metrics.risk_level
        parsed["top_concern"] = metrics.top_concern
        parsed["top_concern_driver"] = metrics.top_concern_driver
        parsed.setdefault("mode", "nova")

        return parsed

    except Exception as exc:
        logger.warning("Nova analysis failed, using fallback: %s", exc)
        return generate_fallback_explanation(snapshots, metrics)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute the full CMSI pipeline and return a structured result.

    Steps:
    1. Fetch price history and compute per-commodity snapshots.
    2. Compute the Correlation Contagion Index (portfolio-level).
    3. Aggregate sub-indices into the final CMSI score and StressMetrics.
    4. Optionally generate an AI narrative via AWS Bedrock.
    5. Return the complete result dict with methodology metadata.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    snapshots, failures = fetch_all_snapshots(COMMODITIES, cfg)

    if not snapshots:
        return {
            "status": "error",
            "message": "Could not fetch sufficient commodity data.",
            "failed_commodities": failures,
        }

    cci_result = compute_correlation_contagion(
        {n: COMMODITIES[n] for n in snapshots},
        cfg,
    )

    metrics = compute_cmsi(snapshots, cci_result, WEIGHTS)

    client = (
        build_bedrock_client(cfg["bedrock_region"])
        if cfg.get("enable_ai_analysis")
        else None
    )

    analysis = analyze_with_nova(
        snapshots,
        metrics,
        client=client,
        model_id=cfg["bedrock_model_id"],
        max_new_tokens=cfg["max_new_tokens"],
    )

    return {
        "status": "ok",
        "methodology": {
            "name": "Commodity Market Stress Index (CMSI)",
            "description": (
                "Project-specific commodity stress dashboard inspired by BIS-style "
                "composite stress monitoring, commodity spillover research, and "
                "commodity futures theory."
            ),
            "sub_indices": list(SUBINDEX_WEIGHTS.keys()),
            "sub_index_weights": SUBINDEX_WEIGHTS,
            "commodity_weights": WEIGHTS,
            "references": [
                "Aldasoro, I., Hördahl, P. & Zhu, S. "
                "(BIS Quarterly Review, Sep 2022), "
                "'Under pressure: market conditions and stress'",
                "Avalos, F. & Huang, W. "
                "(BIS Quarterly Review, Sep 2022), "
                "'Commodity markets: shocks and spillovers'",
                "Gorton, G. & Rouwenhorst, K.G. "
                "(Financial Analysts Journal, vol. 62(2), 2006), "
                "'Facts and Fantasies About Commodity Futures'",
                "Billio, M., Getmansky, M., Lo, A.W. & Pelizzon, L. "
                "(Journal of Financial Economics, vol. 104(3), 2012), "
                "'Econometric measures of connectedness and systemic risk "
                "in the finance and insurance sectors'",
                "Working, H. "
                "(American Economic Review, 1949), "
                "'The Theory of the Price of Storage'",
            ],
            "notes": [
                "MSI is a heuristic RSI-based overstretch indicator, "
                "not a canonical institutional stress metric.",
                "CCI is a simplified rolling-correlation proxy inspired by "
                "Billio et al. (2012). It does NOT apply the heteroskedasticity "
                "correction of Forbes & Rigobon (2002) and should not be "
                "described as a formal contagion test.",
                "Forbes & Rigobon (2002) was removed from the reference list "
                "because its central finding — that raw correlation spikes during "
                "volatile periods are upward-biased and unreliable as contagion "
                "evidence — is a caveat for the CCI, not a justification of it.",
                "Term structure (contango/backwardation) is contextual and "
                "is NOT included in the CMSI score.",
            ],
        },
        "raw_data": {n: asdict(s) for n, s in snapshots.items()},
        "stress_metrics": asdict(metrics),
        "analysis": analysis,
        "data_quality": {
            "available": list(snapshots.keys()),
            "failed": failures,
            "coverage_ratio": round(len(snapshots) / max(len(COMMODITIES), 1), 2),
        },
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, default=str))
