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

# الربط مع Bybit للتداول
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
        
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std()
        
        df['Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
        df.dropna(inplace=True)

        features = ['SMA_10', 'SMA_30', 'RSI', 'MACD', 'MACD_Signal', 'BB_Upper', 'BB_Lower', 'Volatility', 'Returns']
        X = df[features]
        y = df['Target']

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)

        latest_data = df.iloc[[-1]][features]
        pred = model.predict(latest_data)[0]
        return "🟢 صعود محتمل (BUY)" if pred == 1 else "🔴 هبوط / حذر (SELL)"
    except Exception as e:
        print(f"Analysis error for {symbol}: {e}")
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

            if text.startswith("/help"):
                help_msg = (
                    "🤖 **دليل استخدام بوت التداول الذكي المتقدم:**\n\n"
                    "• `/top` - لجلب أفضل 5 عملات مرتفعة مع السعر والتحليل الشامل.\n"
                    "• `/price <coin>` - لمعرفة السعر الحالي والتحليل الفني لأي عملة (مثال: `/price SOL`).\n"
                    "• `/balance` - لعرض رصيد محفظتك الحالي على منصة Bybit.\n"
                    "• `/buy <coin> <usdt> [TP%] [SL%]` - لشراء العملة مع وضع أوامر جني الربح ووقف الخسارة تلقائياً في المنصة (مثال: `/buy SOL 10 5 3`).\n"
                    "• `/sell <coin>` - لبيع كامل رصيد العملة المحدد على منصة Bybit.\n"
                    "• `/help` - لعرض قائمة الأوامر."
                )
                send_telegram(help_msg)

            elif text.startswith("/top"):
                send_telegram("⏳ جاري تحليل السوق بمؤشرات (MACD, RSI, Bollinger) وجلب أفضل العملات...")
                gainers = get_top_gainers()
                if gainers:
                    msg = "**أفضل العملات ارتفاعاً مع التحليل الشامل:**\n"
                    for symbol, price, percentage in gainers:
                        msg += f"• **{symbol}**\n  السعر: `${price:.2f}` | الارتفاع: `{percentage:.2f}%`\n  التحليل الذكي: {analyze_coin(symbol)}\n\n"
                    send_telegram(msg)
                else:
                    send_telegram("❌ لم نتمكن من جلب بيانات السوق حالياً")

            elif text.startswith("/price"):
                parts = text.split()
                if len(parts) > 1:
                    coin = parts[1].upper()
                    symbol = f"{coin}/USDT" if not coin.endswith("/USDT") else coin
                    try:
                        yahoo_symbol = symbol.replace('/USDT', '-USD')
                        df = yf.download(yahoo_symbol, period="1d", interval="1m", progress=False)
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        current_price = float(df['Close'].iloc[-1])
                        send_telegram(f"💰 سعر العملة **{symbol}** حالياً هو: `${current_price:.4f}`\nالتحليل الفني:\n{analyze_coin(symbol)}")
                    except Exception as e:
                        send_telegram(f"❌ لم نتمكن من جلب سعر العملة {symbol}")
                else:
                    send_telegram("⚠️ يرجى كتابة الأمر بهذا الشكل: /price BTC")

            elif text.startswith("/balance"):
                try:
                    balance = exchange.fetch_balance()
                    free_usdt = balance['free'].get('USDT', 0)
                    total_usdt = balance['total'].get('USDT', 0)
                    
                    msg = f"💼 **حالة المحفظة على Bybit:**\n\n• USDT المتاح: `${free_usdt:.2f}`\n• إجمالي USDT: `${total_usdt:.2f}`\n\n**العملات المملوكة:**\n"
                    has_coins = False
                    for coin, total_amount in balance['total'].items():
                        if total_amount > 0 and coin not in ['USDT', 'USD']:
                            if balance['free'].get(coin, 0) > 0 or total_amount > 0:
                                msg += f"• {coin}: `{total_amount}`\n"
                                has_coins = True
                    if not has_coins:
                        msg += "لا توجد عملات أخرى حالياً، رصيدك كله USDT."
                    send_telegram(msg)
                except Exception as e:
                    send_telegram(f"❌ تعذر جلب رصيد المحفظة: {e}")

            elif text.startswith("/buy"):
                parts = text.split()
                if len(parts) > 2:
                    coin = parts[1].upper()
                    amount_usdt = float(parts[2])
                    tp_pct = float(parts[3]) if len(parts) > 3 else None 
                    sl_pct = float(parts[4]) if len(parts) > 4 else None 
                    
                    symbol = f"{coin}/USDT" if not coin.endswith("/USDT") else coin
                    ticker = exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    amount = amount_usdt / price
                    
                    # 1. تنفيذ أمر الشراء بالسوق
                    order = exchange.create_market_buy_order(symbol, amount)
                    reply_msg = f"✅ تم تنفيذ شراء **{symbol}** بقيمة `{amount_usdt}$` بسعر السوق (`${price:.4f}`)."
                    
                    # 2. وضع أوامر البيع المشروطة (TP و SL) في منصة Bybit إذا تم تحديدها
                    try:
                        base_coin = coin.replace('/USDT', '')
                        if tp_pct:
                            tp_price = price * (1 + tp_pct / 100)
                            # إرسال أمر بيع مشروط لجني الربح
                            exchange.create_order(
                                symbol=symbol,
                                type='limit',
                                side='sell',
                                amount=amount,
                                price=tp_price,
                                params={'triggerPrice': tp_price, 'reduceOnly': True}
                            )
                            reply_msg += f"\n🎯 تم تفعيل أمر **جني الربح (+{tp_pct}%)** عند سعر: `${tp_price:.4f}`"

                        if sl_pct:
                            sl_price = price * (1 - sl_pct / 100)
                            # إرسال أمر بيع مشروط لوقف الخسارة
                            exchange.create_order(
                                symbol=symbol,
                                type='market',
                                side='sell',
                                amount=amount,
                                params={'triggerPrice': sl_price, 'reduceOnly': True}
                            )
                            reply_msg += f"\n🛡️ تم تفعيل أمر **وقف الخسارة (-{sl_pct}%)** عند سعر: `${sl_price:.4f}`"
                    except Exception as err:
                        reply_msg += f"\n⚠️ تنبيه: تم الشراء ولكن حدث خطأ في ضبط أوامر TP/SL تلقائياً: {err}"

                    send_telegram(reply_msg)
                else:
                    send_telegram("⚠️ طريقة الاستخدام:\n`/buy SOL 10 5 3`\n(تعني شراء بـ 10 دولار مع جني ربح 5% ووقف خسارة 3% تلقائياً)")

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
    send_telegram("🤖 بوت التداول الذكي مع تفعيل أوامر TP/SL يعمل الآن بنجاح!")
    while True:
        process_commands()
        time.sleep(3)
