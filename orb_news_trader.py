# orb_news_trader.py
# An automated trading bot that combines news sentiment and ORB strategy

import os
import time
import json
import logging
import datetime
import signal
import requests
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import alpaca_trade_api as tradeapi
import pandas as pd
import pytz
import numpy as np

# Import the trade queue module
try:
    from trade_queue import queue_trade, process_queue
    QUEUE_AVAILABLE = True
except ImportError:
    QUEUE_AVAILABLE = False

# Import timezone utilities if available
try:
    from timezone_utils import get_eastern_time, get_current_market_period
    TIMEZONE_UTILS_AVAILABLE = True
except ImportError:
    TIMEZONE_UTILS_AVAILABLE = False

# Set up timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Function execution timed out")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("orb_news_trader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('orb_news_trader')

# Load environment variables
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Alpaca API credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Alpaca API
alpaca = tradeapi.REST(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_PAPER_URL,
    api_version='v2'
)

# Create necessary directories
Path("data").mkdir(exist_ok=True)
Path("data/orb_data").mkdir(exist_ok=True)

# Configuration
SYMBOLS_TO_TRACK = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "AMD", "INTC", "IBM"]
INITIAL_CAPITAL = 10000
MAX_POSITION_PCT = 0.1  # Maximum 10% of portfolio in one position

# ORB Strategy Configuration
ORB_TIMEFRAME = 15  # Opening range in minutes (usually 15 or 30)
ORB_BREAKOUT_PCT = 0.002  # Breakout threshold (0.2%)
ORB_PROFIT_TARGET_PCT = 0.01  # Take profit at 1%
ORB_STOP_LOSS_PCT = 0.005  # Stop loss at 0.5%
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30

class ORBNewsTrader:
    """
    Trading bot that combines Opening Range Breakout (ORB) strategy with
    news sentiment analysis for improved trading decisions.
    """
    
    def __init__(self):
        """Initialize the trading bot"""
        self.orb_ranges = {}  # Store ORB ranges for symbols
        self.orb_signals = {}  # Store current ORB signals
        self.news_sentiment = {}  # Store news sentiment for symbols
        self.positions = {}  # Store current positions
        
        # Load previous state if exists
        self.load_state()
        
    def load_state(self):
        """Load previous trading state"""
        state_file = Path("data/orb_state.json")
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
                    self.orb_ranges = state.get("orb_ranges", {})
                    self.news_sentiment = state.get("news_sentiment", {})
                logger.info(f"Loaded previous state with {len(self.orb_ranges)} ORB ranges")
            except Exception as e:
                logger.error(f"Error loading state: {e}")
    
    def save_state(self):
        """Save current trading state"""
        try:
            state = {
                "orb_ranges": self.orb_ranges,
                "news_sentiment": self.news_sentiment,
                "last_updated": datetime.datetime.now().isoformat()
            }
            with open("data/orb_state.json", "w") as f:
                json.dump(state, f, indent=2)
            logger.info("Saved current trading state")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def get_eastern_time(self):
        """Get current time in US Eastern Time"""
        if TIMEZONE_UTILS_AVAILABLE:
            return get_eastern_time()
        else:
            # Fallback if timezone_utils is not available
            utc_now = datetime.datetime.now(pytz.UTC)
            eastern = pytz.timezone('US/Eastern')
            return utc_now.astimezone(eastern)
    
    def is_market_open(self):
        """Check if the market is currently open"""
        try:
            clock = alpaca.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            # Default to closed if we can't check
            return False
    
    def get_current_market_data(self, symbol):
        """Get current market data for a symbol"""
        try:
            quote = alpaca.get_latest_quote(symbol)
            bid_price = float(quote.bid_price)
            ask_price = float(quote.ask_price)
            mid_price = (bid_price + ask_price) / 2
            
            return {
                "symbol": symbol,
                "bid": bid_price,
                "ask": ask_price,
                "mid": mid_price,
                "timestamp": datetime.datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    def fetch_historical_bars(self, symbol, timeframe="15Min", limit=100):
        """Fetch historical bars for a symbol"""
        try:
            # End time should be now
            end_time = pd.Timestamp.now(tz="America/New_York")
            
            # Calculate start time based on limit and timeframe
            if timeframe == "1Min":
                start_time = end_time - pd.Timedelta(minutes=limit)
            elif timeframe == "5Min":
                start_time = end_time - pd.Timedelta(minutes=limit*5)
            elif timeframe == "15Min":
                start_time = end_time - pd.Timedelta(minutes=limit*15)
            else:
                start_time = end_time - pd.Timedelta(days=limit)
                
            # Format timestamps for Alpaca API
            start_str = start_time.isoformat()
            end_str = end_time.isoformat()
            
            bars = alpaca.get_bars(
                symbol, 
                timeframe,
                start=start_str,
                end=end_str,
                limit=limit
            ).df
            
            if bars.empty:
                logger.warning(f"No historical data found for {symbol}")
                return None
                
            return bars
            
        except Exception as e:
            logger.error(f"Error fetching bars for {symbol}: {e}")
            return None
    
    def calculate_opening_range(self, symbol):
        """
        Calculate the opening range for a symbol
        The opening range is defined as the high and low during the first X minutes of trading
        """
        try:
            # Get current ET time
            et_now = self.get_eastern_time()
            
            # Check if we already calculated the opening range today
            if symbol in self.orb_ranges:
                orb_date = self.orb_ranges[symbol].get("date")
                if orb_date == et_now.strftime("%Y-%m-%d"):
                    logger.info(f"Using existing opening range for {symbol}")
                    return self.orb_ranges[symbol]
            
            # Get 1-minute bars for today
            bars = self.fetch_historical_bars(symbol, timeframe="1Min", limit=60)
            
            if bars is None or bars.empty:
                logger.warning(f"No bars available to calculate opening range for {symbol}")
                return None
            
            # Filter bars from market open to market open + ORB_TIMEFRAME
            market_open_time = pd.Timestamp(
                year=et_now.year, month=et_now.month, day=et_now.day,
                hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE,
                tz="America/New_York"
            )
            
            # Calculate end of opening range
            range_end_time = market_open_time + pd.Timedelta(minutes=ORB_TIMEFRAME)
            
            # Filter bars within opening range
            opening_bars = bars[(bars.index >= market_open_time) & (bars.index <= range_end_time)]
            
            if opening_bars.empty:
                logger.warning(f"No bars available within opening range for {symbol}")
                # Try getting data from previous day
                yesterday = et_now - datetime.timedelta(days=1)
                market_open_time = pd.Timestamp(
                    year=yesterday.year, month=yesterday.month, day=yesterday.day,
                    hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE,
                    tz="America/New_York"
                )
                range_end_time = market_open_time + pd.Timedelta(minutes=ORB_TIMEFRAME)
                
                # Get yesterday's data
                yesterday_bars = self.fetch_historical_bars(symbol, timeframe="1Min", limit=60*8)
                if yesterday_bars is not None and not yesterday_bars.empty:
                    opening_bars = yesterday_bars[(yesterday_bars.index >= market_open_time) & 
                                                (yesterday_bars.index <= range_end_time)]
            
            if opening_bars.empty:
                logger.warning(f"Could not get opening range data for {symbol}")
                return None
            
            # Calculate high and low of opening range
            opening_high = opening_bars['high'].max()
            opening_low = opening_bars['low'].min()
            
            # Calculate midpoint of opening range
            midpoint = (opening_high + opening_low) / 2
            
            # Store the opening range
            orb_data = {
                "symbol": symbol,
                "date": et_now.strftime("%Y-%m-%d"),
                "range_start": market_open_time.isoformat(),
                "range_end": range_end_time.isoformat(),
                "high": float(opening_high),
                "low": float(opening_low),
                "midpoint": float(midpoint),
                "calculated_at": et_now.isoformat()
            }
            
            # Save to instance variable
            self.orb_ranges[symbol] = orb_data
            
            # Save ORB data to file
            self.save_orb_data(symbol, orb_data, opening_bars)
            
            logger.info(f"Calculated opening range for {symbol}: high=${opening_high:.2f}, low=${opening_low:.2f}")
            return orb_data
            
        except Exception as e:
            logger.error(f"Error calculating opening range for {symbol}: {e}")
            return None
    
    def save_orb_data(self, symbol, orb_data, opening_bars):
        """Save ORB data to file for later analysis"""
        try:
            # Save the summary data
            date_str = orb_data["date"].replace("-", "")
            with open(f"data/orb_data/{symbol}_{date_str}_orb.json", "w") as f:
                json.dump(orb_data, f, indent=2)
            
            # Save the opening range bars to CSV
            if opening_bars is not None and not opening_bars.empty:
                opening_bars.to_csv(f"data/orb_data/{symbol}_{date_str}_orb_bars.csv")
                
        except Exception as e:
            logger.error(f"Error saving ORB data for {symbol}: {e}")
    
    def check_orb_signals(self, symbol):
        """Check for ORB breakout signals"""
        try:
            # First, make sure we have the opening range calculated
            orb_range = self.orb_ranges.get(symbol)
            if not orb_range:
                orb_range = self.calculate_opening_range(symbol)
                if not orb_range:
                    logger.warning(f"Cannot check ORB signals for {symbol} without opening range")
                    return None
            
            # Get current price data
            price_data = self.get_current_market_data(symbol)
            if not price_data:
                logger.warning(f"Cannot check ORB signals for {symbol} without current price")
                return None
            
            current_price = price_data["mid"]
            
            # Check for breakouts
            orb_high = orb_range["high"]
            orb_low = orb_range["low"]
            
            # Calculate breakout thresholds with added percentage buffer
            high_breakout = orb_high * (1 + ORB_BREAKOUT_PCT)
            low_breakout = orb_low * (1 - ORB_BREAKOUT_PCT)
            
            # Determine signal
            signal = None
            if current_price > high_breakout:
                signal = "BUY"  # Bullish breakout
                logger.info(f"ORB BUY signal for {symbol}: price ${current_price:.2f} > high breakout ${high_breakout:.2f}")
            elif current_price < low_breakout:
                signal = "SELL"  # Bearish breakout
                logger.info(f"ORB SELL signal for {symbol}: price ${current_price:.2f} < low breakout ${low_breakout:.2f}")
            else:
                signal = "HOLD"  # No breakout
                logger.info(f"No ORB breakout for {symbol}: price ${current_price:.2f} within range")
            
            # Create signal data
            signal_data = {
                "symbol": symbol,
                "date": orb_range["date"],
                "current_price": current_price,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "high_breakout": high_breakout,
                "low_breakout": low_breakout,
                "signal": signal,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Save to instance variable
            self.orb_signals[symbol] = signal_data
            
            return signal_data
            
        except Exception as e:
            logger.error(f"Error checking ORB signals for {symbol}: {e}")
            return None
    
    def fetch_news_articles(self, symbols, max_results=5):
        """Fetch news articles about the given symbols"""
        # Create a query string with all symbols
        query = " OR ".join([symbol for symbol in symbols[:5]])  # Limit to 5 symbols to avoid long queries
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize={max_results}&apiKey={NEWS_API_KEY}"

        try:
            logger.info(f"Fetching news with query: {query}")
            
            # Set a timeout for the request
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)  # 30 second timeout
            
            response = requests.get(url, timeout=20)
            
            # Clear the alarm
            signal.alarm(0)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                logger.info(f"Received {len(articles)} articles from News API")
                
                # Process articles
                processed_articles = []
                for article in articles:
                    title = article.get("title", "")
                    content = article.get("content", "") or article.get("description", "")
                    
                    processed_articles.append({
                        "title": title,
                        "content": content[:500],  # Limit content length
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "published_at": article.get("publishedAt", "")
                    })
                    
                return processed_articles
            else:
                logger.error(f"Failed to fetch news: {response.status_code} - {response.text[:200]}")
                return []
                
        except TimeoutError:
            logger.error("News API request timed out")
            return []
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []
        finally:
            # Reset the alarm handler
            signal.alarm(0)
    
    def analyze_article(self, text):
        """Analyze a news article using GPT to extract sentiment and companies"""
        # Truncate text to ensure it's not too long
        max_length = 1000
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        prompt = f"""
You are a financial trading assistant. Given a news article, return a JSON object with:

1. Market sentiment: Bullish, Bearish, or Neutral
2. A list of up to 3 major publicly traded companies affected. Return exact company names, not ticker symbols.
   IMPORTANT: Only include companies that are publicly traded on stock exchanges.

Format:
{{
  "sentiment": "Bullish",
  "related_companies": ["Apple", "Tesla"]
}}

Article:
{text}
"""

        try:
            logger.info("Sending request to OpenAI API")
            # Set a timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)  # 30 second timeout
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a market-savvy financial assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=20  # Client timeout
            )
            
            # Clear the alarm
            signal.alarm(0)
            
            content = response.choices[0].message.content
            logger.info(f"GPT response received")
            
            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1 or end == 0:
                logger.error(f"Invalid JSON format in GPT response")
                return {"sentiment": "Neutral", "related_companies": []}
                
            json_blob = content[start:end]
            parsed = json.loads(json_blob)
            return parsed

        except TimeoutError:
            logger.error("OpenAI API request timed out")
            return {"sentiment": "Neutral", "related_companies": []}
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {"sentiment": "Neutral", "related_companies": []}
        except Exception as e:
            logger.error(f"GPT error: {e}")
            return {"sentiment": "Neutral", "related_companies": []}
        finally:
            # Reset the alarm handler
            signal.alarm(0)
    
    def match_company_to_symbol(self, company_name, symbols_to_check):
        """Match company name to stock symbol"""
        # Define common company name variations
        company_aliases = {
            "apple": "AAPL",
            "microsoft": "MSFT",
            "amazon": "AMZN",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "meta": "META",
            "facebook": "META",
            "tesla": "TSLA",
            "nvidia": "NVDA",
            "amd": "AMD",
            "advanced micro devices": "AMD",
            "intel": "INTC",
            "ibm": "IBM",
            "international business machines": "IBM"
        }
        
        # Try direct lookup
        company_lower = company_name.lower()
        if company_lower in company_aliases:
            symbol = company_aliases[company_lower]
            if symbol in symbols_to_check:
                return symbol
        
        # No match found
        return None
    
    def process_news_data(self):
        """Process news data and update sentiment for symbols"""
        logger.info("Processing news data")
        
        # Fetch news articles
        articles = self.fetch_news_articles(SYMBOLS_TO_TRACK, max_results=10)
        
        if not articles:
            logger.warning("No news articles found")
            return
        
        news_results = []
        
        # Process each article
        for article in articles:
            try:
                # Process article
                title = article.get('title', 'Untitled article')
                logger.info(f"Processing: {title[:100]}...")
                
                # Analyze with GPT
                full_text = f"{title} {article.get('content', '')}"
                analysis = self.analyze_article(full_text)
                sentiment = analysis.get("sentiment", "Neutral")
                related_companies = analysis.get("related_companies", [])
                
                logger.info(f"Sentiment: {sentiment}")
                logger.info(f"Related companies: {related_companies}")
                
                # Match to symbols
                for company in related_companies:
                    symbol = self.match_company_to_symbol(company, SYMBOLS_TO_TRACK)
                    
                    if not symbol:
                        continue
                        
                    logger.info(f"Matched company '{company}' to symbol {symbol}")
                    
                    # Update sentiment for this symbol
                    if symbol not in self.news_sentiment:
                        self.news_sentiment[symbol] = []
                    
                    # Add the sentiment data
                    sentiment_data = {
                        "sentiment": sentiment,
                        "article_title": title,
                        "article_url": article.get("url", ""),
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    
                    # Keep only the 5 most recent sentiment entries
                    self.news_sentiment[symbol].append(sentiment_data)
                    if len(self.news_sentiment[symbol]) > 5:
                        self.news_sentiment[symbol] = self.news_sentiment[symbol][-5:]
                    
                    # Add to results
                    news_results.append({
                        "symbol": symbol,
                        "company": company,
                        "sentiment": sentiment,
                        "article_title": title
                    })
                
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                continue
        
        # Save updated sentiment data
        self.save_state()
        
        logger.info(f"Processed {len(articles)} articles, updated sentiment for {len(news_results)} symbol-article pairs")
        return news_results
    
    def get_combined_signal(self, symbol):
        """
        Combine ORB strategy signal with news sentiment to get final trading decision
        
        Returns: tuple (decision, confidence, data)
        """
        try:
            # Get ORB signal
            orb_data = self.check_orb_signals(symbol)
            if not orb_data:
                return ("HOLD", 0.5, {"reason": "No ORB data available"})
            
            orb_signal = orb_data["signal"]
            
            # Get news sentiment
            sentiment_data = self.news_sentiment.get(symbol, [])
            
            # If no sentiment data, just use ORB signal
            if not sentiment_data:
                return (orb_signal, 0.6, {"reason": "Using ORB signal only (no news data)", "orb_data": orb_data})
            
            # Calculate overall sentiment from recent news
            sentiment_scores = {
                "Bullish": 1.0,
                "Neutral": 0.5,
                "Bearish": 0.0
            }
            
            # Get sentiment scores, weighting more recent news higher
            scores = []
            weights = []
            for i, item in enumerate(sentiment_data):
                score = sentiment_scores.get(item["sentiment"], 0.5)
                
                # More recent news gets higher weight
                weight = 1.0 + (i * 0.2)  
                
                scores.append(score)
                weights.append(weight)
            
            # Calculate weighted average sentiment
            if sum(weights) > 0:
                avg_sentiment = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
            else:
                avg_sentiment = 0.5
            
            # Sentiment labels
            if avg_sentiment > 0.7:
                sentiment_label = "Bullish"
                sentiment_signal = "BUY"
            elif avg_sentiment < 0.3:
                sentiment_label = "Bearish"
                sentiment_signal = "SELL"
            else:
                sentiment_label = "Neutral"
                sentiment_signal = "HOLD"
                
            logger.info(f"Average sentiment for {symbol}: {avg_sentiment:.2f} ({sentiment_label})")
            
            # Decision logic:
            # If ORB and sentiment agree, use that signal with high confidence
            # If they disagree, use ORB signal but with lower confidence
            # If ORB is HOLD, but sentiment is strong, use sentiment with lower confidence
            
            if orb_signal == sentiment_signal:
                # Signals agree
                confidence = 0.8 if orb_signal != "HOLD" else 0.6
                reason = f"ORB and news sentiment both suggest {orb_signal}"
                decision = orb_signal
            elif orb_signal == "HOLD" and sentiment_signal != "HOLD":
                # ORB says HOLD but sentiment is strong
                confidence = 0.6
                reason = f"News sentiment suggests {sentiment_signal} while ORB indicates HOLD"
                decision = sentiment_signal
            else:
                # Signals disagree, prioritize ORB
                confidence = 0.7
                reason = f"ORB signal {orb_signal} overrides news sentiment {sentiment_signal}"
                decision = orb_signal
            
            return (decision, confidence, {
                "reason": reason,
                "orb_signal": orb_signal,
                "sentiment_signal": sentiment_signal,
                "avg_sentiment": avg_sentiment,
                "sentiment_label": sentiment_label,
                "orb_data": orb_data
            })
            
        except Exception as e:
            logger.error(f"Error generating combined signal for {symbol}: {e}")
            return ("HOLD", 0.5, {"reason": f"Error: {str(e)}"})
    
    def calculate_position_size(self, symbol, confidence, account):
        """Calculate position size based on portfolio value and confidence"""
        try:
            # Get portfolio value
            portfolio_value = float(account.portfolio_value)
            cash = float(account.cash)
            
            # Base position size (% of portfolio)
            base_size = portfolio_value * MAX_POSITION_PCT
            
            # Adjust based on confidence (0.5 to 0.9)
            adjusted_size = base_size * confidence
            
            # Cap at available cash (with 5% buffer)
            position_size = min(adjusted_size, cash * 0.95)
            
            logger.info(f"Calculated position size for {symbol}: ${position_size:.2f} (confidence: {confidence:.2f})")
            return position_size
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    def execute_trade(self, symbol, decision, confidence, account, reason_data=None):
        """Execute a trade based on the decision or queue it if market is closed"""
        market_open = self.is_market_open()
        
        # Format reason data for logging
        reason = reason_data.get("reason", "No reason provided") if reason_data else "No reason provided"
        
        # If market is closed and queue is available, queue the trade
        if not market_open and QUEUE_AVAILABLE:
            logger.info(f"Market is closed, queueing {decision} for {symbol}")
            
            # Convert confidence to sentiment string
            if confidence > 0.7:
                sentiment_str = "Bullish" if decision == "BUY" else "Bearish"
            else:
                sentiment_str = "Neutral"
                
            # Get news title if available
            news_title = None
            if reason_data and "sentiment_signal" in reason_data:
                # Try to get the most recent news title for this symbol
                if symbol in self.news_sentiment and self.news_sentiment[symbol]:
                    news_title = self.news_sentiment[symbol][-1].get("article_title")
            
            # Queue the trade
            queue_trade(symbol, decision, sentiment=sentiment_str, news_title=news_title)
            
            return {
                "symbol": symbol,
                "decision": decision,
                "success": True,
                "message": f"Queued {decision} for next market open",
                "reason": reason,
                "queued": True
            }
        
        # If market is closed and queue is not available, log and return
        if not market_open and not QUEUE_AVAILABLE:
            logger.info(f"Market is closed and trade_queue module not available, cannot trade {symbol}")
            return {
                "symbol": symbol,
                "decision": decision,
                "success": False,
                "message": "Market closed and queue not available",
                "reason": reason,
                "queued": False
            }
        
        # Market is open, execute trade directly
        try:
            if decision == "BUY":
                # Calculate position size
                position_size = self.calculate_position_size(symbol, confidence, account)
                
                # Get current price
                try:
                    quote = alpaca.get_latest_quote(symbol)
                    price = float(quote.ask_price)  # Use ask price for buying
                except:
                    # Fallback to last trade price
                    bar = alpaca.get_latest_bar(symbol)
                    price = float(bar.c)
                
                # Calculate quantity
                quantity = int(position_size / price)
                if quantity < 1:
                    logger.info(f"Position size too small for {symbol}: ${position_size:.2f} / ${price:.2f} = {quantity}")
                    return {
                        "symbol": symbol,
                        "decision": decision,
                        "success": False,
                        "message": "Position size too small",
                        "reason": reason,
                        "queued": False
                    }
                
                # Check if we already have this position
                try:
                    positions = alpaca.list_positions()
                    current_positions = {p.symbol: p for p in positions}
                    
                    if symbol in current_positions:
                        existing_position = current_positions[symbol]
                        logger.info(f"Already have position in {symbol}: {existing_position.qty} shares at ${float(existing_position.avg_entry_price):.2f}")
                        
                        return {
                            "symbol": symbol,
                            "decision": decision,
                            "success": False,
                            "message": f"Already have position in {symbol}",
                            "reason": reason,
                            "queued": False
                        }
                except Exception as e:
                    logger.warning(f"Error checking existing positions: {e}")
                
                # Calculate stop loss and take profit prices
                stop_loss_price = price * (1 - ORB_STOP_LOSS_PCT)
                take_profit_price = price * (1 + ORB_PROFIT_TARGET_PCT)
                
                # Submit market order
                logger.info(f"Buying {quantity} shares of {symbol} at ~${price:.2f}")
                try:
                    order = alpaca.submit_order(
                        symbol=symbol,
                        qty=quantity,
                        side="buy",
                        type="market",
                        time_in_force="day"
                    )
                    
                    # Save order details
                    order_details = {
                        "symbol": symbol,
                        "order_id": order.id,
                        "quantity": quantity,
                        "price": price,
                        "decision": decision,
                        "confidence": confidence,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "stop_loss": stop_loss_price,
                        "take_profit": take_profit_price,
                        "reason": reason
                    }
                    
                    # Add stop loss and take profit orders
                    try:
                        # Wait for the main order to fill
                        filled_order = self.wait_for_order_fill(order.id)
                        if filled_order and filled_order.status == "filled":
                            # Submit stop loss order
                            stop_order = alpaca.submit_order(
                                symbol=symbol,
                                qty=quantity,
                                side="sell",
                                type="stop",
                                time_in_force="day",
                                stop_price=stop_loss_price
                            )
                            logger.info(f"Submitted stop loss order for {symbol} at ${stop_loss_price:.2f}")
                            
                            # Submit take profit order
                            profit_order = alpaca.submit_order(
                                symbol=symbol,
                                qty=quantity,
                                side="sell",
                                type="limit",
                                time_in_force="day",
                                limit_price=take_profit_price
                            )
                            logger.info(f"Submitted take profit order for {symbol} at ${take_profit_price:.2f}")
                            
                            # Update order details
                            order_details["stop_loss_order_id"] = stop_order.id
                            order_details["take_profit_order_id"] = profit_order.id
                    except Exception as e:
                        logger.error(f"Error setting stop loss/take profit for {symbol}: {e}")
                    
                    # Save order to file
                    self.save_order_details(order_details)
                    
                    return {
                        "symbol": symbol,
                        "decision": decision,
                        "success": True,
                        "message": f"Bought {quantity} shares at ~${price:.2f}",
                        "order_id": order.id,
                        "stop_loss": stop_loss_price,
                        "take_profit": take_profit_price,
                        "reason": reason,
                        "queued": False
                    }
                    
                except Exception as e:
                    logger.error(f"Error submitting buy order for {symbol}: {e}")
                    return {
                        "symbol": symbol,
                        "decision": decision,
                        "success": False,
                        "message": f"Error submitting order: {e}",
                        "reason": reason,
                        "queued": False
                    }
                
            elif decision == "SELL":
                # Check if we have a position in this symbol
                try:
                    position = alpaca.get_position(symbol)
                    quantity = int(position.qty)
                    
                    # Submit market order to sell all shares
                    logger.info(f"Selling {quantity} shares of {symbol}")
                    order = alpaca.submit_order(
                        symbol=symbol,
                        qty=quantity,
                        side="sell",
                        type="market",
                        time_in_force="day"
                    )
                    
                    # Save order details
                    order_details = {
                        "symbol": symbol,
                        "order_id": order.id,
                        "quantity": quantity,
                        "price": float(position.current_price),
                        "decision": decision,
                        "confidence": confidence,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "reason": reason
                    }
                    
                    self.save_order_details(order_details)
                    
                    return {
                        "symbol": symbol,
                        "decision": decision,
                        "success": True,
                        "message": f"Sold {quantity} shares",
                        "order_id": order.id,
                        "reason": reason,
                        "queued": False
                    }
                    
                except Exception as e:
                    logger.error(f"Error selling {symbol}: {e}")
                    return {
                        "symbol": symbol,
                        "decision": decision,
                        "success": False,
                        "message": f"No position or error selling: {e}",
                        "reason": reason,
                        "queued": False
                    }
            
            else:  # HOLD or other decision
                logger.info(f"No action needed for {symbol} with decision: {decision}")
                return {
                    "symbol": symbol,
                    "decision": decision,
                    "success": True,
                    "message": "No action needed",
                    "reason": reason,
                    "queued": False
                }
        
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")
            return {
                "symbol": symbol,
                "decision": decision,
                "success": False,
                "message": f"Error: {e}",
                "reason": reason,
                "queued": False
            }
    
    def wait_for_order_fill(self, order_id, timeout=60):
        """Wait for an order to be filled, with timeout"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                order = alpaca.get_order(order_id)
                if order.status == "filled":
                    return order
                elif order.status == "rejected" or order.status == "canceled":
                    logger.warning(f"Order {order_id} was {order.status}")
                    return order
                    
                # Wait a bit before checking again
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                return None
                
        logger.warning(f"Timeout waiting for order {order_id} to fill")
        return None
    
    def save_order_details(self, order_details):
        """Save order details to file for record keeping"""
        try:
            # Ensure directory exists
            Path("data/orders").mkdir(exist_ok=True)
            
            # Create filename with timestamp and symbol
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            symbol = order_details["symbol"]
            filename = f"data/orders/{timestamp}_{symbol}_{order_details['decision']}.json"
            
            # Save to file
            with open(filename, "w") as f:
                json.dump(order_details, f, indent=2)
                
            logger.info(f"Saved order details to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving order details: {e}")
    
    def run_trading_cycle(self):
        """Run a complete trading cycle"""
        logger.info("Starting trading cycle")
        
        results = []
        
        try:
            # First, process any queued trades if the market is open
            if QUEUE_AVAILABLE and self.is_market_open():
                logger.info("Market is open, processing queued trades first")
                try:
                    from trade_queue import process_queue
                    queue_results = process_queue()
                    if queue_results:
                        logger.info(f"Processed {len(queue_results)} queued trades")
                except Exception as e:
                    logger.error(f"Error processing trade queue: {e}")
            
            # Get Alpaca account
            logger.info("Connecting to Alpaca account")
            account = alpaca.get_account()
            logger.info(f"Connected to Alpaca account: {account.id}")
            logger.info(f"Cash balance: ${float(account.cash):.2f}")
            logger.info(f"Portfolio value: ${float(account.portfolio_value):.2f}")
            
            # Process news data first (this also saves state)
            self.process_news_data()
            
            # Calculate opening ranges if not done yet
            for symbol in SYMBOLS_TO_TRACK:
                if symbol not in self.orb_ranges:
                    self.calculate_opening_range(symbol)
            
            # Process each symbol
            for symbol in SYMBOLS_TO_TRACK:
                try:
                    logger.info(f"Processing symbol: {symbol}")
                    
                    # Get combined signal
                    decision, confidence, reason_data = self.get_combined_signal(symbol)
                    
                    logger.info(f"Decision for {symbol}: {decision} (confidence: {confidence:.2f})")
                    logger.info(f"Reason: {reason_data['reason']}")
                    
                    # Execute or queue trade
                    trade_result = self.execute_trade(symbol, decision, confidence, account, reason_data)
                    
                    # Record result
                    result = {
                        "symbol": symbol,
                        "decision": decision,
                        "confidence": confidence,
                        "reason": reason_data["reason"],
                        "trade_executed": trade_result["success"],
                        "message": trade_result["message"],
                        "queued": trade_result.get("queued", False),
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"Error processing symbol {symbol}: {e}")
                    continue
            
            # Save final results
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Get updated account info
                account = alpaca.get_account()
                portfolio_value = {
                    'cash': float(account.cash),
                    'portfolio_value': float(account.portfolio_value),
                    'positions_value': float(account.portfolio_value) - float(account.cash)
                }
                
                with open(f"data/trading_results_{timestamp}.json", "w") as f:
                    json.dump({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "portfolio_value": portfolio_value,
                        "results": results
                    }, f, indent=2)
                
                logger.info("Results saved to file")
            except Exception as e:
                logger.error(f"Error saving results: {e}")
            
            # Print summary
            logger.info("\nTRADING RESULTS SUMMARY:")
            logger.info(f"Processed {len(SYMBOLS_TO_TRACK)} symbols")
            logger.info(f"Made {len(results)} trading decisions")
            logger.info(f"Portfolio value: ${float(account.portfolio_value):.2f}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            return results

def main():
    """Main function with overall timeout"""
    logger.info("Starting ORB News Trader Bot")
    
    try:
        # Set overall timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(300)  # 5 minute global timeout
        
        # Initialize and run the bot
        bot = ORBNewsTrader()
        results = bot.run_trading_cycle()
        
        # Clear timeout
        signal.alarm(0)
        
        logger.info("ORB News Trader Bot completed successfully")
        return results
        
    except TimeoutError:
        logger.error("Bot execution timed out after 5 minutes")
    except Exception as e:
        logger.error(f"Unhandled error in bot: {e}")
    finally:
        # Always reset the alarm
        signal.alarm(0)

if __name__ == "__main__":
    main()