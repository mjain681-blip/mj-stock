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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning {len(FNO_STOCKS)} F&O stocks...")
    intraday = yf.download(FNO_STOCKS, period="1d", interval="5m", group_by='ticker', progress=False)
    daily = yf.download(FNO_STOCKS, period="2d", interval="1d", group_by='ticker', progress=False)

    for ticker in FNO_STOCKS:
        try:
            df = intraday[ticker].dropna().copy()
            df_d = daily[ticker].dropna()
            if len(df) < 21 or len(df_d) < 2:
                continue

            df['VWAP'] = calculate_vwap(df)
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            pdh = df_d['High'].iloc[-2]
            pdl = df_d['Low'].iloc[-2]

            symbol = ticker.replace(".NS", "")
            cmp = round(float(curr['Close']), 2)
            vwap = round(float(curr['VWAP']), 2)
            ema20 = round(float(curr['EMA20']), 2)

            signal = None
            strategy = ""

            if (curr['Close'] > curr['VWAP'] and curr['Close'] > curr['EMA20']) and not (prev['Close'] > prev['VWAP'] and prev['Close'] > prev['EMA20']):
                signal = "BUY"
                strategy = "5m VWAP + 20 EMA"
            elif (curr['Close'] < curr['VWAP'] and curr['Close'] < curr['EMA20']) and not (prev['Close'] < prev['VWAP'] and prev['Close'] < prev['EMA20']):
                signal = "SELL"
                strategy = "5m VWAP + 20 EMA"
            elif curr['Close'] > curr['VWAP'] and prev['Close'] <= curr['VWAP']:
                signal = "BUY"
                strategy = "5m VWAP Cross"
            elif curr['Close'] < curr['VWAP'] and prev['Close'] >= curr['VWAP']:
                signal = "SELL"
                strategy = "5m VWAP Cross"
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
                    "time": datetime.now().strftime("%I:%M %p")
                }
                requests.post(FIREBASE_URL, json=alert_data)
                print(f"Alert Sent: {symbol} | {signal} | {strategy}")
        except Exception:
            continue

if __name__ == "__main__":
    scan_all_fno()
          
