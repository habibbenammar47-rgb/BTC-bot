import os
import time
import requests
import ccxt
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# الإعدادات
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
BINANCE_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET = os.environ.get("BINANCE_API_SECRET")

exchange = ccxt.binance({'apiKey': BINANCE_KEY, 'secret': BINANCE_SECRET, 'enableRateLimit': True})

def send_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

# --- 1. جزء الذكاء الاصطناعي ---
def get_prediction(symbol):
    try:
        yahoo_symbol = symbol.replace('/USDT', '-USD')
        df = yf.download(yahoo_symbol, period="1y", interval="1d", progress=False)
        df['SMA_10'] = df['Close'].rolling(10).mean()
        df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().rolling(14).mean() / df['Close'].diff().abs().rolling(14).mean())))
        df['Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
        df.dropna(inplace=True)
        model = RandomForestClassifier().fit(df[['SMA_10', 'RSI']], df['Target'])
        pred = model.predict(df[['SMA_10', 'RSI']].iloc[[-1]])[0]
        return "🟢 BUY" if pred == 1 else "🔴 WAIT"
    except: return "⚠️"

# --- 2. الماسح التلقائي ---
def scanner():
    tickers = exchange.fetch_tickers()
    gainers = sorted([t for t in tickers if '/USDT' in t], key=lambda x: tickers[x]['percentage'], reverse=True)[:3]
    msg = "🔍 **ماسح الفرص الآلي:**\n"
    for s in gainers:
        pred = get_prediction(s)
        if "BUY" in pred:
            msg += f"🔥 `{s}`: {tickers[s]['percentage']}% | {pred}\n"
    if "🔥" in msg: send_msg(msg + "\nأرسل `/buy [العملة] [المبلغ]` للتنفيذ.")

# --- 3. منفذ الأوامر (Command Listener) ---
last_id = 0
def listener():
    global last_id
    res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}").json()
    for r in res.get("result", []):
        last_id = r["update_id"]
        text = r.get("message", {}).get("text", "").split()
        if not text: continue
        cmd = text[0]
        
        if cmd == "/buy":
            symbol = f"{text[1].upper()}/USDT"
            amt = float(text[2])
            price = exchange.fetch_ticker(symbol)['last']
            exchange.create_market_buy_order(symbol, amt / price)
            send_msg(f"✅ تم شراء {symbol}")
        elif cmd == "/sell":
            symbol = f"{text[1].upper()}/USDT"
            bal = exchange.fetch_balance()['free'].get(text[1].upper(), 0)
            exchange.create_market_sell_order(symbol, bal)
            send_msg(f"🚨 تم بيع {symbol}")

# الحلقة الرئيسية
while True:
    try:
        listener()
        # مسح السوق كل ساعة (3600 ثانية)
        # يمكنك إضافة منطق توقيت هنا
        time.sleep(5)
    except Exception as e:
        print(e)
        time.sleep(10)
        
