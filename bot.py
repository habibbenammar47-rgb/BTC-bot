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
BINANCE_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET = os.environ.get("BINANCE_API_SECRET")

# الربط مع منصة Binance
exchange = ccxt.binance({
    'apiKey': BINANCE_KEY,
    'secret': BINANCE_SECRET,
    'enableRateLimit': True,
})

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending telegram msg: {e}")

# 1. دالة للذكاء الاصطناعي لتحليل أي عملة
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
        X, y = df[features], df['Target']

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)

        latest_data = df.iloc[[-1]][features]
        pred = model.predict(latest_data)[0]
        return "🟢 صعود محتمل (BUY)" if pred == 1 else "🔴 هبوط / حذر (SELL)"
    except Exception as e:
        return "⚠️ بيانات غير كافية"

# 2. دالة جلب Top Gainers
def get_top_gainers():
    try:
        tickers = exchange.fetch_tickers()
        usdt_pairs = {symbol: data for symbol, data in tickers.items() if '/USDT' in symbol}
        sorted_pairs = sorted(usdt_pairs.items(), key=lambda item: item[1]['percentage'], reverse=True)
        return sorted_pairs[:5]
    except Exception as e:
        print(f"Error fetching top gainers: {e}")
        return []

# 3. الاستماع لأوامر التليغرام
last_update_id = 0
def process_commands():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}"
    try:
        res = requests.get(url).json()
        for result in res.get("result", []):
            last_update_id = result["update_id"]
            text = result.get("message", {}).get("text", "").strip()
            
            if text.startswith("/top"):
                send_telegram("🔍 **جاري البحث في Binance عن Top Gainers وتحليلها بالذكاء الاصطناعي...**")
                gainers = get_top_gainers()
                if gainers:
                    msg = "📊 **أفضل 5 عملات ارتفاعاً وتوقع الذكاء الاصطناعي:**\n\n"
                    for symbol, data in gainers:
                        pred = analyze_coin(symbol)
                        pct = data.get('percentage', 0)
                        msg += f"🔹 `{symbol}` | نسبة الارتفاع: {pct:.2f}%\n💡 التحليل: {pred}\n\n"
                    msg += "للتنفيذ أرسل:\n`/buy [اسم العملة] [المبلغ]` (مثال: `/buy SOL 10`)"
                    send_telegram(msg)
                else:
                    send_telegram("❌ لم نتمكن من جلب بيانات السوق حالياً.")

            elif text.startswith("/buy"):
                parts = text.split()
                if len(parts) >= 3:
                    coin = parts[1].upper()
                    amount_usdt = float(parts[2])
                    symbol = f"{coin}/USDT" if not coin.endswith("/USDT") else coin
                    ticker = exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    order = exchange.create_market_buy_order(symbol, amount_usdt / price)
                    send_telegram(f"✅ **تم شراء {symbol} بنجاح بقيمة ${amount_usdt}!**")
                else:
                    send_telegram("⚠️ يرجى كتابة الأمر بهذا الشكل: `/buy SOL 10`")

            elif text.startswith("/sell"):
                parts = text.split()
                if len(parts) >= 2:
                    coin = parts[1].upper().replace("/USDT", "")
                    symbol = f"{coin}/USDT"
                    balance = exchange.fetch_balance()
                    amount = balance['free'].get(coin, 0)
                    if amount > 0:
                        order = exchange.create_market_sell_order(symbol, amount)
                        send_telegram(f"🚨 **تم بيع كامل رصيد {coin} بنجاح!**")
                    else:
                        send_telegram(f"ℹ️ لا يوجد رصيد من {coin} للبيع.")
                else:
                    send_telegram("⚠️ يرجى كتابة الأمر بهذا الشكل: `/sell SOL`")
    except Exception as e:
        print(f"Error in command processing: {e}")

if __name__ == "__main__":
    send_telegram("🤖 **البوت يعمل الآن ومستعد لتلقي الأوامر!**\nجرب إرسال `/top` الآن.")
    while True:
        process_commands()
        time.sleep(3)
