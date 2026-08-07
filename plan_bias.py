"""Transparent measured tonnage bias lens for Plan (does not change the engine).

Measured on 44 routes (HANDOVER / J52 / J55):
  no factor  → +5.5% (current DEFAULT_AVAILABILITY=1.0)
  ×0.85      → −10.3% (worse — double-counts downtime already in effective cycle)

This module ONLY labels and optionally *displays* an adjusted figure.
It never mutates /api/simulate tonnes and never re-adds availability.
"""
from __future__ import annotations

# Over-predict vs delivered tickets when availability factor = 1.0
MEASURED_BIAS = 0.055
# Divide raw achievable by this to show a delivery-adjusted lens
ADJUST_DIVISOR = 1.0 + MEASURED_BIAS  # 1.055


def ticket_calibrated_t(achievable_t):
    """Companion calibrated tonnes (raw / 1.055). Never replaces engine primary."""
    try:
        raw = float(achievable_t)
    except (TypeError, ValueError):
        return None
    return round(raw / ADJUST_DIVISOR, 0)


def bias_lens(achievable_t, enabled=True):
    """Return raw + delivery-adjusted tonnes.

    enabled=True (default for Plan UI): show ticket-calibrated companion.
    Engine /api/simulate primary achievable stays raw (availability=1.0).
    """
    try:
        raw = float(achievable_t) if achievable_t is not None else None
    except (TypeError, ValueError):
        raw = None
    out = {
        "measured_bias": MEASURED_BIAS,
        "adjust_divisor": ADJUST_DIVISOR,
        "enabled": bool(enabled),
        "raw_achievable_t": round(raw, 0) if raw is not None else None,
        "adjusted_achievable_t": None,
        "engine_unchanged": True,
        "availability_factor": 1.0,
        "note": (
            "Ticket-calibrated companion = raw ÷ 1.055 (measured +5.5% residual). "
            "Primary /api/simulate achievable stays raw; availability stays 1.0 "
            "(×0.85 would move bias to −10.3% — forbidden)."
        ),
        "basis": {
            "congestion_clips_tonnes": False,
            "simulate_unchanged": True,
            "trains_away_bias": False,
            "availability_scales_tonnage": False,
        },
    }
    if raw is None:
        return out
    cal = ticket_calibrated_t(raw)
    if enabled:
        out["adjusted_achievable_t"] = cal
    else:
        out["adjusted_achievable_t"] = round(raw, 0)
    out["ticket_calibrated_achievable_t"] = cal
    return out
