import asyncio
import logging
import os
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Set, Any

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from backend.shared.events.core import EventBus, CH_NEWS
from backend.shared.schema.events import NewsSentimentEvent

logger = logging.getLogger("news-intelligence")
vader_analyzer = SentimentIntensityAnalyzer()

# Lazy loaded FinBERT pipeline
finbert_pipeline = None

def get_finbert():
    global finbert_pipeline
    if finbert_pipeline is None:
        try:
            from transformers import pipeline
            logger.info("Loading FinBERT model into memory...")
            finbert_pipeline = pipeline("text-classification", model="ProsusAI/finbert")
            logger.info("FinBERT model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            finbert_pipeline = "FAILED"
    return finbert_pipeline

def extract_sentiment(text: str) -> tuple[float, str]:
    """
    Returns (sentiment_score, source_model)
    Attempts FinBERT first, falls back to VADER on failure or memory pressure.
    """
    pipeline_instance = get_finbert()
    
    if pipeline_instance and pipeline_instance != "FAILED":
        try:
            # FinBERT returns labels: positive, negative, neutral
            result = pipeline_instance(text[:512])[0] # Truncate to 512 chars for FinBERT limits
            label = result["label"]
            score = result["score"]
            
            # Convert to -1 to 1 scale
            if label == "positive":
                sentiment = score
            elif label == "negative":
                sentiment = -score
            else:
                sentiment = 0.0
                
            return sentiment, "FinBERT"
        except Exception as e:
            logger.warning(f"FinBERT inference failed: {e}. Falling back to VADER.")
            
    # Fallback to VADER
    scores = vader_analyzer.polarity_scores(text)
    return scores["compound"], "VADER"

TICKER_KEYWORDS = {
    "BTCUSDT": "bitcoin BTC crypto", "ETHUSDT": "ethereum ETH crypto",
    "SOLUSDT": "solana SOL crypto", "BNBUSDT": "binance BNB crypto",
    "XAUUSD": "gold price XAU inflation", "EURUSD": "EUR USD euro dollar forex",
    "NVDA": "nvidia NVDA AI chips GPU", "AAPL": "apple AAPL iphone earnings",
    "MSFT": "microsoft MSFT azure AI", "TSLA": "tesla TSLA EV electric vehicle",
    "AMZN": "amazon AMZN AWS ecommerce", "GOOGL": "google GOOGL alphabet AI search"
}

seen_headlines: Set[str] = set()
SPAM_KEYWORDS = ["scam", "giveaway", "free crypto", "click here", "subscribe now", "promoted", "sponsored"]
PREMIUM_SOURCES = ["Bloomberg", "Reuters", "Financial Times", "Wall Street Journal", "CNBC"]

def calculate_news_score(sentiment: float, relevance: float, recency: float, source_quality: float) -> float:
    base_sentiment_score = (sentiment + 1.0) * 50.0
    final_score = (
        (base_sentiment_score * 0.50) +
        (relevance * 100 * 0.20) +
        (recency * 100 * 0.15) +
        (source_quality * 100 * 0.15)
    )
    return max(0.0, min(100.0, final_score))

def get_fallback_sentiment(ticker: str) -> NewsSentimentEvent:
    headline = f"Market activity continues for {ticker} amid general market trends."
    sentiment, model_used = extract_sentiment(headline)
    
    relevance = 0.5
    recency = 0.5
    source_quality = 0.5
    
    final_score = calculate_news_score(sentiment, relevance, recency, source_quality)
    
    return NewsSentimentEvent(
        ticker=ticker,
        headline=headline,
        sentiment_score=sentiment,
        relevance_score=relevance,
        recency_score=recency,
        source_quality_score=source_quality,
        final_news_score=final_score,
        confidence_score=0.5,
        source=f"FallbackSentinel ({model_used})"
    )

async def fetch_news_and_score(ticker: str, api_key: str, client: httpx.AsyncClient) -> NewsSentimentEvent:
    keyword = TICKER_KEYWORDS.get(ticker, ticker)
    url = f"https://newsapi.org/v2/everything?q={keyword}&apiKey={api_key}&pageSize=10&sortBy=publishedAt&language=en"
    
    try:
        r = await client.get(url, timeout=5.0)
        if r.status_code == 200:
            articles = r.json().get("articles", [])
            valid_articles = []
            now = datetime.now(timezone.utc)
            
            for a in articles:
                title = a.get("title", "")
                if title in seen_headlines: continue
                if any(spam in title.lower() for spam in SPAM_KEYWORDS): continue
                
                pub_date_str = a.get("publishedAt")
                if pub_date_str:
                    try:
                        pub_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        age_hours = (now - pub_date).total_seconds() / 3600
                        if age_hours > 24: continue
                    except Exception:
                        age_hours = 12
                else:
                    age_hours = 12
                
                seen_headlines.add(title)
                if len(seen_headlines) > 1000: seen_headlines.clear()
                
                desc = a.get("description", "") or ""
                text = f"{title}. {desc}"
                relevance = min(1.0, (text.lower().count(ticker.lower()[:3]) * 0.2) + 0.4)
                
                source_name = a.get("source", {}).get("name", "")
                source_quality = 1.0 if any(p in source_name for p in PREMIUM_SOURCES) else 0.6
                recency = max(0.0, 1.0 - (age_hours / 24.0))
                
                # NLP Inference
                sentiment, model_used = await asyncio.to_thread(extract_sentiment, text)
                
                final_score = calculate_news_score(sentiment, relevance, recency, source_quality)
                
                valid_articles.append({
                    "headline": title,
                    "sentiment": sentiment,
                    "relevance": relevance,
                    "recency": recency,
                    "source_quality": source_quality,
                    "final_score": final_score,
                    "source": f"{source_name} ({model_used})"
                })
            
            if valid_articles:
                valid_articles.sort(key=lambda x: x["final_score"], reverse=True)
                top = valid_articles[0]
                conf = min(0.95, 0.6 + (len(valid_articles) * 0.05))
                
                logger.info(f"[News] {ticker}: {len(valid_articles)} valid articles. Top Score: {top['final_score']:.1f}")
                return NewsSentimentEvent(
                    ticker=ticker,
                    headline=top["headline"][:200],
                    sentiment_score=top["sentiment"],
                    relevance_score=top["relevance"],
                    recency_score=top["recency"],
                    source_quality_score=top["source_quality"],
                    final_news_score=top["final_score"],
                    confidence_score=conf,
                    source=top["source"] or "NewsAPI"
                )
    except Exception as e:
        logger.error(f"[NewsAPI] Error fetching {ticker}: {e}")

    return get_fallback_sentiment(ticker)

async def news_intelligence_poller(event_bus: EventBus):
    logger.info("Starting News Intelligence Engine...")
    tickers = list(TICKER_KEYWORDS.keys())
    
    while True:
        try:
            api_key = os.getenv("NEWS_API_KEY", "").strip()
            has_real_api = bool(api_key) and "News" not in api_key and len(api_key) > 10

            async with httpx.AsyncClient() as client:
                for ticker in tickers:
                    if has_real_api:
                        event = await fetch_news_and_score(ticker, api_key, client)
                    else:
                        event = get_fallback_sentiment(ticker)
                        
                    await event_bus.publish(CH_NEWS, event.model_dump())
                    await asyncio.sleep(0.5 if has_real_api else 0.1)

            logger.info("[News] Cycle complete. Next update in 5 minutes.")
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[News] Fatal error: {e}")
            await asyncio.sleep(60)

def start_news_intelligence_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    registry.register(news_intelligence_poller(event_bus), name="news_poller")
