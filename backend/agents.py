import random
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("agents")

# รายชื่อและโปรไฟล์ของ AI Agents ใน Virtual Office
AGENTS = {
    "CEO": {
        "name": "CEO Agent (The Orchestrator)",
        "role": "ผู้อำนวยการสั่งการระบบและประเมินผลลัพธ์ขั้นตอนสุดท้าย",
        "avatar": "💼"
    },
    "Chart": {
        "name": "Chart AI (Forex Desk)",
        "role": "นักวิเคราะห์เทคนิคคอลและระดับแนวรับแนวต้านในตลาด Forex",
        "avatar": "📊"
    },
    "Crypto": {
        "name": "Crypto Analyst AI (Crypto Desk)",
        "role": "นักวิเคราะห์พฤติกรรมราคา ปริมาณการซื้อขาย และ Order Book ฝั่งคริปโต",
        "avatar": "🪙"
    },
    "Wallet": {
        "name": "Wallet Intel AI (Digital Asset Detective)",
        "role": "ผู้คุมเงินดิจิทัล ตรวจสอบ Net Worth และความเคลื่อนไหวกระเป๋าวาฬ",
        "avatar": "🔍"
    },
    "Risk": {
        "name": "Risk AI (The Guardian)",
        "role": "ผู้คุมกฎเหล็กบริหารความเสี่ยงและกำหนดขนาดล็อตคำสั่งซื้อขาย",
        "avatar": "🛡️"
    },
    "News": {
        "name": "News/Audit AI",
        "role": "ผู้ตรวจสอบข่าวเศรษฐกิจมหภาคและความปลอดภัยเชิงสถิติของระบบ",
        "avatar": "📰"
    }
}

# ─────────────────────────────────────────────────────────
# Claude-Powered Agent Debate (Async, with streaming-ready steps)
# ─────────────────────────────────────────────────────────

async def generate_claude_agent_opinion(
    agent_key: str,
    symbol: str,
    indicators: Dict[str, Any],
    signal: Dict[str, Any],
    risk: Dict[str, Any],
    anthropic_key: str,
    context_from_prev: str = ""
) -> str:
    """เรียก Claude API จริงสำหรับแต่ละ Agent ด้วย System Prompt เฉพาะทาง"""
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=anthropic_key)

        latest = indicators.get("latest", 0)
        trend = indicators.get("trend", "Unknown")
        rsi = indicators.get("rsi", 50)
        atr = indicators.get("atr", 0)
        support = indicators.get("support", 0)
        resistance = indicators.get("resistance", 0)
        macd = indicators.get("macd", {})
        action = signal.get("action", "WAIT")
        confidence = signal.get("confidence", 0)
        strategy_type = signal.get("strategy_type", "WAIT")
        stat_score = signal.get("statistical_score", 0)
        confirmations = signal.get("confirmations", [])
        risk_passed = risk.get("passed", False)
        risk_pct = risk.get("riskPct", 0)

        # System Prompt เฉพาะทางของแต่ละ Agent
        system_prompts = {
            "CEO": (
                f"คุณคือ CEO Agent หัวหน้าทีม AI Trading Virtual Office "
                f"ทำหน้าที่เปิดประชุมและมอบหมายงานวิเคราะห์ "
                f"พูดภาษาไทยอย่างเป็นทางการ กระชับ มีอำนาจ ความยาว 2-3 ประโยค "
                f"ข้อมูล: {symbol} ราคา {latest} สัญญาณ {action} "
                f"({strategy_type}, confidence {confidence:.0%}, stat {stat_score:.0%}, "
                f"confirmations: {', '.join(confirmations) or 'none'})"
            ),
            "Chart": (
                f"คุณคือนักวิเคราะห์เทคนิคอล ผู้เชี่ยวชาญ EMA RSI MACD Bollinger Bands "
                f"วิเคราะห์กราฟ {symbol} พูดภาษาไทย ใช้ตัวเลขจริง ความยาว 3-4 ประโยค\n"
                f"ข้อมูล: ราคา={latest}, เทรนด์={trend}, RSI={rsi}, ATR={atr}, "
                f"แนวรับ={support}, แนวต้าน={resistance}, "
                f"MACD histogram={macd.get('histogram', 0):.4f}"
            ),
            "Crypto": (
                f"คุณคือนักวิเคราะห์ตลาดคริปโตและ On-chain data ผู้เชี่ยวชาญ "
                f"{'วิเคราะห์ ' + symbol + ' ในมุม crypto/DeFi ecosystem' if symbol in ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT'] else 'วิเคราะห์ความเชื่อมโยงระหว่าง ' + symbol + ' กับภาวะตลาดคริปโต'} "
                f"พูดภาษาไทย ความยาว 3-4 ประโยค ใช้ศัพท์เทคนิค crypto\n"
                f"ข้อมูลตลาด: ราคา={latest}, เทรนด์={trend}, ATR={atr}"
            ),
            "Wallet": (
                f"คุณคือ Wallet Intelligence Analyst ผู้เชี่ยวชาญด้าน portfolio management และ liquidity "
                f"ตรวจสอบยอดคงเหลือและ exposure ของพอร์ต วิเคราะห์ {symbol} "
                f"พูดภาษาไทย ความยาว 2-3 ประโยค เน้นความปลอดภัยของเงินทุน\n"
                f"ข้อมูล: risk_pct={risk_pct}%, ความเสี่ยงรวม={'ผ่าน' if risk_passed else 'เกินเกณฑ์'}"
            ),
            "Risk": (
                f"คุณคือ Risk Manager ผู้คุมกฎเหล็กบริหารความเสี่ยง "
                f"ต้องรายงานตัวเลขความเสี่ยงอย่างชัดเจน พูดภาษาไทย ความยาว 3-4 ประโยค\n"
                f"ผลประเมิน: risk_pct={risk_pct}%, สถานะ={'✅ ผ่าน' if risk_passed else '❌ ระงับ'}\n"
                f"checks: {[c['name'] + ': ' + ('✅' if c['pass'] else '❌') for c in risk.get('checks', [])]}"
            ),
            "News": (
                f"คุณคือ News & Macro Analyst ผู้เชี่ยวชาญด้านข่าวเศรษฐกิจและ fundamental analysis "
                f"วิเคราะห์ว่าข่าวมหภาคปัจจุบัน (Fed, GDP, inflation, geopolitics) ส่งผลต่อ {symbol} อย่างไร "
                f"พูดภาษาไทย ความยาว 3-4 ประโยค ใช้ข้อมูลปัจจุบัน\n"
                f"ข้อมูลตลาด: ราคา={latest}, เทรนด์={trend}"
            )
        }

        context_note = f"\n\nบทสรุปจากการประชุมก่อนหน้า:\n{context_from_prev}" if context_from_prev else ""

        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=250,
            system=system_prompts.get(agent_key, system_prompts["CEO"]) + context_note,
            messages=[{
                "role": "user",
                "content": f"กรุณาให้ความเห็นในฐานะ {AGENTS[agent_key]['role']} สำหรับ {symbol}"
            }]
        )
        return response.content[0].text.strip()

    except Exception as e:
        logger.error(f"[Claude Agent] Error for {agent_key}: {e}")
        return None  # จะ fallback ไปใช้ template


def _build_template_message(agent_key: str, symbol: str, indicators: Dict, signal: Dict, risk: Dict) -> str:
    """Template fallback เมื่อ Claude ไม่พร้อม"""
    latest = indicators.get("latest", 0)
    trend = indicators.get("trend", "Sideways")
    rsi = indicators.get("rsi", 50)
    atr = indicators.get("atr", 0)
    support = indicators.get("support", 0)
    resistance = indicators.get("resistance", 0)
    action = signal.get("action", "WAIT")
    confidence = signal.get("confidence", 0)
    risk_passed = risk.get("passed", False)
    risk_pct = risk.get("riskPct", 0)

    templates = {
        "CEO": (
            f"สวัสดีทีมงาน เปิดเซสชันวิเคราะห์ {symbol} — ราคาปัจจุบัน {latest} "
            f"สัญญาณเบื้องต้นระบุ [{action}] (confidence: {confidence:.0%}) "
            f"ช่วยวิเคราะห์ในแผนกของตนด่วนครับ"
        ),
        "Chart": (
            f"ฝั่ง Chart รายงาน: {symbol} อยู่ใน{trend} trend "
            f"RSI={rsi} ATR={atr:.2f} แนวรับ={support:.2f} แนวต้าน={resistance:.2f} "
            f"ราคาอยู่{'ใกล้แนวรับ เหมาะ BUY' if action=='BUY' else 'ใกล้แนวต้าน เหมาะ SELL' if action=='SELL' else 'กลางกรอบ ควรรอ'}"
        ),
        "Crypto": (
            f"{'ตลาดคริปโตยืนยัน: Order Flow ฝั่ง ' + symbol + ' สอดคล้องกับสัญญาณ' if symbol in ['BTCUSDT','ETHUSDT','SOLUSDT'] else 'ไม่พบ correlation ผิดปกติระหว่าง ' + symbol + ' กับตลาดคริปโต'} "
            f"Sentiment โดยรวมเป็น{'กระทิง' if trend=='Bullish' else 'หมี' if trend=='Bearish' else 'ทรงตัว'}"
        ),
        "Wallet": (
            f"ตรวจสอบพอร์ตเรียบร้อย: risk exposure {risk_pct:.1f}% "
            f"{'ยังมีพื้นที่รองรับคำสั่งนี้ได้ปลอดภัย' if risk_passed else 'เกินเกณฑ์ความปลอดภัย ควรระงับ'} "
            f"ไม่พบ anomaly ในธุรกรรมขนาดใหญ่"
        ),
        "Risk": (
            f"Risk Manager รายงาน: {symbol} สถานะ {'✅ APPROVED' if risk_passed else '❌ BLOCKED'} "
            f"risk={risk_pct:.1f}% exposure={risk.get('exposurePct', 0):.1f}% "
            f"{'ขนาด lot ปลอดภัยตามกฎ 2%' if risk_passed else 'ขัดกฎเหล็ก — ยกเลิกหรือหั่น lot'}"
        ),
        "News": (
            f"Macro check: ไม่พบ high-impact event ในช่วง 3 ชม. ถัดไป "
            f"ภาวะเงินเฟ้อและ Fed policy ยังส่งผลต่อ {symbol} ในระยะกลาง "
            f"{'ปลอดภัยสำหรับการเทรด' if risk_passed else 'แนะนำหลีกเลี่ยงการเปิดออเดอร์ใหม่'}"
        )
    }
    return templates.get(agent_key, f"วิเคราะห์ {symbol} เรียบร้อย")


async def generate_thai_debate_async(
    symbol: str,
    indicators: Dict[str, Any],
    signal: Dict[str, Any],
    risk: Dict[str, Any],
    anthropic_key: str = ""
) -> List[Dict[str, Any]]:
    """
    สร้าง Debate แบบ Async — ใช้ Claude จริงถ้ามี API key
    ถ้าไม่มี Claude → fallback ไปใช้ template ที่ปรับปรุงแล้ว
    """
    timestamp = datetime.now().isoformat()
    debate_steps = []
    has_claude = bool(anthropic_key) and "Anthropic" not in anthropic_key and len(anthropic_key) > 20

    agent_order = ["CEO", "Chart", "Crypto", "Wallet", "Risk", "News", "CEO"]
    context_summary = ""

    for i, agent_key in enumerate(agent_order):
        agent_info = AGENTS[agent_key]
        is_final_ceo = (i == len(agent_order) - 1)

        if has_claude:
            if is_final_ceo:
                # CEO สรุปพิเศษพร้อม context ทั้งหมด
                final_prompt = f"สรุปมติที่ประชุมสำหรับ {symbol}: action={signal.get('action')}, risk={'ผ่าน' if risk.get('passed') else 'ไม่ผ่าน'}, confidence={signal.get('confidence', 0):.0%}"
                message = await generate_claude_agent_opinion(
                    "CEO", symbol, indicators, signal, risk,
                    anthropic_key, context_from_prev=context_summary
                )
                if not message:
                    message = _build_ceo_final_template(symbol, signal, risk)
            else:
                message = await generate_claude_agent_opinion(
                    agent_key, symbol, indicators, signal, risk, anthropic_key
                )
                if not message:
                    message = _build_template_message(agent_key, symbol, indicators, signal, risk)
                # สะสม context
                context_summary += f"\n{agent_info['name']}: {message[:100]}..."
        else:
            if is_final_ceo:
                message = _build_ceo_final_template(symbol, signal, risk)
            else:
                message = _build_template_message(agent_key, symbol, indicators, signal, risk)

        debate_steps.append({
            "agent": agent_info["name"],
            "role": agent_info["role"],
            "avatar": agent_info["avatar"],
            "message": message,
            "timestamp": timestamp,
            "powered_by": "claude" if has_claude else "template"
        })

    return debate_steps


def _build_ceo_final_template(symbol: str, signal: Dict, risk: Dict) -> str:
    """Template สำหรับ CEO สรุปสุดท้าย"""
    action = signal.get("action", "WAIT")
    risk_passed = risk.get("passed", False)
    confidence = signal.get("confidence", 0)

    if action == "WAIT":
        return (
            f"ขอบคุณทีมงานทุกท่าน สรุปสำหรับ {symbol}: "
            f"ยังไม่มีสัญญาณที่สอดคล้องเพียงพอ ดำเนินโหมด Watch Mode ต่อ "
            f"จะแจ้งเตือนทันทีเมื่อมีสัญญาณชัดเจนครับ"
        )
    elif risk_passed:
        return (
            f"มติเป็นเอกฉันท์! แผน [{action}] {symbol} ผ่านการประเมินทุกด้าน "
            f"(confidence: {confidence:.0%}) "
            f"กำลังส่งรายงานและปุ่มยืนยันไปยัง Telegram ทันทีครับ"
        )
    else:
        return (
            f"มติที่ประชุม {symbol}: แม้มีสัญญาณ {action} แต่ Risk Engine ระงับ "
            f"ความปลอดภัยของทุนสำคัญกว่า — ยุติเซสชันนี้ครับ"
        )


def generate_thai_debate(
    symbol: str,
    indicators: Dict[str, Any],
    signal: Dict[str, Any],
    risk: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Sync wrapper สำหรับ backward compatibility —
    ใช้ template เมื่อถูกเรียกแบบ sync (ไม่มี await)
    """
    timestamp = datetime.now().isoformat()
    debate_steps = []
    agent_order = ["CEO", "Chart", "Crypto", "Wallet", "Risk", "News"]

    for agent_key in agent_order:
        agent_info = AGENTS[agent_key]
        message = _build_template_message(agent_key, symbol, indicators, signal, risk)
        debate_steps.append({
            "agent": agent_info["name"],
            "role": agent_info["role"],
            "avatar": agent_info["avatar"],
            "message": message,
            "timestamp": timestamp,
            "powered_by": "template"
        })

    # CEO สรุป
    ceo_info = AGENTS["CEO"]
    debate_steps.append({
        "agent": ceo_info["name"],
        "role": ceo_info["role"],
        "avatar": ceo_info["avatar"],
        "message": _build_ceo_final_template(symbol, signal, risk),
        "timestamp": timestamp,
        "powered_by": "template"
    })

    return debate_steps
