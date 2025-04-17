# Simplified News Trader Bot

A simplified news-based trading bot that uses GPT to analyze financial news articles and make trading decisions.

## Overview

This simplified trading bot:
1. Fetches financial news articles about specified stocks
2. Uses GPT to analyze sentiment and identify affected companies
3. Makes simple buy/sell decisions based on sentiment analysis
4. Tracks a portfolio with positions and performance

## Requirements

- Python 3.7+
- Required packages (install with `pip install -r requirements.txt`):
  - openai
  - requests
  - yfinance
  - python-dotenv
  - alpaca-trade-api

## Setup

1. Clone the repository:
```
git clone https://github.com/yourusername/news-trader-bot.git
cd news-trader-bot
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Create a `.env` file with your API keys:
```
NEWS_API_KEY=your_newsapi_key_here
OPENAI_API_KEY=your_openai_api_key_here
ALPACA_API_KEY=your_alpaca_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_here
ALPACA_PAPER_URL=https://paper-api.alpaca.markets
```

## Usage

### Running Once

To run the bot once:

```
python run_bot_simplified.py --once
```

### Running Continuously

To run the bot continuously (default: every 60 minutes):

```
python run_bot_simplified.py
```

### Test Mode

To run without executing actual trades:

```
python run_bot_simplified.py --test
```

### Custom Settings

```
python run_bot_simplified.py --interval 30 --script simple_news_trader.py
```

## Configuration

Edit `simple_news_trader.py` to modify:

- `SYMBOLS_TO_TRACK`: List of stock symbols to monitor
- `INITIAL_CAPITAL`: Starting capital for the portfolio
- `MAX_POSITION_PCT`: Maximum percentage of portfolio for a single position

## Project Structure

- `simple_news_trader.py`: Main trading logic and portfolio management
- `run_bot_simplified.py`: Runner script to execute the bot on a schedule
- `data/`: Directory for storing portfolio and results data
- `requirements.txt`: Required Python packages

## How It Works

1. The bot fetches recent financial news articles related to the tracked stocks
2. Each article is analyzed by GPT to determine sentiment (Bullish, Bearish, Neutral)
3. Companies mentioned in the articles are mapped to stock symbols
4. For each identified stock:
   - If sentiment is Bullish: Buy (unless the stock is already up significantly)
   - If sentiment is Bearish: Sell
   - If sentiment is Neutral: Hold
5. Trading orders are executed through Alpaca Trading API
6. The bot waits for orders to be filled and records results
7. Trading history is saved and portfolio performance is tracked

## Extending the Bot

This simplified version is designed to be easily extended:

1. Add more sophisticated trading strategies in `make_trading_decision()`
2. Enhance the company-to-symbol matching in `match_company_to_symbol()`
3. Implement more advanced position sizing in `calculate_position_size()`
4. Add technical indicators for better entry/exit points

## Logs and Monitoring

- Main log file: `trading_bot.log`
- Runner log file: `runner.log`
- Trading results: `data/trading_results_[timestamp].json`
- Trade history: `data/trade_history.json`
- Real-time portfolio data is stored in your Alpaca account

## Windows Server Deployment

1. Set up a scheduled task to run the bot:
   - Open Task Scheduler
   - Create a new task
   - Set the program/script to `python` or the path to your Python executable
   - Set the arguments to `run_bot_simplified.py`
   - Configure the schedule as desired

2. Alternatively, run as a background service using NSSM (Non-Sucking Service Manager)

## Disclaimer

This bot is for educational purposes only. Trading stocks based on automated systems involves significant risk. Use at your own risk and always consult with a financial advisor.