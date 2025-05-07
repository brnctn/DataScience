import tkinter as tk
import threading
import time
import pandas as pd
import json
from ta.momentum import RSIIndicator
from ta.trend import MACD
from binance.client import Client
from ta.trend import EMAIndicator
from ta.volatility import BollingerBands

# Testnet API Key'in buraya
api_key = 'YOUR API KEY'
api_secret = 'YOUR SECRET KEY'

client = Client(api_key, api_secret)
client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'

# Varsayılan değerler
symbol = 'BTCUSDT'
interval = '5m'
quantity = 0.001
leverage = 20
rsi_long_threshold = 30
rsi_short_threshold = 70
running = False



def get_klines():
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=200)
    df = pd.DataFrame(klines, columns=['time','open','high','low','close','volume','c_time','qv','n','tb','tq','ignore'])
    df['close'] = pd.to_numeric(df['close'])
    return df

def calculate_indicators(df, interval_selected='5m'):
    if interval_selected == '1m': ema_fast, ema_slow = 20, 50
    elif interval_selected == '5m': ema_fast, ema_slow = 50, 100
    elif interval_selected == '15m': ema_fast, ema_slow = 50, 150
    elif interval_selected == '1h': ema_fast, ema_slow = 100, 200
    elif interval_selected == '4h': ema_fast, ema_slow = 150, 250
    elif interval_selected == '1d': ema_fast, ema_slow = 200, 300
    else: ema_fast, ema_slow = 50, 200

    df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
    df['ema50'] = EMAIndicator(close=df['close'], window=ema_fast).ema_indicator()
    df['ema200'] = EMAIndicator(close=df['close'], window=ema_slow).ema_indicator()
    macd = MACD(close=df['close'])
    df['macd_hist'] = macd.macd_diff()
    bb = BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_low'] = bb.bollinger_lband()
    df['bb_high'] = bb.bollinger_hband()
    return df

def get_position():
    positions = client.futures_position_information(symbol=symbol)
    for pos in positions:
        entry_price = float(pos['entryPrice'])
        amount = float(pos['positionAmt'])
        if amount > 0:
            return 'long', entry_price
        elif amount < 0:
            return 'short', entry_price
    return None, None

def place_order(side):
    return client.futures_create_order(
        symbol=symbol,
        side=side,
        type='MARKET',
        quantity=quantity
    )

def should_long(df):
    row = df.iloc[-1]
    return (row['rsi'] < rsi_long_threshold and row['ema50'] > row['ema200'])

def should_short(df):
    row = df.iloc[-1]
    return (row['rsi'] > rsi_short_threshold and row['ema50'] < row['ema200'])

"""

def should_long(df):
    row = df.iloc[-1]
    return (row['rsi'] < rsi_long_threshold and row['ema50'] > row['ema200'] and row['macd_hist'] > 0 and row['close'] <= row['bb_low'])

def should_short(df):
    row = df.iloc[-1]
    return (row['rsi'] > rsi_short_threshold and row['ema50'] < row['ema200'] and row['macd_hist'] < 0 and row['close'] >= row['bb_high'])

"""

def run_backtest():
   
    symbol_bt = symbol_entry.get().upper()
    interval_bt = interval_var.get()
    rsi_l = int(rsi_long_entry.get())
    rsi_s = int(rsi_short_entry.get())
    usdt_amount = float(quantity_entry.get())

    try:
        klines = client.futures_klines(symbol=symbol_bt, interval=interval_bt, limit=1000)
        df = pd.DataFrame(klines, columns=['time','open','high','low','close','volume','c_time','qv','n','tb','tq','ignore'])
        df['close'] = pd.to_numeric(df['close'])
        df = calculate_indicators(df, interval_selected=interval_bt)

        position = None
        entry_price = 0
        pnl_list = []

        for i in range(200, len(df)):
            row = df.iloc[i]
            price = row['close']
            rsi = row['rsi']
            ema50 = row['ema50']
            ema200 = row['ema200']
            macd = row['macd_hist']
            bb_low = row['bb_low']
            bb_high = row['bb_high']

            # coin miktarı USDT üzerinden hesaplanır
            coin_amount = usdt_amount / price  

            if position is None:
                if rsi < rsi_l and ema50 > ema200 and macd > 0 and price <= bb_low:
                    position = 'long'
                    entry_price = price
                elif rsi > rsi_s and ema50 < ema200 and macd < 0 and price >= bb_high:
                    position = 'short'
                    entry_price = price
            elif position == 'long':
                change = (price - entry_price) / entry_price * 100
                if change >= 2 or change <= -1:
                    pnl = change * coin_amount / 100 * leverage
                    pnl_list.append(pnl)
                    position = None
            elif position == 'short':
                change = (entry_price - price) / entry_price * 100
                if change >= 2 or change <= -1:
                    pnl = change * coin_amount / 100 * leverage
                    pnl_list.append(pnl)
                    position = None

        total = sum(pnl_list)
        win = len([x for x in pnl_list if x > 0])
        loss = len([x for x in pnl_list if x <= 0])
        winrate = (win / (win + loss)) * 100 if (win + loss) > 0 else 0

        backtest_text.set(
            f"Backtest ({symbol_bt} / {interval_bt}):\n"
            f"Toplam Kar/Zarar: {total:.2f} USDT\n"
            f"İşlem Sayısı: {len(pnl_list)}\n"
            f"Başarı: %{winrate:.2f} ({win}W / {loss}L)"
        )

    except Exception as e:
        backtest_text.set(f"Backtest hatası: {e}")


def bot_loop():
    global running
    while running:
        df = get_klines()
        df = calculate_indicators(df, interval_selected=interval)
        price = df['close'].iloc[-1]
        position, entry_price = get_position()

        if position is None:
            if should_long(df):
                place_order('BUY')
                log_text.set(f"LONG açıldı @ {price}")
            elif should_short(df):
                place_order('SELL')
                log_text.set(f"SHORT açıldı @ {price}")
        elif position == 'long':
            profit = ((price - entry_price) / entry_price) * 100
            if profit >= 2 or profit <= -1:
                place_order('SELL')
                log_text.set(f"LONG kapatıldı @ {price} | PnL: %{profit:.2f}")
        elif position == 'short':
            profit = ((entry_price - price) / entry_price) * 100
            if profit >= 2 or profit <= -1:
                place_order('BUY')
                log_text.set(f"SHORT kapatıldı @ {price} | PnL: %{profit:.2f}")
        time.sleep(60)

def start_bot():
    global running, symbol, quantity, leverage, rsi_long_threshold, rsi_short_threshold, interval

    symbol = symbol_entry.get().upper()
    usdt_amount = float(quantity_entry.get())
    leverage = int(leverage_entry.get())
    rsi_long_threshold = int(rsi_long_entry.get())
    rsi_short_threshold = int(rsi_short_entry.get())
    interval = interval_var.get()

    # Anlık coin fiyatını çek
    ticker = client.futures_symbol_ticker(symbol=symbol)
    current_price = float(ticker['price'])

    # Coin miktarını hesapla (örneğin BTC cinsinden)
    quantity = round(usdt_amount / current_price, 6)

    client.futures_change_leverage(symbol=symbol, leverage=leverage)

    if not running:
        running = True
        threading.Thread(target=bot_loop, daemon=True).start()
        log_text.set(f"Bot çalışıyor. {usdt_amount} USDT ≈ {quantity} {symbol[:-4]}")


def stop_bot():
    global running
    running = False
    log_text.set("Bot durduruldu.")
"""
def önerilen_eşikleri_ayarla():
    val = interval_var.get()
    eşikler = {
        '1m': (24, 76), '5m': (30, 70), '15m': (30, 70),
        '1h': (35, 65), '4h': (38, 62), '1d': (45, 55)
    }
    rsi_l, rsi_s = eşikler.get(val, (30, 70))
    rsi_long_entry.delete(0, tk.END)
    rsi_short_entry.delete(0, tk.END)
    rsi_long_entry.insert(0, str(rsi_l))
    rsi_short_entry.insert(0, str(rsi_s))
    log_text.set(f"{val} için RSI eşikleri güncellendi.")   """

# GUI Arayüz
root = tk.Tk()
root.title("Binance Futures Testnet Trading Botu")
root.geometry("400x600")

tk.Label(root, text="Sembol:").pack()
symbol_entry = tk.Entry(root)
symbol_entry.insert(0, "BTCUSDT")
symbol_entry.pack()

tk.Label(root, text="Miktar (USDT):").pack()
quantity_entry = tk.Entry(root)
quantity_entry.insert(0, "20")
quantity_entry.pack()


tk.Label(root, text="Kaldıraç:").pack()
leverage_entry = tk.Entry(root)
leverage_entry.insert(0, "20")
leverage_entry.pack()

tk.Label(root, text="Zaman Aralığı:").pack()
interval_var = tk.StringVar()
interval_var.set("5m")
tk.OptionMenu(root, interval_var, "1m", "5m", "15m", "1h", "4h", "1d").pack()

tk.Label(root, text="RSI Long Eşiği:").pack()
rsi_long_entry = tk.Entry(root)
rsi_long_entry.insert(0, "30")
rsi_long_entry.pack()

tk.Label(root, text="RSI Short Eşiği:").pack()
rsi_short_entry = tk.Entry(root)
rsi_short_entry.insert(0, "70")
rsi_short_entry.pack()

tk.Button(root, text="BAŞLAT", command=start_bot, bg="green", fg="white", width=20).pack(pady=5)
tk.Button(root, text="DURDUR", command=stop_bot, bg="red", fg="white", width=20).pack(pady=5)
# tk.Button(root, text="EŞİKLERİ ÖNER", command=önerilen_eşikleri_ayarla, bg="orange", width=20).pack(pady=5)

backtest_text = tk.StringVar()
tk.Label(root, textvariable=backtest_text, wraplength=380, justify="left", fg="blue").pack(pady=10)
tk.Button(root, text="BACKTEST", command=run_backtest, bg="blue", fg="white", width=20).pack(pady=5)

log_text = tk.StringVar()
tk.Label(root, textvariable=log_text, wraplength=380, justify="left").pack(pady=10)

root.mainloop()
