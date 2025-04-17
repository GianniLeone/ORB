# simple_news_trader.py
# A simplified trading bot that reads news and makes trading decisions

import os
import time
import json
import datetime
import logging
import requests
import yfinance as yf
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import alpaca_trade_api as tradeapi  # Add Alpaca trade API

# Load environment variables
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Alpaca API credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('trading_bot')

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

# Configuration
SYMBOLS_TO_TRACK = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]
INITIAL_CAPITAL = 10000
MAX_POSITION_PCT = 0.1  # Maximum 10% of portfolio in one position

class Portfolio:
    """Portfolio management using Alpaca Trading API"""
    
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.trade_history = []
        
        # Load trade history if exists
        trade_history_file = Path("data/trade_history.json")
        if trade_history_file.exists():
            try:
                with open(trade_history_file, "r") as f:
                    self.trade_history = json.load(f)
                logger.info(f"Loaded trade history with {len(self.trade_history)} records")
            except Exception as e:
                logger.error(f"Error loading trade history: {e}")
        
        # Get account information from Alpaca
        try:
            self.account = alpaca.get_account()
            logger.info(f"Connected to Alpaca account: {self.account.id}")
            logger.info(f"Cash balance: ${float(self.account.cash):.2f}")
            logger.info(f"Portfolio value: ${float(self.account.portfolio_value):.2f}")
        except Exception as e:
            logger.error(f"Error connecting to Alpaca: {e}")
            raise
    
    def get_current_value(self):
        """Get current portfolio value from Alpaca"""
        try:
            # Refresh account info
            self.account = alpaca.get_account()
            
            # Get positions
            positions = alpaca.list_positions()
            positions_value = sum(float(position.market_value) for position in positions)
            positions_current = {}
            
            # Format positions data
            for position in positions:
                symbol = position.symbol
                quantity = int(position.qty)
                avg_price = float(position.avg_entry_price)
                current_price = float(position.current_price)
                current_value = float(position.market_value)
                cost_basis = quantity * avg_price
                
                # Calculate profit/loss
                pl_dollars = current_value - cost_basis
                pl_percent = (pl_dollars / cost_basis) * 100 if cost_basis > 0 else 0
                
                positions_current[symbol] = {
                    'quantity': quantity,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'current_value': current_value,
                    'profit_loss_dollars': pl_dollars,
                    'profit_loss_percent': pl_percent
                }
            
            # Calculate total value and performance
            cash = float(self.account.cash)
            total_value = float(self.account.portfolio_value)
            total_pl_dollars = total_value - self.initial_capital
            total_pl_percent = (total_pl_dollars / self.initial_capital) * 100
            
            return {
                'cash': cash,
                'positions_value': positions_value,
                'total_value': total_value,
                'initial_capital': self.initial_capital,
                'profit_loss_dollars': total_pl_dollars,
                'profit_loss_percent': total_pl_percent,
                'positions': positions_current
            }
        except Exception as e:
            logger.error(f"Error getting portfolio value: {e}")
            # Return a default structure with zeros
            return {
                'cash': 0,
                'positions_value': 0,
                'total_value': 0,
                'initial_capital': self.initial_capital,
                'profit_loss_dollars': 0,
                'profit_loss_percent': 0,
                'positions': {}
            }
    
    def add_position(self, symbol, quantity, price=None):
        """Buy shares of a stock using Alpaca API"""
        try:
            # Submit market order
            order = alpaca.submit_order(
                symbol=symbol,
                qty=quantity,
                side='buy',
                type='market',
                time_in_force='day'
            )
            
            logger.info(f"Submitted buy order for {quantity} shares of {symbol}")
            
            # Wait for order to fill
            filled_order = self._wait_for_order_fill(order.id)
            
            if filled_order and filled_order.status == 'filled':
                # Get fill price
                fill_price = float(filled_order.filled_avg_price)
                fill_qty = int(filled_order.filled_qty)
                
                # Record the trade
                trade = {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'action': 'BUY',
                    'symbol': symbol,
                    'quantity': fill_qty,
                    'price': fill_price,
                    'cost': fill_price * fill_qty,
                    'order_id': order.id
                }
                self.trade_history.append(trade)
                
                logger.info(f"Bought {fill_qty} shares of {symbol} at ${fill_price:.2f}")
                self._save_trade_history()
                return True
            else:
                logger.error(f"Order for {symbol} failed or didn't fill")
                return False
            
        except Exception as e:
            logger.error(f"Error buying {symbol}: {e}")
            return False
    
    def close_position(self, symbol, quantity=None):
        """Sell shares of a stock using Alpaca API"""
        try:
            # Get current position
            try:
                position = alpaca.get_position(symbol)
                current_qty = int(position.qty)
            except:
                logger.warning(f"No position found for {symbol}")
                return False
            
            # Determine quantity to sell
            if quantity is None or quantity > current_qty:
                quantity = current_qty  # Sell all
            
            # Submit market order
            order = alpaca.submit_order(
                symbol=symbol,
                qty=quantity,
                side='sell',
                type='market',
                time_in_force='day'
            )
            
            logger.info(f"Submitted sell order for {quantity} shares of {symbol}")
            
            # Wait for order to fill
            filled_order = self._wait_for_order_fill(order.id)
            
            if filled_order and filled_order.status == 'filled':
                # Get fill price
                fill_price = float(filled_order.filled_avg_price)
                fill_qty = int(filled_order.filled_qty)
                
                # Record the trade
                trade = {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'action': 'SELL',
                    'symbol': symbol,
                    'quantity': fill_qty,
                    'price': fill_price,
                    'proceeds': fill_price * fill_qty,
                    'order_id': order.id
                }
                self.trade_history.append(trade)
                
                logger.info(f"Sold {fill_qty} shares of {symbol} at ${fill_price:.2f}")
                self._save_trade_history()
                return True
            else:
                logger.error(f"Order for {symbol} failed or didn't fill")
                return False
            
        except Exception as e:
            logger.error(f"Error selling {symbol}: {e}")
            return False
    
    def _wait_for_order_fill(self, order_id, timeout=30):
        """Wait for an order to fill, with timeout in seconds"""
        start_time = time.time()
    
        logger.info(f"Waiting for order {order_id} to fill (timeout: {timeout}s)")
    
        while time.time() - start_time < timeout:
            try:
                order = alpaca.get_order(order_id)
                
                if order.status == 'filled':
                    logger.info(f"Order {order_id} filled at price ${float(order.filled_avg_price):.2f}")
                    return order
                
                if order.status == 'rejected' or order.status == 'canceled':
                    logger.warning(f"Order {order_id} {order.status}: {order.reject_reason}")
                    return None
                
                # Log the status
                logger.info(f"Order status: {order.status} - waiting...")
                
                # Wait before checking again
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                return None
        
        # Timeout reached
        logger.warning(f"Timeout waiting for order {order_id} to fill")
        return None
    
    def _save_trade_history(self):
        """Save trade history to file"""
        try:
            with open("data/trade_history.json", 'w') as f:
                json.dump(self.trade_history, f, indent=2)
                
            logger.debug("Trade history saved")
            return True
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")
            return False

def fetch_news_articles(symbols, max_results=10):
    """Fetch news articles about the given symbols"""
    # Create a simple query string
    query = " OR ".join(symbols[:5])  # Use top 5 symbols
    url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize={max_results}&apiKey={NEWS_API_KEY}"

    try:
        logger.info(f"Fetching news with query: {query}")
        response = requests.get(url, timeout=30)  # Add 30-second timeout
        
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
                    "content": content,
                    "url": article.get("url", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "published_at": article.get("publishedAt", "")
                })
                
            return processed_articles
        else:
            logger.error(f"Failed to fetch news: {response.status_code} - {response.text}")
            return []
            
    except requests.exceptions.Timeout:
        logger.error("News API request timed out")
        return []
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return []

def analyze_article(text):
    """Analyze a news article using GPT to extract sentiment and companies"""
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
        # Add timeout for API call
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a market-savvy financial assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            timeout=30  # Add 30-second timeout
        )
        content = response.choices[0].message.content
        logger.info(f"GPT response received, parsing result")
        
        # Extract JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error(f"Invalid JSON format in GPT response: {content}")
            return {"sentiment": "Neutral", "related_companies": []}
            
        json_blob = content[start:end]
        parsed = json.loads(json_blob)
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e} in content: {content}")
        return {"sentiment": "Neutral", "related_companies": []}
    except Exception as e:
        logger.error(f"GPT error: {e}")
        return {"sentiment": "Neutral", "related_companies": []}

def match_company_to_symbol(company_name, symbols_to_check):
    """Simple matching of company name to stock symbol"""
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
        "nvidia": "NVDA"
    }
    
    # Try direct lookup
    company_lower = company_name.lower()
    if company_lower in company_aliases:
        symbol = company_aliases[company_lower]
        if symbol in symbols_to_check:
            return symbol
    
    # No match found
    return None

def make_trading_decision(symbol, sentiment, historical_data=None):
    """Make a simple trading decision based on sentiment"""
    # Get recent price changes if not provided
    if historical_data is None:
        try:
            logger.info(f"Getting historical data for {symbol}")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", timeout=20)  # Add timeout
            if not hist.empty and len(hist) > 1:
                start_price = hist['Close'].iloc[0]
                end_price = hist['Close'].iloc[-1]
                change_5d = ((end_price - start_price) / start_price) * 100
                logger.info(f"{symbol} 5-day change: {change_5d:.2f}%")
            else:
                logger.warning(f"No historical data found for {symbol}")
                change_5d = 0
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            change_5d = 0
    else:
        change_5d = historical_data.get("5d", 0)
    
    # Simple decision logic
    logger.info(f"Making trading decision for {symbol} with sentiment: {sentiment}")
    if sentiment == "Bullish":
        # Buy on bullish sentiment if not already up significantly
        if change_5d < 5:
            logger.info(f"Decision: BUY {symbol} (Bullish sentiment, 5-day change < 5%)")
            return "BUY"
        else:
            # Already up significantly, wait for pullback
            logger.info(f"Decision: HOLD {symbol} (Bullish sentiment, but 5-day change > 5%)")
            return "HOLD"
    
    elif sentiment == "Bearish":
        # Sell on bearish sentiment
        logger.info(f"Decision: SELL {symbol} (Bearish sentiment)")
        return "SELL"
    
    else:  # Neutral sentiment
        logger.info(f"Decision: HOLD {symbol} (Neutral sentiment)")
        return "HOLD"

def calculate_position_size(portfolio, symbol, sentiment_strength=0.7):
    """Calculate simple position size based on portfolio value"""
    # Get portfolio value from Alpaca account
    portfolio_value = float(portfolio.account.portfolio_value)
    cash = float(portfolio.account.cash)
    
    # Calculate base position size (% of portfolio)
    base_size = portfolio_value * MAX_POSITION_PCT
    
    # Adjust based on sentiment strength (0.5 to 1.0)
    position_size = base_size * sentiment_strength
    
    # Ensure minimum position size if trading
    min_position = min(1000, portfolio_value * 0.02)  # Min $1000 or 2% of portfolio
    if position_size < min_position:
        position_size = min_position
    
    # Cap at available cash (with 5% buffer)
    position_size = min(position_size, cash * 0.95)
    
    return position_size

def process_articles(articles, portfolio):
    """Process articles and make trading decisions"""
    results = []
    
    for article in articles:
        # Combine title and content
        full_text = f"{article.get('title', '')} {article.get('content', '')}"
        logger.info(f"Processing: {article.get('title', 'Untitled article')[:100]}...")
        
        # Analyze with GPT
        analysis = analyze_article(full_text)
        sentiment = analysis.get("sentiment", "Neutral")
        related_companies = analysis.get("related_companies", [])
        
        logger.info(f"Sentiment: {sentiment}")
        logger.info(f"Related companies: {related_companies}")
        
        # Match to symbols
        for company in related_companies:
            symbol = match_company_to_symbol(company, SYMBOLS_TO_TRACK)
            
            if symbol:
                logger.info(f"Matched company '{company}' to symbol {symbol}")
                
                # Make trading decision
                decision = make_trading_decision(symbol, sentiment)
                
                # Execute trade
                trade_executed = False
                
                if decision == "BUY":
                    # Calculate position size
                    amount = calculate_position_size(portfolio, symbol)
                    
                    if amount > 0:
                        # Get current price
                        try:
                            ticker = yf.Ticker(symbol)
                            data = ticker.history(period="1d")
                            if not data.empty:
                                price = data['Close'].iloc[-1]
                                quantity = max(1, int(amount / price))
                                trade_executed = portfolio.add_position(symbol, quantity, price)
                        except Exception as e:
                            logger.error(f"Error getting price for {symbol}: {e}")
                
                elif decision == "SELL":
                    # Check if we have a position in this symbol
                    try:
                        # Try to get position through Alpaca API
                        position = alpaca.get_position(symbol)
                        trade_executed = portfolio.close_position(symbol)
                    except Exception as e:
                        logger.info(f"No position in {symbol} to sell: {e}")
                
                # Record result
                results.append({
                    "article": article.get('title', 'Untitled'),
                    "sentiment": sentiment,
                    "company": company,
                    "symbol": symbol,
                    "decision": decision,
                    "trade_executed": trade_executed
                })
    
    return results

def run_trading_cycle():
    """Run a complete trading cycle"""
    logger.info("Starting trading cycle")
    
    # Initialize portfolio
    portfolio = Portfolio(initial_capital=INITIAL_CAPITAL)
    
    # Fetch news
    articles = fetch_news_articles(SYMBOLS_TO_TRACK, max_results=10)
    logger.info(f"Found {len(articles)} articles")
    
    if not articles:
        logger.warning("No articles found to process")
        return []
    
    # Process articles and make trades
    results = process_articles(articles, portfolio)
    
    # Print summary
    account_info = alpaca.get_account()
    logger.info("\nTRADING RESULTS SUMMARY:")
    logger.info(f"Portfolio value: ${float(account_info.portfolio_value):.2f}")
    logger.info(f"Cash: ${float(account_info.cash):.2f}")
    logger.info(f"Positions value: ${float(account_info.portfolio_value) - float(account_info.cash):.2f}")
    
    # Calculate P/L
    profit_loss = float(account_info.portfolio_value) - INITIAL_CAPITAL
    profit_loss_percent = (profit_loss / INITIAL_CAPITAL) * 100
    logger.info(f"P/L: ${profit_loss:.2f} ({profit_loss_percent:.2f}%)")
    
    # Save results
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        portfolio_value = {
            'cash': float(account_info.cash),
            'portfolio_value': float(account_info.portfolio_value),
            'positions_value': float(account_info.portfolio_value) - float(account_info.cash),
            'profit_loss_dollars': profit_loss,
            'profit_loss_percent': profit_loss_percent
        }
        
        with open(f"data/trading_results_{timestamp}.json", "w") as f:
            json.dump({
                "timestamp": datetime.datetime.now().isoformat(),
                "portfolio_value": portfolio_value,
                "results": results
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving results: {e}")
    
    return results

def main():
    """Main function to run the trading bot"""
    logger.info("Starting simplified news trading bot")
    
    try:
        # Run a single trading cycle
        results = run_trading_cycle()
        logger.info(f"Processed {len(results)} articles, trading cycle complete")
        
    except Exception as e:
        logger.error(f"Error in trading bot: {e}")
        raise

if __name__ == "__main__":
    main()