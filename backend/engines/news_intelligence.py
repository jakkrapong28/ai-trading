import asyncio
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from backend.shared.events.core import EventBus, CH_NEWS
from backend.shared.schema.events import NewsSentimentEvent

logger = logging.getLogger("news-intelligence")
analyzer = SentimentIntensityAnalyzer()

async def mock_news_poller(event_bus: EventBus):
    logger.info("Starting News Intelligence Poller...")
    tickers = ["BTCUSDT", "ETHUSDT", "NVDA", "AAPL", "MSFT", "XAUUSD"]
    while True:
        try:
            for ticker in tickers:
                # Mock sentiment
                headline = f"Market updates and economic data affecting {ticker}"
                sentiment_dict = analyzer.polarity_scores(headline)
                event = NewsSentimentEvent(
                    ticker=ticker,
                    headline=headline,
                    sentiment_score=sentiment_dict['compound'],
                    confidence_score=0.85,
                    source="GlobalFinanceNews"
                )
                await event_bus.publish(CH_NEWS, event.model_dump())
                logger.info(f"Published news for {ticker}: Score {event.sentiment_score}")
            await asyncio.sleep(300) # every 5 mins
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"News poller error: {e}")
            await asyncio.sleep(60)

def start_news_intelligence_engine(event_bus: EventBus):
    asyncio.create_task(mock_news_poller(event_bus))
