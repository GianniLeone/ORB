# trade_queue.py
# Handles queueing and processing of trades

import os
import json
import logging
import datetime
from pathlib import Path
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trade_queue.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('trade_queue')

# Load environment variables
load_dotenv()

# Alpaca API credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

# Initialize Alpaca API
alpaca = tradeapi.REST(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_PAPER_URL,
    api_version='v2'
)

# Configuration
QUEUE_FILE = "data/trade_queue.json"
TRADE_HISTORY_FILE = "data/trade_history.json"
MAX_POSITION_PCT = 0.1  # Maximum 10% of portfolio in one position

class TradeQueue:
    """Handles trade queueing and execution"""
    
    def __init__(self):
        """Initialize the trade queue"""
        # Ensure data directory exists
        Path("data").mkdir(exist_ok=True)
        self.load_queue()
        self.load_history()
    
    def load_queue(self):
        """Load the trade queue from file"""
        queue_file = Path(QUEUE_FILE)
        if queue_file.exists():
            try:
                with open(queue_file, "r") as f:
                    self.queue = json.load(f)
                logger.info(f"Loaded {len(self.queue)} queued trades")
            except Exception as e:
                logger.error(f"Error loading trade queue: {e}")
                self.queue = []
        else:
            self.queue = []
    
    def save_queue(self):
        """Save the trade queue to file"""
        try:
            with open(QUEUE_FILE, "w") as f:
                json.dump(self.queue, f, indent=2)
            logger.info(f"Saved {len(self.queue)} queued trades")
        except Exception as e:
            logger.error(f"Error saving trade queue: {e}")
    
    def load_history(self):
        """Load trade history from file"""
        history_file = Path(TRADE_HISTORY_FILE)
        if history_file.exists():
            try:
                with open(history_file, "r") as f:
                    self.history = json.load(f)
                logger.info(f"Loaded trade history with {len(self.history)} records")
            except Exception as e:
                logger.error(f"Error loading trade history: {e}")
                self.history = []
        else:
            self.history = []
    
    def save_history(self):
        """Save trade history to file"""
        try:
            with open(TRADE_HISTORY_FILE, "w") as f:
                json.dump(self.history, f, indent=2)
            logger.info(f"Saved trade history with {len(self.history)} records")
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")
    
    def add_to_queue(self, symbol, decision, sentiment, news_title=None):
        """Add a trade to the queue"""
        # Check if there's already a queued trade for this symbol
        for i, trade in enumerate(self.queue):
            if trade["symbol"] == symbol:
                logger.info(f"Updating existing queued trade for {symbol} from {trade['decision']} to {decision}")
                # Update the existing trade with new decision
                self.queue[i].update({
                    "decision": decision,
                    "sentiment": sentiment,
                    "updated_at": datetime.datetime.now().isoformat(),
                    "news_title": news_title
                })
                self.save_queue()
                return True
        
        # Add new trade to queue
        self.queue.append({
            "symbol": symbol,
            "decision": decision,
            "sentiment": sentiment,
            "news_title": news_title,
            "queued_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        })
        
        logger.info(f"Added {decision} for {symbol} to queue")
        self.save_queue()
        return True
    
    def process_queue(self):
        """Process all queued trades"""
        if not self.queue:
            logger.info("No queued trades to process")
            return []
        
        # Check if market is open
        try:
            clock = alpaca.get_clock()
            if not clock.is_open:
                logger.info("Market is closed, cannot process queue")
                return []
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return []
        
        # Get account information
        try:
            account = alpaca.get_account()
            portfolio_value = float(account.portfolio_value)
            cash = float(account.cash)
            logger.info(f"Account value: ${portfolio_value:.2f}, Cash: ${cash:.2f}")
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return []
        
        # Process each trade in the queue
        processed = []
        results = []
        
        for trade in self.queue:
            symbol = trade["symbol"]
            decision = trade["decision"]
            sentiment = trade.get("sentiment", "Neutral")
            news_title = trade.get("news_title", "Unknown news source")
            
            result = {
                "symbol": symbol,
                "decision": decision,
                "sentiment": sentiment,
                "news_title": news_title,
                "success": False,
                "message": "",
                "order_id": None
            }
            
            try:
                if decision == "BUY":
                    # Calculate position size (max 10% of portfolio)
                    position_size = portfolio_value * MAX_POSITION_PCT
                    
                    # Adjust based on sentiment strength
                    sentiment_factor = 0.7  # Default
                    if sentiment == "Bullish":
                        sentiment_factor = 0.9
                    elif sentiment == "Neutral":
                        sentiment_factor = 0.5
                    
                    position_size *= sentiment_factor
                    
                    # Ensure we don't exceed available cash
                    position_size = min(position_size, cash * 0.95)
                    
                    # Get current price
                    positions = alpaca.list_positions()
                    current_positions = {p.symbol: p for p in positions}
                    
                    # Check if we already have this position
                    if symbol in current_positions:
                        existing_position = current_positions[symbol]
                        logger.info(f"Already have position in {symbol}: {existing_position.qty} shares at ${float(existing_position.avg_entry_price):.2f}")
                        # We could add to the position here if desired
                        result["success"] = False
                        result["message"] = f"Already have position in {symbol}"
                        results.append(result)
                        processed.append(trade)
                        continue
                    
                    # Get latest price quote
                    try:
                        quote = alpaca.get_latest_quote(symbol)
                        price = float(quote.ask_price)  # Use ask price for buying
                    except:
                        # Fallback to last trade price
                        try:
                            bar = alpaca.get_latest_bar(symbol)
                            price = float(bar.c)
                        except Exception as e:
                            logger.error(f"Error getting price for {symbol}: {e}")
                            result["message"] = f"Error getting price: {e}"
                            results.append(result)
                            continue
                    
                    # Calculate quantity
                    quantity = int(position_size / price)
                    if quantity < 1:
                        logger.info(f"Position size too small for {symbol}: ${position_size:.2f} / ${price:.2f} = {quantity}")
                        result["message"] = "Position size too small"
                        results.append(result)
                        processed.append(trade)
                        continue
                    
                    # Submit market order
                    try:
                        logger.info(f"Buying {quantity} shares of {symbol} at ~${price:.2f}")
                        order = alpaca.submit_order(
                            symbol=symbol,
                            qty=quantity,
                            side="buy",
                            type="market",
                            time_in_force="day"
                        )
                        
                        # Update result
                        result["success"] = True
                        result["message"] = f"Bought {quantity} shares at ~${price:.2f}"
                        result["order_id"] = order.id
                        
                        # Add to history
                        self.history.append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "symbol": symbol,
                            "action": "BUY",
                            "quantity": quantity,
                            "price": price,
                            "order_id": order.id,
                            "sentiment": sentiment,
                            "news_title": news_title
                        })
                        
                        # Mark as processed
                        processed.append(trade)
                        
                    except Exception as e:
                        logger.error(f"Error submitting buy order for {symbol}: {e}")
                        result["message"] = f"Error submitting order: {e}"
                
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
                        
                        # Update result
                        result["success"] = True
                        result["message"] = f"Sold {quantity} shares"
                        result["order_id"] = order.id
                        
                        # Add to history
                        self.history.append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "symbol": symbol,
                            "action": "SELL",
                            "quantity": quantity,
                            "price": float(position.current_price),
                            "order_id": order.id,
                            "sentiment": sentiment,
                            "news_title": news_title
                        })
                        
                        # Mark as processed
                        processed.append(trade)
                        
                    except Exception as e:
                        logger.error(f"Error selling {symbol}: {e}")
                        result["message"] = f"No position or error selling: {e}"
                
                else:  # HOLD or other decision
                    logger.info(f"No action needed for {symbol} with decision: {decision}")
                    result["success"] = True
                    result["message"] = "No action needed"
                    processed.append(trade)
            
            except Exception as e:
                logger.error(f"Error processing queued trade for {symbol}: {e}")
                result["message"] = f"Error: {e}"
            
            # Add result to results list
            results.append(result)
        
        # Remove processed trades from queue
        for trade in processed:
            if trade in self.queue:
                self.queue.remove(trade)
        
        # Save updated queue and history
        self.save_queue()
        self.save_history()
        
        logger.info(f"Processed {len(processed)} queued trades, {len(self.queue)} remaining")
        return results

def queue_trade(symbol, decision, sentiment="Neutral", news_title=None):
    """Convenience function to queue a trade"""
    queue = TradeQueue()
    return queue.add_to_queue(symbol, decision, sentiment, news_title)

def process_queue():
    """Convenience function to process the queue"""
    queue = TradeQueue()
    return queue.process_queue()

if __name__ == "__main__":
    # If run directly, process the queue
    logger.info("Processing trade queue")
    results = process_queue()
    logger.info(f"Processed {len(results)} trades")
    
    # Print results
    for result in results:
        status = "SUCCESS" if result["success"] else "FAILED"
        logger.info(f"{status}: {result['decision']} {result['symbol']} - {result['message']}")