import pandas as pd
import matplotlib.pyplot as plt
from binance.client import Client
from ta.momentum import RSIIndicator

# Binance API bilgilerini gir
api_key = 'YOUR API KEY'
api_secret = 'YOUR SECRET KEY'
client = Client(api_key, api_secret)

# Kline verisi çek (örnek: BTCUSDT 1h)
klines = client.futures_klines(symbol='BTCUSDT', interval='1h', limit=100)
df = pd.DataFrame(klines, columns=['time','open','high','low','close','volume','close_time','qv','n','tb','tq','ignore'])
df['close'] = pd.to_numeric(df['close'])

# RSI hesapla
rsi = RSIIndicator(close=df['close'], window=14).rsi()
df['rsi'] = rsi

# RSI Grafiği
plt.figure(figsize=(10, 5))
plt.plot(df['rsi'], label='RSI', color='blue')
plt.axhline(70, color='red', linestyle='--', label='Overbought (70)')
plt.axhline(30, color='green', linestyle='--', label='Oversold (30)')
plt.fill_between(df.index, 30, 70, color='gray', alpha=0.1)
plt.title('BTCUSDT RSI Grafiği (1 Saatlik Mum)')
plt.xlabel('Mum')
plt.ylabel('RSI Değeri')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
