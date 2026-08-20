import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from sklearn.ensemble import RandomForestClassifier

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_with_buttons(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    inline_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ تنفيذ الصفقة ($10)", "callback_data": "buy_10"},
                {"text": "❌ إلغاء", "callback_data": "cancel"}
            ]
        ]
    }
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": inline_keyboard
    }
    
    try:
        r = requests.post(url, json=payload)
        print("Telegram Response:", r.status_code, r.text)
    except Exception as e:
        print(f"Error: {e}")

# 1. جلب البيانات
print("Fetching BTC data...")
df = yf.download("BTC-USD", period="1y", interval="1d", progress=False)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# 2. الحسابات والتحليل
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
prediction = model.predict(latest_data)[0]
current_price = float(df['Close'].iloc[-1])

signal = "ارتفاع (إشارة شراء 🟢)" if prediction == 1 else "انخفاض (إشارة حذر/بيع 🔴)"

message = f"""
🤖 **تنبيه إشارة تداول BTC**

💰 **سعر BTC الحالي:** ${current_price:,.2f}
🔮 **التوقع:** {signal}

اختر من الأزرار أدناه للتحكم:
"""

send_telegram_with_buttons(message)
