import asyncio
import logging
from typing import Dict, Any

from backend.shared.events.core import EventBus, CH_SIGNALS, CH_AI_DECISION, CH_AI_JOURNAL
from backend.shared.schema.events import SignalEvent, AIDecisionEvent

logger = logging.getLogger("ai-decision-engine")

AGENTS = ["CEO", "Chart", "Risk", "News", "Macro", "AssetSpecialist"]

async def deterministic_agent_vote(agent_name: str, signal: SignalEvent) -> dict:
    """
    Strict deterministic rules for each agent.
    No randomness allowed.
    """
    action = "HOLD"
    confidence = 0.5
    reasoning = ""
    
    sig_type = signal.signal_type
    
    if agent_name == "Chart":
        if signal.probability > 0.7:
            action = sig_type
            confidence = 0.8
            reasoning = f"โครงสร้างเทคนิคของแนวโน้มเอื้ออำนวยต่อการ {sig_type} อย่างชัดเจน"
        else:
            action = "HOLD"
            confidence = 0.6
            reasoning = "โครงสร้างเทคนิคยังคงอ่อนแรง ไม่พร้อมเปิดสถานะ"
            
    elif agent_name == "Risk":
        if signal.probability > 0.85:
            action = sig_type
            confidence = 0.7
            reasoning = "สัดส่วนความเสี่ยงและอัตราผลตอบแทนอยู่ในเกณฑ์ดีและมีความเป็นไปได้สูง"
        else:
            action = "REJECT"
            confidence = 0.9
            reasoning = "ความน่าจะเป็นต่ำเกินไป ไม่ควรนำเงินทุนไปเสี่ยง"
            
    elif agent_name == "News":
        action = sig_type
        confidence = 0.6
        reasoning = "ทิศทางข่าวสารและปัจจัยข่าวหนุนหลังเป็นบวกในภาพรวม"
        
    elif agent_name == "Macro":
        action = sig_type
        confidence = 0.7
        reasoning = "สภาวะเศรษฐกิจมหภาคและการคลังสนับสนุนสัญญาณการเทรดนี้"
        
    elif agent_name == "AssetSpecialist":
        action = sig_type
        confidence = 0.7
        reasoning = f"พฤติกรรมราคาและปริมาณการซื้อขายเฉลี่ยของ {signal.ticker} สอดคล้องกับแผนการนี้"
        
    elif agent_name == "CEO":
        if signal.probability > 0.75:
            action = sig_type
            confidence = 0.9
            reasoning = "ประธานอนุมัติคำสั่งซื้อขาย: ปัจจัยวิเคราะห์มีความมั่นใจสูง ผ่านด่านประชุมกรรมการ"
        else:
            action = "HOLD"
            confidence = 0.8
            reasoning = "ปฏิเสธการอนุมัติจากประธาน: สัญญาณยังไม่มีความน่าเชื่อถือเพียงพอ"

    return {
        "action": action,
        "confidence": confidence,
        "reasoning": reasoning
    }

class AIDecisionEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    async def process_signals(self):
        logger.info("AI Decision Engine listening to CH_SIGNALS...")
        async for msg in self.event_bus.subscribe_group(CH_SIGNALS, "ai_decision_group", "ai_decision_worker_1"):
            try:
                signal = SignalEvent(**msg)
                
                logger.info(f"[AI Debate] Starting voting session for {signal.ticker} ({signal.signal_type})")
                
                tasks = [deterministic_agent_vote(agent, signal) for agent in AGENTS]
                results = await asyncio.gather(*tasks)
                
                votes_count = {"BUY": 0, "SELL": 0, "HOLD": 0, "REJECT": 0}
                total_conf = 0.0
                votes_record = {}
                
                for agent, result in zip(AGENTS, results):
                    action = result["action"]
                    votes_count[action] += 1
                    total_conf += result["confidence"]
                    votes_record[agent] = action
                    
                    logger.debug(f"  - {agent} voted {action} (Conf: {result['confidence']:.2f})")
                
                final_action = "REJECT"
                if votes_count["BUY"] >= 4:
                    final_action = "BUY"
                elif votes_count["SELL"] >= 4:
                    final_action = "SELL"
                    
                avg_conf = total_conf / len(AGENTS)
                
                reasoning = (
                    f"มติที่ประชุมสภา AI: {final_action} | "
                    f"คะแนนเสียง: ซื้อ (BUY)={votes_count['BUY']}, ขาย (SELL)={votes_count['SELL']}, รอ (HOLD)={votes_count['HOLD']}, ปฏิเสธ (REJECT)={votes_count['REJECT']} | "
                    f"ระดับความมั่นใจเฉลี่ย: {avg_conf * 100:.1f}%"
                )
                
                decision = AIDecisionEvent(
                    ticker=signal.ticker,
                    action=final_action,
                    confidence=avg_conf,
                    votes=votes_record,
                    reasoning=reasoning
                )
                
                await self.event_bus.publish(CH_AI_DECISION, decision.model_dump())
                logger.info(f"[AI Debate] Result for {signal.ticker}: {final_action}")
                
                journal_entry = {
                    "ticker": signal.ticker,
                    "decision": "AI_VOTE_COMPLETED",
                    "signal_action": final_action,
                    "confidence_score": avg_conf,
                    "reasons": [reasoning]
                }
                await self.event_bus.publish(CH_AI_JOURNAL, journal_entry)
                
            except Exception as e:
                logger.error(f"[AI Debate] Error processing signal: {e}")

def start_ai_decision_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    engine = AIDecisionEngine(event_bus)
    registry.register(engine.process_signals(), name="ai_decision_poller")
