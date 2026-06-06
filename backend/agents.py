import random
from typing import List, Dict, Any
from datetime import datetime

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

def generate_thai_debate(
    symbol: str, 
    indicators: Dict[str, Any], 
    signal: Dict[str, Any], 
    risk: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    จำลองการประชุมสัมมนาและถกเถียง (Debate) ของทีม AI ใน Virtual Office
    โดยอ้างอิงจากราคาปัจจุบัน สัญญาณ และผลลัพธ์ความเสี่ยง
    """
    latest = indicators["latest"]
    trend = indicators["trend"]
    rsi = indicators["rsi"]
    atr = indicators["atr"]
    support = indicators["support"]
    resistance = indicators["resistance"]
    action = signal["action"]
    
    debate_steps = []
    timestamp = datetime.now().isoformat()
    
    # ขั้นที่ 1: CEO เริ่มต้นการประชุม
    debate_steps.append({
        "agent": AGENTS["CEO"]["name"],
        "role": AGENTS["CEO"]["role"],
        "avatar": AGENTS["CEO"]["avatar"],
        "message": f"สวัสดีทีมงานทุกคน ยินดีต้อนรับสู่เซสชันการวิเคราะห์ด่วนสำหรับ {symbol} ราคาปัจจุบันอยู่ที่ {latest} ระบบ Rule Engine ของเราส่งสัญญาณเบื้องต้นเป็น [{action}] ช่วยกันวิเคราะห์ในแผนกตนเองด่วนครับ!",
        "timestamp": timestamp
    })
    
    # ขั้นที่ 2: Chart AI แสดงความคิดเห็น
    if symbol in ["XAUUSD", "EURUSD"]:
        chart_msg = f"ฝั่ง Forex ขอรายงานครับ จากกราฟเทคนิค {symbol} กำลังอยู่ในช่วงเทรนด์ {trend} (คำนวณจาก EMA 12/26) ค่า RSI ล่าสุดวัดได้ {rsi} และระดับความผันผวน ATR อยู่ที่ {atr} ตอนนี้ราคาเข้าใกล้โซนแนวรับที่ {support} ถือเป็นโอกาสที่ดีในการพิจารณาแผนครับ"
    else:
        chart_msg = f"สำหรับการเคลื่อนไหวทางเทคนิคของ {symbol} ปัจจุบันค่าความผันผวน ATR อยู่ที่ {atr} สภาพเส้น EMA บ่งบอกทิศทาง {trend} ส่วนความแข็งแกร่ง RSI อยู่ที่ {rsi} ครับ ระดับแนวต้านสำคัญมองไว้ที่ {resistance}"
        
    debate_steps.append({
        "agent": AGENTS["Chart"]["name"],
        "role": AGENTS["Chart"]["role"],
        "avatar": AGENTS["Chart"]["avatar"],
        "message": chart_msg,
        "timestamp": timestamp
    })
    
    # ขั้นที่ 3: Crypto Analyst AI แสดงความคิดเห็น (เน้นพฤติกรรมวอลลุ่ม)
    if symbol in ["BTCUSDT", "ETHUSDT"]:
        crypto_msg = f"โต๊ะคริปโตยืนยันเพิ่มครับ! สำหรับ {symbol} วอลลุ่มการซื้อขายใน Binance 24 ชม. ที่ผ่านมาค่อนข้างแน่นหนา ตรวจสอบฝั่ง Order Book พบกำแพงแรงซื้อหนาแน่นแถวๆ ระดับจิตวิทยา สอดรับกับสัญญาณเชิงเทคนิคของ Chart AI ครับ"
    else:
        crypto_msg = f"ถึงแม้ {symbol} จะเป็นสินทรัพย์ดั้งเดิม แต่ผมได้ตรวจสอบความเชื่อมโยงกับดัชนีคริปโตแล้ว พบว่าความสัมพันธ์ (Correlation) สภาพคล่องโดยรวมยังเอื้อให้ตลาดเคลื่อนตัวในกรอบปกติครับ ไม่มีสัญญาณขายตื่นตระหนก (Panic Sell) จากฝั่งคริปโต"
        
    debate_steps.append({
        "agent": AGENTS["Crypto"]["name"],
        "role": AGENTS["Crypto"]["role"],
        "avatar": AGENTS["Crypto"]["avatar"],
        "message": crypto_msg,
        "timestamp": timestamp
    })
    
    # ขั้นที่ 4: Wallet Intel AI ตรวจเช็คกระเป๋าและสินทรัพย์รวม
    wallet_msg = f"จากการสแกนยอดคงเหลือใน Team Ecosystem ขณะนี้บัญชีลงทุนพอร์ตรวม (Net Worth) ของเรามีความมั่นคงดี ตรวจไม่พบการทำธุรกรรมขนาดใหญ่ผิดปกติของกลุ่มวาฬ (Whale Wallets) ในสินทรัพย์ {symbol} ทุนสำรองกระแสเงินสดของเราพร้อมรองรับคำสั่งนี้ได้ทันที"
    debate_steps.append({
        "agent": AGENTS["Wallet"]["name"],
        "role": AGENTS["Wallet"]["role"],
        "avatar": AGENTS["Wallet"]["avatar"],
        "message": wallet_msg,
        "timestamp": timestamp
    })
    
    # ขั้นที่ 5: Risk AI ตรวจสอบกฎเหล็กบริหารความเสี่ยง
    passed_txt = "ผ่านการประเมิน 🟢" if risk["passed"] else "ถูกปฏิเสธ/ระงับชั่วคราว 🔴"
    risk_msg = f"แผนกความเสี่ยงตรวจสอบข้อมูลแล้วครับ คำร้องขอเปิดไม้ {action} สำหรับ {symbol} มีสถานะความเสี่ยง: {passed_txt}\n"
    risk_msg += f"- ขนาดความเสี่ยงสะสมต่อพอร์ต: {risk['riskPct']}% (ขีดจำกัดสูงสุด 2%)\n"
    risk_msg += f"- สัดส่วนการถือครองทั้งหมด (Exposure): {risk['exposurePct']}% ของพอร์ตสุทธิ\n"
    
    if risk["passed"]:
        risk_msg += "ความเสี่ยงอยู่ในระดับยอมรับได้ แนะนำให้ใช้สัดส่วน Lot Sizing นี้ตามแผนได้เลยครับ"
    else:
        risk_msg += "แจ้งเตือน! พารามิเตอร์บางตัวขัดต่อกฎเหล็ก (เช่น ไม่มีสัญญาณเทรดหลัก หรือ ความเสี่ยงเกินเกณฑ์) ไม้นี้ต้องยกเลิกหรือหั่นล็อตลงเพื่อความปลอดภัยครับ"
        
    debate_steps.append({
        "agent": AGENTS["Risk"]["name"],
        "role": AGENTS["Risk"]["role"],
        "avatar": AGENTS["Risk"]["avatar"],
        "message": risk_msg,
        "timestamp": timestamp
    })
    
    # ขั้นที่ 6: News/Audit AI เช็คตารางข่าว
    news_msg = "จากการมอนิเตอร์ปฏิทินข่าวเศรษฐกิจของวันนี้ ในช่วง 3 ชั่วโมงถัดไปไม่มีรายงานการประกาศตัวเลขแรงงานสำคัญ (เช่น Non-Farm Payrolls) หรือดัชนีเงินเฟ้อ CPI ที่จะสร้างความผันผวนรุนแรง และไม่มีสัญญาณผิดปกติ (Anomaly) ในระบบการทำราคาของโบรกเกอร์ด้วยครับ ปลอดภัยสำหรับการเทรด"
    debate_steps.append({
        "agent": AGENTS["News"]["name"],
        "role": AGENTS["News"]["role"],
        "avatar": AGENTS["News"]["avatar"],
        "message": news_msg,
        "timestamp": timestamp
    })
    
    # ขั้นที่ 7: CEO สรุปประชุม
    if action == "WAIT":
        ceo_final = f"ขอบคุณทีมงานทุกคน สรุปผลการประชุมสำหรับ {symbol}: เนื่องจากพารามิเตอร์ตลาดยังไม่สอดคล้องตรงตามข้อกำหนดหลักของการเข้าเทรด เราจะดำเนินโหมดเฝ้าระวังภัย (Watch Mode) ต่อไป และยังไม่มีการส่งสัญญาณขออนุมัติถึงคุณโทนี่ในรอบนี้ครับ"
    elif risk["passed"]:
        ceo_final = f"วิเคราะห์ดีมากทุกคน! แผนการเทรด [BUY] {symbol} ได้รับมติเป็นเอกฉันท์และผ่านด่านประเมินความเสี่ยงความเสี่ยงเรียบร้อย ผมกำลังส่งใบสรุปคำสั่งและปุ่มอนุมัติผ่านหน้าแชท Telegram ของคุณโทนี่ทันที โปรดเตรียมความพร้อมสำหรับการยิงคำสั่งซื้อขายจริงเมื่อได้รับการตอบรับครับ"
    else:
        ceo_final = f"มติที่ประชุมสำหรับ {symbol} รอบนี้ถูกระงับ! แม้จะมีสัญญาณทางเทคนิคแต่ขัดแย้งกับข้อบังคับด้านการบริหารความเสี่ยงความเสี่ยง (Risk Rules) ของเรา ความปลอดภัยของทุนต้องมาก่อน ขอยุติเซสชันรอบนี้ครับ"
        
    debate_steps.append({
        "agent": AGENTS["CEO"]["name"],
        "role": AGENTS["CEO"]["role"],
        "avatar": AGENTS["CEO"]["avatar"],
        "message": ceo_final,
        "timestamp": timestamp
    })
    
    return debate_steps
