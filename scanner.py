import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

FIREBASE_URL = "https://mj-stock-15f1b-default-rtdb.asia-southeast1.firebasedatabase.app/alerts.json"

FNO_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS",
    "BHARTIARTL.NS", "TATAMOTORS.NS", "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS",
    "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "TATASTEEL.NS",
    "NTPC.NS", "POWERGRID.NS", "M&M.NS", "INDUSINDBK.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "COALINDIA.NS", "HINDALCO.NS", "VOLTAS.NS", "EICHERMOT.NS",
    "INDUSTOWER.NS", "TRENT.NS", "BEL.NS", "HAL.NS", "POLYCAB.NS", "PERSISTENT.NS",
    "DIXON.NS", "CHOLAFIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "RECLTD.NS",
    "PFC.NS", "TVSMOTOR.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "DRREDDY.NS",
    "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "JSWSTEEL.NS", "GRASIM.NS",
    "TECHM.NS", "WIPRO.NS", "HCLTECH.NS", "LTIM.NS", "TATAPOWER.NS", "DLF.NS",
    "GODREJPROP.NS", "OBEROIRLTY.NS", "MUTHOOTFIN.NS", "SHRIRAMFIN.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "ICICIPRULI.NS", "BAJAJFINSV.NS", "ASIANPAINT.NS", "PIDILITIND.NS",
    "BRITANNIA.NS", "NESTLEIND.NS", "HINDUNILVR.NS", "ITC.NS", "VBL.NS", "ZOMATO.NS",
    "JIOFIN.NS", "ABB.NS", "SIEMENS.NS", "CUMMINSIND.NS", "BHEL.NS", "IRCTC.NS",
    "INDIGO.NS", "MOTHERSON.NS", "ASHOKLEY.NS", "BHARATFORG.NS", "ASTRAL.NS",
    "SUPREMEIND.NS", "CROMPTON.NS", "HAVELLS.NS", "COFORGE.NS", "MPHASIS.NS",
    "KPITTECH.NS", "LTTS.NS", "AUROPHARMA.NS", "LUPIN.NS", "BIOCON.NS", "ALKEM.NS",
    "TORNTPHARM.NS", "ZYDUSLIFE.NS", "GLENMARK.NS", "LAURUSLABS.NS", "GRANULES.NS",
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "AUBANK.NS", "BANDHANBNK.NS", "RBLBANK.NS",
    "MANAPPURAM.NS", "LICHSGFIN.NS", "ABCAPITAL.NS", "M&MFIN.NS", "MFSL.NS",
    "MCX.NS", "CDSL.NS", "BSE.NS", "ANGELONE.NS", "IEX.NS", "PETRONET.NS", "GAIL.NS",
    "ONGC.NS", "BPCL.NS", "IOC.NS", "HINDPETRO.NS", "IGL.NS", "MGL.NS", "GUJGASLTD.NS",
    "NATIONALUM.NS", "VEDL.NS", "SAIL.NS", "NMDC.NS", "JINDALSTEL.NS", "HINDCOPPER.NS"
]

def calculate_vwap(df):
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    return (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()

def scan_all_fno():
    intraday = yf.download(FNO_STOCKS, period="2d", interval="5m", group_by='ticker', progress=False)
    daily = yf.download(FNO_STOCKS, period="12d", interval="1d", group_by='ticker', progress=False)

    for ticker in FNO_STOCKS:
        try:
            df = intraday[ticker].dropna().copy()
            df_d = daily[ticker].dropna()
            if len(df) < 25 or len(df_d) < 9:
                continue

            last_date = df.index[-1].date()
            df_today = df[df.index.date == last_date].copy()
            if len(df_today) < 3:
                continue

            df_today['VWAP'] = calculate_vwap(df_today)
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df_today['EMA20'] = df['EMA20'].loc[df_today.index]

            curr = df_today.iloc[-1]
            prev = df_today.iloc[-2]
            pdh = float(df_d['High'].iloc[-2])
            pdl = float(df_d['Low'].iloc[-2])

            # Pichhle 8 din ki consolidation range (aaj ko chhodkar)
            range_days = df_d.iloc[-9:-1]
            range_high = float(range_days['High'].max())
            range_low = float(range_days['Low'].min())
            range_pct = ((range_high - range_low) / range_low) * 100

            symbol = ticker.replace(".NS", "")
            cmp = round(float(curr['Close']), 2)
            vwap = round(float(curr['VWAP']), 2)
            ema20 = round(float(curr['EMA20']), 2)

            signal = None
            strategy = ""

            # 1. 7-8 Day Narrow Range Breakout / Breakdown (range <= 5.5%)
            if range_pct <= 5.5 and curr['Close'] > range_high and prev['Close'] <= range_high:
                signal = "BUY"
                strategy = "7-8D Range Breakout"
            elif range_pct <= 5.5 and curr['Close'] < range_low and prev['Close'] >= range_low:
                signal = "SELL"
                strategy = "7-8D Range Breakout"
            # 2. 5m VWAP + 20 EMA Cross
            elif (curr['Close'] > curr['VWAP'] and curr['Close'] > curr['EMA20']) and not (prev['Close'] > prev['VWAP'] and prev['Close'] > prev['EMA20']):
                signal = "BUY"
                strategy = "5m VWAP + 20 EMA"
            elif (curr['Close'] < curr['VWAP'] and curr['Close'] < curr['EMA20']) and not (prev['Close'] < prev['VWAP'] and prev['Close'] < prev['EMA20']):
                signal = "SELL"
                strategy = "5m VWAP + 20 EMA"
            # 3. 5m VWAP Cross
            elif curr['Close'] > curr['VWAP'] and prev['Close'] <= curr['VWAP']:
                signal = "BUY"
                strategy = "5m VWAP Cross"
            elif curr['Close'] < curr['VWAP'] and prev['Close'] >= curr['VWAP']:
                signal = "SELL"
                strategy = "5m VWAP Cross"
            # 4. PDH / PDL Breakout
            elif curr['Close'] > pdh and prev['Close'] <= pdh:
                signal = "BUY"
                strategy = "PDH/PDL"
            elif curr['Close'] < pdl and prev['Close'] >= pdl:
                signal = "SELL"
                strategy = "PDH/PDL"

            if signal:
                sl = round(cmp * 0.993, 2) if signal == "BUY" else round(cmp * 1.007, 2)
                target = round(cmp * 1.015, 2) if signal == "BUY" else round(cmp * 0.985, 2)

                alert_data = {
                    "symbol": symbol,
                    "type": signal,
                    "strategy": strategy,
                    "cmp": cmp,
                    "vwap": vwap,
                    "ema20": ema20,
                    "sl": sl,
                    "target": target,
                    "time": curr.name.strftime("%I:%M %p")
                }
                requests.post(FIREBASE_URL, json=alert_data)
        except Exception:
            continue

if __name__ == "__main__":
    scan_all_fno()
         
