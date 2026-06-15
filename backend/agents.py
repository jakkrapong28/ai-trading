import asyncio
import logging
from typing import Dict, Any

from backend.shared.events.core import EventBus, CH_SIGNALS, CH_AI_DECISION, CH_AI_JOURNAL
from backend.shared.schema.events import SignalEvent, AIDecisionEvent

logger = logging.getLogger("ai-decision-engine")

AGENTS = ["CEO", "Chart", "Risk", "News", "Macro", "AssetSpecialist"]

# Weighted committee. Each agent now reads its OWN domain signal from the
# SignalEvent.score_breakdown (trend / momentum / volume / news / volatility,
# all 0-100 from the strategy engine) instead of rubber-stamping the signal.
# The final decision is a weighted ensemble, and Risk holds a veto so a
# high-conviction risk rejection can't be out-voted (risk management first).
AGENT_WEIGHTS = {
    "CEO": 0.26,
    "Chart": 0.22,
    "Risk": 0.20,
    "News": 0.12,
    "Macro": 0.12,
    "AssetSpecialist": 0.08,
}
# Weighted support (0-1) the signal direction needs to be approved.
APPROVE_THRESHOLD = 0.50


def _norm100(v: float) -> float:
    """Coerce a score to a 0-100 'bullishness' scale (50 = neutral).

    MultiFactor breakdown is already 0-100; SMC passes raw trend strength
    (-100..100) — map that defensively so agents read one consistent scale.
    """
    if v is None:
        return 50.0
    if -100.0 <= v < 0.0 or v > 100.0:
        v = (v + 100.0) / 2.0
    return max(0.0, min(100.0, v))


def _agree(direction: str, bullishness: float) -> bool:
    """Does a 0-100 bullishness reading agree with a BUY/SELL direction?"""
    return (direction == "BUY" and bullishness >= 55) or (direction == "SELL" and bullishness <= 45)


def _conviction(bullishness: float) -> float:
    """How far from neutral (50) → 0..1 conviction."""
    return min(abs(bullishness - 50.0) / 50.0, 1.0)


def analyze_agent(agent_name: str, signal: SignalEvent) -> dict:
    """Real per-domain analysis. Returns {action, confidence, reasoning}."""
    b = signal.score_breakdown or {}
    direction = signal.signal_type if signal.signal_type in ("BUY", "SELL") else "HOLD"
    prob = float(signal.probability or 0.0)
    price = float(signal.price_at_signal or 0.0)
    atr_pct = (float(signal.atr or 0.0) / price * 100.0) if price else 0.0

    trend = _norm100(b.get("trend", 50.0))
    momentum = _norm100(b.get("momentum", trend))
    news = _norm100(b.get("news", 50.0))
    volume = _norm100(b.get("volume", 50.0))
    volatility = _norm100(b.get("volatility", 50.0))

    if agent_name == "Chart":
        # Technical structure: trend + momentum confluence.
        score = (trend + momentum) / 2.0
        if direction != "HOLD" and _agree(direction, score):
            conf = round(0.5 + 0.5 * _conviction(score), 2)
            return {"action": direction, "confidence": conf,
                    "reasoning": f"โครงสร้างเทคนิคหนุน {direction} (trend {trend:.0f}, momentum {momentum:.0f})"}
        return {"action": "HOLD", "confidence": 0.6,
                "reasoning": f"เทคนิคยังไม่สอดคล้อง (trend {trend:.0f}, momentum {momentum:.0f})"}

    if agent_name == "Risk":
        # Risk-of-ruin guard: low probability or extreme volatility = veto.
        if prob < 0.55:
            return {"action": "REJECT", "confidence": 0.9,
                    "reasoning": f"ความน่าจะเป็นต่ำ {prob:.0%} — ไม่คุ้มเสี่ยง"}
        if atr_pct > 4.0:
            return {"action": "REJECT", "confidence": 0.82,
                    "reasoning": f"ผันผวนสูงเกิน (ATR {atr_pct:.1f}% ของราคา) — เสี่ยงโดน stop"}
        conf = round(min(0.6 + (prob - 0.55) * 0.8, 0.92), 2)
        return {"action": direction if direction != "HOLD" else "HOLD", "confidence": conf,
                "reasoning": f"R:R รับได้ (prob {prob:.0%}, ATR {atr_pct:.1f}%)"}

    if agent_name == "News":
        # Uses the REAL final_news_score (0-100) the news engine produced.
        if direction != "HOLD" and _agree(direction, news):
            return {"action": direction, "confidence": round(0.5 + 0.4 * _conviction(news), 2),
                    "reasoning": f"ปัจจัยข่าวหนุน {direction} (news {news:.0f}/100)"}
        if direction != "HOLD" and _agree("SELL" if direction == "BUY" else "BUY", news):
            return {"action": "HOLD", "confidence": 0.7,
                    "reasoning": f"ข่าวสวนทางสัญญาณ (news {news:.0f}/100) — ชะลอ"}
        return {"action": "HOLD", "confidence": 0.55,
                "reasoning": f"ข่าวเป็นกลาง (news {news:.0f}/100)"}

    if agent_name == "Macro":
        # Macro/regime trend as the slow-moving bias.
        if direction != "HOLD" and _agree(direction, trend):
            return {"action": direction, "confidence": round(0.5 + 0.4 * _conviction(trend), 2),
                    "reasoning": f"เทรนด์มหภาคสอดคล้อง {direction} (bias {trend:.0f})"}
        return {"action": "HOLD", "confidence": 0.6,
                "reasoning": f"มหภาคยังไม่ชัด (bias {trend:.0f})"}

    if agent_name == "AssetSpecialist":
        # Volume / participation confirmation for this asset.
        if volume >= 60 and direction != "HOLD":
            return {"action": direction, "confidence": round(0.55 + 0.4 * _conviction(volume), 2),
                    "reasoning": f"วอลุ่มยืนยันแรงซื้อขาย (vol {volume:.0f})"}
        if volume <= 40:
            return {"action": "HOLD", "confidence": 0.65,
                    "reasoning": f"วอลุ่มเบาบาง (vol {volume:.0f}) — ขาดแรงยืนยัน"}
        return {"action": direction if direction != "HOLD" else "HOLD", "confidence": 0.55,
                "reasoning": f"วอลุ่มปกติ (vol {volume:.0f})"}

    if agent_name == "CEO":
        # CEO weighs the overall composite + probability before approving.
        composite = (trend + momentum + news + volume) / 4.0
        if direction != "HOLD" and _agree(direction, composite) and prob >= 0.6:
            return {"action": direction, "confidence": round(0.6 + 0.35 * _conviction(composite), 2),
                    "reasoning": f"ประธานอนุมัติ: ภาพรวม {composite:.0f}/100, มั่นใจ {prob:.0%}"}
        return {"action": "HOLD", "confidence": 0.7,
                "reasoning": f"ประธานชะลอ: ภาพรวม {composite:.0f}/100, มั่นใจ {prob:.0%} ยังไม่พอ"}

    return {"action": "HOLD", "confidence": 0.5, "reasoning": ""}


async def call_claude_vote(agent_name: str, signal: SignalEvent) -> dict:
    import os
    import json
    import re
    import httpx
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    b = signal.score_breakdown or {}
    prompt = (
        f"You are the {agent_name} agent on an AI trading committee.\n"
        f"Signal: {signal.ticker} {signal.signal_type} @ {signal.price_at_signal:.2f}, "
        f"probability {signal.probability:.2f}.\n"
        f"Domain scores (0-100): trend={b.get('trend')}, momentum={b.get('momentum')}, "
        f"volume={b.get('volume')}, news={b.get('news')}, volatility={b.get('volatility')}.\n"
        f"From YOUR domain only, vote BUY, SELL, HOLD, or REJECT with a confidence "
        f"(0.0-1.0) and a one-line reason. JSON only: "
        f'{{"action":"BUY/SELL/HOLD/REJECT","confidence":0.85,"reasoning":"..."}}'
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 150,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=5.0
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data["content"][0]["text"]
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                res = json.loads(m.group(0))
                if "action" in res and "confidence" in res and "reasoning" in res:
                    return res
        raise RuntimeError(f"Claude API failed: status {resp.status_code}")


async def deterministic_agent_vote(agent_name: str, signal: SignalEvent) -> dict:
    """Domain analysis, with optional Claude API enrichment."""
    from backend.config import FEATURE_FLAGS
    if FEATURE_FLAGS.get("claude_fallback", False):
        try:
            return await call_claude_vote(agent_name, signal)
        except Exception as e:
            logger.warning(f"Claude vote failed for {agent_name}, using rules: {e}")
    return analyze_agent(agent_name, signal)


def tally_votes(results: Dict[str, dict], direction: str) -> dict:
    """Weighted ensemble with a Risk veto. Returns final action + confidence."""
    support = 0.0   # weighted conviction backing the signal direction
    oppose = 0.0    # weighted conviction against (REJECT or opposite)
    risk_veto = False

    for agent, r in results.items():
        w = AGENT_WEIGHTS.get(agent, 0.0)
        act, conf = r["action"], float(r.get("confidence", 0.5))
        if agent == "Risk" and act == "REJECT" and conf >= 0.8:
            risk_veto = True
        if act == direction and direction in ("BUY", "SELL"):
            support += w * conf
        elif act == "REJECT" or (act in ("BUY", "SELL") and act != direction):
            oppose += w * conf

    if risk_veto:
        return {"action": "REJECT", "confidence": round(oppose, 2), "support": round(support, 2)}
    if direction in ("BUY", "SELL") and support >= APPROVE_THRESHOLD and support > oppose:
        return {"action": direction, "confidence": round(support, 2), "support": round(support, 2)}
    return {"action": "REJECT", "confidence": round(max(oppose, 1 - support), 2), "support": round(support, 2)}


class AIDecisionEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def process_signals(self):
        logger.info("AI Decision Engine listening to CH_SIGNALS...")
        async for msg in self.event_bus.subscribe_group(CH_SIGNALS, "ai_decision_group", "ai_decision_worker_1"):
            try:
                signal = SignalEvent(**msg)
                direction = signal.signal_type
                logger.info(f"[AI Debate] Voting on {signal.ticker} ({direction})")

                votes = await asyncio.gather(*[deterministic_agent_vote(a, signal) for a in AGENTS])
                results = dict(zip(AGENTS, votes))
                votes_record = {a: r["action"] for a, r in results.items()}

                outcome = tally_votes(results, direction)
                final_action = outcome["action"]

                # Human-readable committee summary (each agent's actual reasoning).
                lines = " | ".join(f"{a}:{r['action']}({r['confidence']:.2f})" for a, r in results.items())
                reasoning = (
                    f"มติถ่วงน้ำหนักสภา AI: {final_action} "
                    f"(support {outcome['support']:.0%} / เกณฑ์ {APPROVE_THRESHOLD:.0%}) — {lines}"
                )

                decision = AIDecisionEvent(
                    ticker=signal.ticker,
                    action=final_action,
                    confidence=outcome["confidence"],
                    votes=votes_record,
                    reasoning=reasoning,
                )
                await self.event_bus.publish(CH_AI_DECISION, decision.model_dump())
                logger.info(f"[AI Debate] {signal.ticker} → {final_action} (support {outcome['support']:.2f})")

                await self.event_bus.publish(CH_AI_JOURNAL, {
                    "ticker": signal.ticker,
                    "decision": "AI_VOTE_COMPLETED",
                    "signal_action": final_action,
                    "confidence_score": outcome["confidence"],
                    "reasons": [reasoning],
                })
            except Exception as e:
                logger.error(f"[AI Debate] Error processing signal: {e}")


def start_ai_decision_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    engine = AIDecisionEngine(event_bus)
    registry.register(engine.process_signals(), name="ai_decision_poller")
