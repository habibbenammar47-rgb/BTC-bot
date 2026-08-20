import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from sklearn.ensemble import RandomForestClassifier

# جلب الإعدادات السرية من GitHub Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("✅ تم إرسال التنبيه إلى Telegram بنجاح!")
        else:
            print("⚠️ فشل الإرسال، تحقق من Token و Chat ID.")
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")

# 1. جلب البيانات
print("جاري تحميل البيانات وتدريب النموذج...")
df = yf.download("BTC-USD", period="3y", interval="1d", progress=False)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# 2. حساب المؤشرات الفنية
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

# 3. التدريب والتنبؤ
features = ['SMA_10', 'SMA_30', 'RSI', 'Volatility', 'Returns']
X = df[features]
y = df['Target']

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X, y)

latest_data = df.iloc[[-1]][features]
prediction = model.predict(latest_data)[0]
current_price = float(df['Close'].iloc[-1])
current_date = df.index[-1].strftime('%Y-%m-%d')

# 4. التنبيه
if prediction == 1:
    signal_text = "🟢 **إشارة شراء (BUY)**"
    action_text = "النموذج يتوقع ارتفاع السعر غداً."
else:
    signal_text = "🔴 **إشارة بيع/حذر (SELL/HOLD)**"
    action_text = "النموذج يتوقع انخفاض السعر أو استقراره."

alert_message = f"""
🤖 **تحديث بوت التداول اليومي**
📅 **التاريخ:** {current_date}
💰 **سعر BTC الحالي:** ${current_price:,.2f}

📊 **القرار:** {signal_text}
💡 **التفاصيل:** {action_text}
"""

send_telegram_alert(alert_message)
