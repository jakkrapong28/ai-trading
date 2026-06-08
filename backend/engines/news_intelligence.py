import asyncio
import logging
import os
import httpx
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from backend.shared.events.core import EventBus, CH_NEWS
from backend.shared.schema.events import NewsSentimentEvent

logger = logging.getLogger("news-intelligence")
analyzer = SentimentIntensityAnalyzer()

# Keywords mapping สำหรับแต่ละ ticker
TICKER_KEYWORDS = {
    "BTCUSDT":  "bitcoin BTC crypto",
    "ETHUSDT":  "ethereum ETH crypto",
    "SOLUSDT":  "solana SOL crypto",
    "BNBUSDT":  "binance BNB crypto",
    "XAUUSD":   "gold price XAU inflation",
    "EURUSD":   "EUR USD euro dollar forex",
    "NVDA":     "nvidia NVDA AI chips GPU",
    "AAPL":     "apple AAPL iphone earnings",
    "MSFT":     "microsoft MSFT azure AI",
    "TSLA":     "tesla TSLA EV electric vehicle",
    "AMZN":     "amazon AMZN AWS ecommerce",
    "GOOGL":    "google GOOGL alphabet AI search"
}

# Fallback headlines เมื่อไม่มี API key
FALLBACK_HEADLINES = {
    "BTCUSDT":  [
        "Bitcoin maintains strong institutional demand amid ETF inflows",
        "Crypto market shows resilience as bitcoin finds key support level",
        "Bitcoin network hashrate reaches new all-time high"
    ],
    "ETHUSDT":  [
        "Ethereum staking yields attract long-term investors",
        "ETH price action consolidates near key resistance zone",
        "Ethereum layer-2 ecosystem continues rapid expansion"
    ],
    "XAUUSD":   [
        "Gold prices firm as central bank buying remains robust",
        "Safe haven demand supports gold amid global uncertainty",
        "Inflation concerns keep gold attractive for investors"
    ],
    "NVDA":     [
        "Nvidia data center revenue continues record pace on AI demand",
        "NVDA stock benefits from accelerating AI infrastructure spending",
        "Nvidia announces next-generation GPU architecture for AI workloads"
    ],
    "AAPL":     [
        "Apple iPhone sales exceed analyst expectations in latest quarter",
        "Services revenue growth drives Apple valuation higher",
        "Apple AI features drive upgrade cycle demand"
    ],
    "MSFT":     [
        "Microsoft Azure AI growth accelerates enterprise adoption",
        "Copilot integration boosts Microsoft productivity suite revenue",
        "Microsoft cloud margins improve on AI efficiency gains"
    ],
    "TSLA":     [
        "Tesla delivery numbers beat consensus estimates for quarter",
        "Tesla Cybertruck production ramp progresses ahead of schedule",
        "Tesla energy storage business shows strong growth trajectory"
    ]
}

def get_fallback_sentiment(ticker: str) -> NewsSentimentEvent:
    """สร้าง sentiment จาก fallback headlines เมื่อไม่มี API"""
    headlines = FALLBACK_HEADLINES.get(ticker, [f"Market activity continues for {ticker}"])
    headline = headlines[int(datetime.now().minute) % len(headlines)]  # rotate
    scores = analyzer.polarity_scores(headline)
    return NewsSentimentEvent(
        ticker=ticker,
        headline=headline,
        sentiment_score=round(scores["compound"], 3),
        confidence_score=0.65,
        source="FallbackSentinel"
    )

async def fetch_newsapi_sentiment(ticker: str, api_key: str, client: httpx.AsyncClient) -> NewsSentimentEvent:
    """ดึงข่าวจริงจาก NewsAPI และคำนวณ VADER sentiment"""
    keyword = TICKER_KEYWORDS.get(ticker, ticker)
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={keyword}&apiKey={api_key}&pageSize=5"
        f"&sortBy=publishedAt&language=en"
    )
    try:
        r = await client.get(url, timeout=5.0)
        if r.status_code == 200:
            articles = r.json().get("articles", [])
            if articles:
                # รวม sentiment จากหลายบทความ weighted by position
                all_scores = []
                headlines_used = []
                for i, article in enumerate(articles[:5]):
                    title = article.get("title", "")
                    desc = article.get("description", "") or ""
                    text = f"{title}. {desc}"
                    scores = analyzer.polarity_scores(text)
                    weight = 1.0 / (i + 1)  # บทความแรกสำคัญกว่า
                    all_scores.append(scores["compound"] * weight)
                    headlines_used.append(title)

                total_weight = sum(1.0 / (i + 1) for i in range(len(all_scores)))
                weighted_sentiment = sum(all_scores) / total_weight if total_weight > 0 else 0.0

                # ใช้ headline แรกเป็น representative
                main_headline = headlines_used[0] if headlines_used else f"News for {ticker}"

                logger.info(f"[NewsAPI] {ticker}: {len(articles)} articles → sentiment {weighted_sentiment:.3f}")
                return NewsSentimentEvent(
                    ticker=ticker,
                    headline=main_headline[:200],  # truncate
                    sentiment_score=round(weighted_sentiment, 3),
                    confidence_score=min(0.95, 0.7 + len(articles) * 0.05),
                    source="NewsAPI"
                )
        else:
            logger.warning(f"[NewsAPI] {ticker}: HTTP {r.status_code}")
    except Exception as e:
        logger.error(f"[NewsAPI] Error fetching {ticker}: {e}")

    return get_fallback_sentiment(ticker)

async def news_intelligence_poller(event_bus: EventBus):
    """
    News Intelligence Engine — ดึงข่าวจริงและคำนวณ sentiment
    - ใช้ NewsAPI ถ้ามี key
    - ใช้ VADER กับ fallback headlines ถ้าไม่มี key
    - Publish ทุก 5 นาที
    """
    logger.info("Starting News Intelligence Engine...")
    tickers = list(TICKER_KEYWORDS.keys())

    while True:
        try:
            # โหลด API key ทุกรอบ (user อาจ update ผ่าน settings)
            api_key = os.getenv("NEWS_API_KEY", "").strip()
            has_real_api = bool(api_key) and "News" not in api_key and len(api_key) > 10

            async with httpx.AsyncClient() as client:
                for ticker in tickers:
                    try:
                        if has_real_api:
                            event = await fetch_newsapi_sentiment(ticker, api_key, client)
                        else:
                            event = get_fallback_sentiment(ticker)

                        await event_bus.publish(CH_NEWS, event.model_dump())
                        logger.info(
                            f"[News] {ticker}: {event.source} → "
                            f"sentiment={event.sentiment_score:+.3f} "
                            f"(conf={event.confidence_score:.2f})"
                        )
                        # หน่วงระหว่าง ticker เพื่อไม่ Rate Limit
                        await asyncio.sleep(0.5 if has_real_api else 0.1)

                    except Exception as e:
                        logger.error(f"[News] Error processing {ticker}: {e}")

            # รอ 5 นาทีก่อนรอบถัดไป
            logger.info("[News] Cycle complete. Next update in 5 minutes.")
            await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("[News] Engine shutting down.")
            break
        except Exception as e:
            logger.error(f"[News] Fatal error in poller: {e}")
            await asyncio.sleep(60)

def start_news_intelligence_engine(event_bus: EventBus):
    asyncio.create_task(news_intelligence_poller(event_bus))
