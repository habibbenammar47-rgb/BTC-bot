import os
import time
import requests
import ccxt
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# المتغيرات السرية
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
BYBIT_KEY = os.environ.get("BYBIT_API_KEY")
BYBIT_SECRET = os.environ.get("BYBIT_API_SECRET")

# الربط مع Bybit للتداول فقط
exchange = ccxt.bybit({
    'apiKey': BYBIT_KEY,
    'secret': BYBIT_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot',
    },
})

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending telegram msg: {e}")

def analyze_coin(symbol):
    try:
        yahoo_symbol = symbol.replace('/USDT', '-USD')
        df = yf.download(yahoo_symbol, period="1y", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df['SMA_10'] = df['Close'].rolling(window=10).mean()
        df['SMA_30'] = df['Close'].rolling(window=30).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std()
        df['Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
        df.dropna(inplace=True)

        features = ['SMA_10', 'SMA_30', 'RSI', 'Volatility', 'Returns']
        X = df[features]
        y = df['Target']

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)

        latest_data = df.iloc[[-1]][features]
        pred = model.predict(latest_data)[0]
        return "🟢 صعود محتمل (BUY)" if pred == 1 else "🔴 هبوط / حذر (SELL)"
    except Exception as e:
        return "⚠️ بيانات غير كافية"

def get_top_gainers():
    coins = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "LINK/USDT", "BNB/USDT", "SUI/USDT"]
    results = []
    
    for symbol in coins:
        try:
            yahoo_symbol = symbol.replace('/USDT', '-USD')
            df = yf.download(yahoo_symbol, period="5d", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) >= 2:
                prev_close = df['Close'].iloc[-2]
                latest_close = float(df['Close'].iloc[-1])
                change = float(((latest_close - prev_close) / prev_close) * 100)
                results.append((symbol, latest_close, change))
        except Exception as e:
            print(f"Error for {symbol}: {e}")
            continue
            
    sorted_pairs = sorted(results, key=lambda x: x[2], reverse=True)
    return sorted_pairs[:5]

last_update_id = 0
def process_commands():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}"
    try:
        res = requests.get(url).json()
        for result in res.get("result", []):
            last_update_id = result["update_id"]
            text = result["message"].get("text", "").strip()

            if text.startswith("/top"):
                send_telegram("⏳ جاري تحليل السوق وجلب أفضل العملات...")
                gainers = get_top_gainers()
                if gainers:
                    msg = "**أفضل العملات ارتفاعاً:**\n"
                    for symbol, price, percentage in gainers:
                        msg += f"• {symbol} | السعر: ${price:.2f} | الارتفاع: {percentage:.2f}% | التحليل: {analyze_coin(symbol)}\n"
                    send_telegram(msg)
                else:
                    send_telegram("❌ لم نتمكن من جلب بيانات السوق حالياً")

            elif text.startswith("/buy"):
                parts = text.split()
                if len(parts) > 2:
                    coin = parts[1].upper()
                    amount_usdt = float(parts[2])
                    symbol = f"{coin}/USDT" if not coin.endswith("/USDT") else coin
                    ticker = exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    amount = amount_usdt / price
                    order = exchange.create_market_buy_order(symbol, amount)
                    send_telegram(f"✅ تم شراء {symbol} بقيمة {amount_usdt}$")
                else:
                    send_telegram("⚠️ يرجى كتابة الأمر بهذا الشكل: /buy SOL 10")

            elif text.startswith("/sell"):
                parts = text.split()
                if len(parts) > 2:
                    coin = parts[1].upper().replace("/USDT", "")
                    symbol = f"{coin}/USDT"
                    balance = exchange.fetch_balance()
                    amount = balance['total'].get(coin, 0)
                    if amount > 0:
                        order = exchange.create_market_sell_order(symbol, amount)
                        send_telegram(f"✅ تم بيع كامل رصيد {coin} بنجاح")
                    else:
                        send_telegram(f"❌ لا يوجد رصيد من {coin} للبيع")
                else:
                    send_telegram("⚠️ يرجى كتابة الأمر بهذا الشكل: /sell SOL")
    except Exception as e:
        print(f"Error in command processing: {e}")

if __name__ == "__main__":
    send_telegram("🤖 البوت يعمل الآن ومستعد لتلقي الأوامر")
    while True:
        process_commands()
        time.sleep(3)
    
