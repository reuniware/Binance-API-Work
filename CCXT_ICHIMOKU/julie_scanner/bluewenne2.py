import ccxt
import sys
import os
import argparse
import time
from datetime import datetime
import pytz
import threading

def fetch_markets(exchange):
    try:
        markets = exchange.fetch_markets()
        # Filter to include only assets ending with '/USDT'
        symbols = [market['symbol'] for market in markets if market['spot'] and market['symbol'].endswith('/USDT')]
        return symbols
    except (ccxt.ExchangeError, ccxt.NetworkError, ccxt.DDoSProtection) as e:
        print(f"Exchange error: {str(e)}")
        os.kill(os.getpid(), 9)
        sys.exit(-999)

def fetch_ohlcv(exchange, symbol, timeframe, limit):
    try:
        return exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    except Exception as e:
        print(f"Error fetching OHLCV data for {symbol}: {str(e)}")
        return []

def fetch_current_price(exchange, symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['ask'] if 'ask' in ticker else None
    except Exception as e:
        print(f"Error fetching current price for {symbol}: {str(e)}")
        return None

def format_candle_time(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')

def calculate_percentage_evolution(open_price, current_price):
    if open_price == 0:
        return 0
    return ((current_price - open_price) / open_price) * 100

def analyze_symbol(exchange, symbol, timeframe, output_file):
    try:
        ohlcv = fetch_ohlcv(exchange, symbol, timeframe, 1)
        if not ohlcv:
            return

        current_price = fetch_current_price(exchange, symbol)
        if current_price is None:
            return

        if len(ohlcv) < 1:
            return

        current_candle = ohlcv[-1]
        open_price = current_candle[1]
        evolution = calculate_percentage_evolution(open_price, current_price)

        current_time = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
        result = (
            f"[{current_time}] {symbol} (BINANCE:{symbol.replace('/', '')}) "
            f"Timeframe: {timeframe}, Current price: {current_price:.4f}, Current candle evolution: {evolution:.2f}%\n\n"
        )
        print(result.strip())

        with open(output_file, 'a') as f:
            f.write(result)

    except Exception as e:
        print(f"Error analyzing symbol {symbol}: {str(e)}")

def worker(exchange, symbols, timeframe, output_file):
    for symbol in symbols:
        analyze_symbol(exchange, symbol, timeframe, output_file)

def main():
    parser = argparse.ArgumentParser(description='Show evolution of the current candle.')
    parser.add_argument('--timeframe', type=str, required=True, help='Timeframe for the candlestick analysis')
    args = parser.parse_args()

    timeframe = args.timeframe
    script_name = os.path.basename(__file__).split('.')[0]
    directory = f"scan_results_{script_name}"

    if not os.path.exists(directory):
        os.makedirs(directory)

    output_file = os.path.join(directory, f"{datetime.now(pytz.UTC).strftime('%Y%m%d_%H%M%S')}_{timeframe}_evolution_results.txt")

    exchange = ccxt.binance({
        'rateLimit': 1200,
        'enableRateLimit': True,
    })

    symbols = fetch_markets(exchange)
    num_threads = 20
    chunk_size = len(symbols) // num_threads + 1

    threads = []
    for i in range(num_threads):
        start = i * chunk_size
        end = start + chunk_size
        symbols_chunk = symbols[start:end]
        thread = threading.Thread(target=worker, args=(exchange, symbols_chunk, timeframe, output_file))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == '__main__':
    main()
