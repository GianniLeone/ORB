# trade_queue_processor.py
# Enhanced trade queue processor with news sentiment verification

import os
import json
import logging
import datetime
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import alpaca_trade_api as tradeapi
import requests
import yfinance as yf

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("queue_processor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('queue_processor')

# Load environment variables
load_dotenv()

# API keys
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Alpaca API credentials
APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

# Initialize API clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)

alpaca = tradeapi.REST(
    APCA_API_KEY_ID,
    APCA_API_SECRET_KEY,
    ALPACA_PAPER_URL,
    api_version='v2'
)

# Configuration
MAX_POSITION_PCT = 0.1  # Maximum 10% of portfolio in one position
QUEUE_FILE = "data/trade_queue.json"
TRADE_HISTORY_FILE = "data/trade_history.json"

def is_market_open():
    """Check if the market is currently open"""
    try:
        clock = alpaca.get_clock()
        return clock.is_open
    except Exception as e:
        logger.error(f"Error checking market hours: {e}")
        return False

def fetch_news_for_symbol(symbol, max_results=3):
    """Fetch the latest news for a specific symbol"""
    logger.info(f"Fetching latest news for {symbol}")
    
    url = f"https://newsapi.org/v2/everything?q={symbol}&language=en&sortBy=publishedAt&pageSize={max_results}&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            logger.info(f"Received {len(articles)} articles for {symbol}")
            
            # Filter out non-English articles
            processed_articles = []
            for article in articles:
                title = article.get("title", "")
                
                # Skip articles with non-ASCII characters in title
                try:
                    title.encode('ascii', 'strict')
                    content = article.get("content", "") or article.get("description", "")
                    
                    processed_articles.append({
                        "title": title,
                        "content": content[:500],
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "published_at": article.get("publishedAt", "")
                    })
                except UnicodeEncodeError:
                    # Skip non-English articles
                    continue
            
            return processed_articles
        else:
            logger.error(f"Error fetching news for {symbol}: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        return []

def analyze_sentiment(article_text):
    """Analyze sentiment of an article using OpenAI"""
    # Truncate text to ensure it's not too long
    max_length = 1000
    if len(article_text) > max_length:
        article_text = article_text[:max_length] + "..."
    
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
{article_text}
"""

    try:
        logger.info("Analyzing sentiment with OpenAI")
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a market-savvy financial assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        logger.info("Sentiment analysis completed")
        
        # Extract JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("Invalid JSON format in GPT response")
            return {"sentiment": "Neutral", "related_companies": []}
            
        json_blob = content[start:end]
        parsed = json.loads(json_blob)
        return parsed
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        return {"sentiment": "Neutral", "related_companies": []}

def is_company_related_to_symbol(companies, symbol):
    """Check if any company in the list is related to the symbol"""
    company_aliases = {
        "AAPL": ["apple", "apple inc"],
        "MSFT": ["microsoft", "microsoft corporation"],
        "GOOGL": ["google", "alphabet", "alphabet inc"],
        "AMZN": ["amazon", "amazon.com"],
        "META": ["meta", "facebook", "meta platforms"],
        "TSLA": ["tesla", "tesla motors", "tesla inc"],
        "NVDA": ["nvidia", "nvidia corporation"],
        "AMD": ["amd", "advanced micro devices"],
        "INTC": ["intel", "intel corporation"],
        "IBM": ["ibm", "international business machines"]
    }
    
    if symbol in company_aliases:
        aliases = company_aliases[symbol]
        for company in companies:
            if company.lower() in aliases:
                return True
    
    return False

def verify_sentiment_for_trade(symbol, original_decision):
    """Verify if latest news sentiment still supports the original trading decision"""
    logger.info(f"Verifying sentiment for {symbol} ({original_decision})")
    
    # Fetch latest news
    articles = fetch_news_for_symbol(symbol)
    
    if not articles:
        logger.info(f"No recent news found for {symbol}, proceeding with original decision")
        return True, "No recent news found"
    
    # Analyze sentiment for each article
    sentiments = []
    for article in articles:
        full_text = f"{article['title']} {article['content']}"
        analysis = analyze_sentiment(full_text)
        sentiment = analysis.get("sentiment", "Neutral")
        companies = analysis.get("related_companies", [])
        
        # Only consider sentiment if article is related to this symbol
        if is_company_related_to_symbol(companies, symbol):
            sentiments.append(sentiment)
            logger.info(f"Related article found: '{article['title'][:50]}...' - Sentiment: {sentiment}")
    
    if not sentiments:
        logger.info(f"No relevant articles found for {symbol}, proceeding with original decision")
        return True, "No relevant articles found"
    
    # Map sentiments to decision types
    sentiment_to_decision = {
        "Bullish": "BUY",
        "Bearish": "SELL",
        "Neutral": "HOLD"
    }
    
    # Count sentiment types
    bullish_count = sentiments.count("Bullish")
    bearish_count = sentiments.count("Bearish")
    neutral_count = sentiments.count("Neutral")
    
    # Determine predominant sentiment
    if bullish_count > bearish_count and bullish_count > neutral_count:
        current_sentiment = "Bullish"
    elif bearish_count > bullish_count and bearish_count > neutral_count:
        current_sentiment = "Bearish"
    else:
        current_sentiment = "Neutral"
    
    logger.info(f"Current sentiment for {symbol}: {current_sentiment}")
    
    # Convert sentiment to decision
    current_decision = sentiment_to_decision.get(current_sentiment, "HOLD")
    
    # Special case: if original decision is HOLD and current is not strongly opposed, proceed
    if original_decision == "HOLD" and current_decision != "SELL":
        return True, f"Original HOLD compatible with current sentiment {current_sentiment}"
    
    # Special case: if original decision is BUY and current is HOLD, still proceed
    if original_decision == "BUY" and current_decision == "HOLD":
        return True, "Neutral sentiment does not contradict BUY decision"
    
    # If decisions match, proceed with trade
    if original_decision == current_decision:
        return True, f"Current sentiment ({current_sentiment}) confirms {original_decision} decision"
    
    # If new sentiment contradicts original decision, don't proceed
    return False, f"Current sentiment ({current_sentiment}) contradicts {original_decision} decision"

def load_queue():
    """Load the trade queue from file"""
    queue_file = Path(QUEUE_FILE)
    if queue_file.exists():
        try:
            with open(queue_file, "r") as f:
                queue = json.load(f)
            logger.info(f"Loaded {len(queue)} queued trades")
            return queue
        except Exception as e:
            logger.error(f"Error loading trade queue: {e}")
            return []
    else:
        logger.info("No trade queue file found")
        return []

def save_queue(queue):
    """Save the trade queue to file"""
    try:
        with open(QUEUE_FILE, "w") as f:
            json.dump(queue, f, indent=2)
        logger.info(f"Saved {len(queue)} queued trades")
    except Exception as e:
        logger.error(f"Error saving trade queue: {e}")

def get_current_price(symbol):
    """Get current price for a symbol using Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        
        if data.empty:
            logger.warning(f"No price data for {symbol}")
            return None
        
        current_price = data['Close'].iloc[-1]
        return current_price
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        return None

def execute_trade(trade, account):
    """Execute a trade from the queue with news verification"""
    symbol = trade["symbol"]
    decision = trade["decision"]
    sentiment = trade.get("sentiment", "Neutral")
    news_title = trade.get("news_title", "")
    
    logger.info(f"Processing queued trade: {decision} {symbol} (Sentiment: {sentiment})")
    
    # Verify sentiment still supports the decision
    proceed, reason = verify_sentiment_for_trade(symbol, decision)
    
    if not proceed:
        logger.info(f"Skipping trade for {symbol}: {reason}")
        return {
            "symbol": symbol,
            "decision": decision,
            "executed": False,
            "message": f"Trade canceled: {reason}",
            "original_sentiment": sentiment,
            "original_news": news_title
        }
    
    logger.info(f"Proceeding with {decision} for {symbol}: {reason}")
    
    # Execute the trade based on decision
    try:
        if decision == "BUY":
            # Calculate position size
            portfolio_value = float(account.portfolio_value)
            cash = float(account.cash)
            
            # Base position size
            position_size = portfolio_value * MAX_POSITION_PCT
            
            # Adjust based on sentiment
            if sentiment == "Bullish":
                confidence = 0.9
            elif sentiment == "Neutral":
                confidence = 0.6
            else:
                confidence = 0.5
                
            position_size *= confidence
            
            # Cap at available cash (with 5% buffer)
            position_size = min(position_size, cash * 0.95)
            
            # Get current price
            price = get_current_price(symbol)
            if not price:
                return {
                    "symbol": symbol,
                    "decision": decision,
                    "executed": False,
                    "message": "Could not get current price",
                    "original_sentiment": sentiment,
                    "original_news": news_title
                }
            
            # Calculate quantity
            quantity = int(position_size / price)
            if quantity < 1:
                logger.info(f"Position size too small for {symbol}: ${position_size:.2f} / ${price:.2f} = {quantity}")
                return {
                    "symbol": symbol,
                    "decision": decision,
                    "executed": False,
                    "message": "Position size too small",
                    "original_sentiment": sentiment,
                    "original_news": news_title
                }
            
            # Check if we already have this position
            try:
                positions = alpaca.list_positions()
                for position in positions:
                    if position.symbol == symbol:
                        logger.info(f"Already have position in {symbol}: {position.qty} shares")
                        return {
                            "symbol": symbol,
                            "decision": decision,
                            "executed": False,
                            "message": f"Already have position: {position.qty} shares",
                            "original_sentiment": sentiment,
                            "original_news": news_title
                        }
            except Exception as e:
                logger.warning(f"Error checking positions: {e}")
            
            # Submit market order
            logger.info(f"Buying {quantity} shares of {symbol} at ~${price:.2f}")
            order = alpaca.submit_order(
                symbol=symbol,
                qty=quantity,
                side="buy",
                type="market",
                time_in_force="day"
            )
            
            # Add stop loss and take profit orders
            stop_loss_price = price * 0.995  # 0.5% stop loss
            take_profit_price = price * 1.01  # 1% take profit
            
            try:
                # Wait for the main order to fill
                order_filled = False
                max_wait_time = 60  # seconds
                start_time = time.time()
                
                while not order_filled and (time.time() - start_time) < max_wait_time:
                    try:
                        order_status = alpaca.get_order(order.id)
                        
                        if order_status.status == "filled":
                            order_filled = True
                            logger.info(f"Order filled: {quantity} shares of {symbol}")
                            break
                            
                        elif order_status.status in ["rejected", "canceled"]:
                            logger.warning(f"Order was {order_status.status}: {symbol}")
                            break
                            
                        # Wait a bit before checking again
                        time.sleep(2)
                    except Exception as e:
                        logger.error(f"Error checking order status: {e}")
                        break
                
                # If order was filled, add stop loss and take profit orders
                if order_filled:
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
            except Exception as e:
                logger.error(f"Error setting stop loss/take profit for {symbol}: {e}")
            
            return {
                "symbol": symbol,
                "decision": decision,
                "executed": True,
                "message": f"Bought {quantity} shares at ~${price:.2f}",
                "order_id": order.id,
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
                "original_sentiment": sentiment,
                "original_news": news_title,
                "sentiment_verification": reason
            }
            
        elif decision == "SELL":
            # Check if we have a position
            try:
                position = alpaca.get_position(symbol)
                quantity = int(position.qty)
                
                # Submit market order to sell
                logger.info(f"Selling {quantity} shares of {symbol}")
                order = alpaca.submit_order(
                    symbol=symbol,
                    qty=quantity,
                    side="sell",
                    type="market",
                    time_in_force="day"
                )
                
                return {
                    "symbol": symbol,
                    "decision": decision,
                    "executed": True,
                    "message": f"Sold {quantity} shares",
                    "order_id": order.id,
                    "original_sentiment": sentiment,
                    "original_news": news_title,
                    "sentiment_verification": reason
                }
                
            except Exception as e:
                logger.error(f"Error selling {symbol}: {e}")
                return {
                    "symbol": symbol,
                    "decision": decision,
                    "executed": False,
                    "message": f"No position or error selling: {e}",
                    "original_sentiment": sentiment,
                    "original_news": news_title
                }
        
        else:  # HOLD
            logger.info(f"HOLD decision for {symbol}, no action needed")
            return {
                "symbol": symbol,
                "decision": decision,
                "executed": False,
                "message": "HOLD decision, no action taken",
                "original_sentiment": sentiment,
                "original_news": news_title
            }
    
    except Exception as e:
        logger.error(f"Error executing trade for {symbol}: {e}")
        return {
            "symbol": symbol,
            "decision": decision,
            "executed": False,
            "message": f"Error: {e}",
            "original_sentiment": sentiment,
            "original_news": news_title
        }

def process_queue():
    """Process the trade queue with news sentiment verification"""
    logger.info("Processing trade queue with news verification")
    
    # Check if market is open
    if not is_market_open():
        logger.info("Market is closed, cannot process queue")
        return []
    
    # Load the queue
    queue = load_queue()
    if not queue:
        logger.info("No queued trades to process")
        return []
    
    # Get account information
    try:
        account = alpaca.get_account()
        logger.info(f"Account value: ${float(account.portfolio_value):.2f}, Cash: ${float(account.cash):.2f}")
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        return []
    
    # Process each trade
    processed = []
    results = []
    
    for trade in queue:
        symbol = trade["symbol"]
        decision = trade["decision"]
        
        logger.info(f"Processing queued trade: {decision} {symbol}")
        
        result = execute_trade(trade, account)
        results.append(result)
        
        # Mark as processed
        processed.append(trade)
    
    # Remove processed trades from queue
    new_queue = [t for t in queue if t not in processed]
    save_queue(new_queue)
    
    # Save results to history
    save_trade_history(results)
    
    logger.info(f"Processed {len(processed)} queued trades, {len(new_queue)} remaining")
    return results

def save_trade_history(results):
    """Save trade execution results to history file"""
    try:
        # Load existing history
        history = []
        history_file = Path(TRADE_HISTORY_FILE)
        if history_file.exists():
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except:
                history = []
        
        # Add timestamp to results
        execution_record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "results": results
        }
        
        # Add to history
        history.append(execution_record)
        
        # Save updated history
        with open(TRADE_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
        
        logger.info(f"Saved execution results to trade history ({len(results)} trades)")
    except Exception as e:
        logger.error(f"Error saving trade history: {e}")

def main():
    """Main function to process the queue with news verification"""
    logger.info("Starting enhanced queue processor with news verification")
    
    # Process the queue
    results = process_queue()
    
    # Print summary
    logger.info("\nQUEUE PROCESSING SUMMARY:")
    logger.info(f"Processed {len(results)} queued trades")
    
    executed_count = sum(1 for r in results if r.get("executed", False))
    logger.info(f"Successfully executed {executed_count} trades")
    
    logger.info("Queue processing completed")
    return results

if __name__ == "__main__":
    main()