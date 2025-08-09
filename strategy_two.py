import pandas as pd
from okx_api import fetch_ohlcv

def check_signal(symbol):
    data_5m = fetch_ohlcv(symbol, '5m', 100)
    if not data_5m:
        return False
    df = pd.DataFrame(data_5m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['rsi'] = rsi(df['close'], 14)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if (prev['ema9'] < prev['ema21']) and (last['ema9'] > last['ema21']) and (last['rsi'] > 55):
        return True
    return False

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
