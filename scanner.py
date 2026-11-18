import os
import time
import requests
import pandas as pd
import numpy as np
from io import StringIO
from datetime import datetime, timezone, timedelta

CLIENT_ID = os.environ.get("DHAN_CLIENT_ID", "").strip()
ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
FIREBASE_URL = "https://mj-stock-15f1b-default-rtdb.asia-southeast1.firebasedatabase.app/alerts.json"

FNO_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL",
    "SBIN", "LT", "ITC", "AXISBANK", "KOTAKBANK", "HINDUNILVR",
    "BAJFINANCE", "MARUTI", "M&M", "SUNPHARMA", "TITAN", "ULTRACEMCO",
    "NTPC", "ONGC", "POWERGRID", "TATASTEEL", "JSWSTEEL", "HINDALCO",
    "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV", "BAJAJ-AUTO",
    "EICHERMOT", "HEROMOTOCO", "TVSMOTOR", "TRENT", "BEL", "HAL",
    "BHEL", "RECLTD", "PFC", "IRCTC", "INDIGO", "DLF", "GODREJPROP",
    "LODHA", "OBEROIRLTY", "ASIANPAINT", "PIDILITIND", "BRITANNIA",
    "NESTLEIND", "TATACONSUM", "VBL", "DABUR", "MARICO", "COLPAL",
    "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN", "AUROPHARMA", "APOLLOHOSP",
    "MAXHEALTH", "FORTIS", "HCLTECH", "WIPRO", "TECHM", "PERSISTENT",
    "COFORGE", "MPHASIS", "KPITTECH", "TATAELXSI", "INDUSINDBK",
    "FEDERALBNK", "IDFCFIRSTB", "AUBANK", "BANDHANBNK", "PNB", "BANKBARODA",
    "CANBK", "UNIONBANK", "CHOLAFIN", "SHRIRAMFIN", "MUTHOOTFIN",
    "MANAPPURAM", "SBILIFE", "HDFCLIFE", "ICICIGI", "SBICARD", "MCX",
    "BSE", "CDSL", "ANGELONE", "JIOFIN", "ETERNAL", "POLYCAB",
    "HAVELLS", "VOLTAS", "BLUESTARCO", "DIXON", "AMBER", "ABB",
    "SIEMENS", "CGPOWER", "CUMMINSIND", "ASTRAL", "SUPREMEIND",
    "GRASIM", "AMBUJACEM", "SHREECEM", "ACC", "DALBHARAT", "UPL",
    "PIIND", "SRF", "DEEPAKNTR", "NAVINFLUOR", "TATACHEM", "GAIL",
    "BPCL", "IOC", "HINDPETRO", "PETRONET", "IGL", "MGL", "TATAPOWER",
    "NHPC", "SJVN", "CESC", "INDUSTOWER", "IDEA", "SAIL", "NMDC",
    "VEDL", "NATIONALUM", "JINDALSTEL", "EXIDEIND", "MOTHERSON",
    "BOSCHLTD", "MRF", "APOLLOTYRE", "BALKRISIND", "ASHOKLEY",
    "ESCORTS", "CONCOR", "IRFC", "RVNL"
]

ist = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(ist)
today_str = now_ist.strftime("%Y-%m-%d")
time_str = now_ist.strftime("%I:%M %p")
from_date_daily = (now_ist - timedelta(days=18)).strftime("%Y-%m-%d")
from_date_intra = (now_ist - timedelta(days=3)).strftime("%Y-%m-%d")
to_date_intra = (now_ist + timedelta(days=1)).strftime("%Y-%m-%d")

print(f"Starting Dhan 0-Second Live Scan at {today_str} {time_str} IST...")

if not CLIENT_ID or not ACCESS_TOKEN:
    print("ERROR: DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN missing in GitHub Secrets!")
    exit(1)

# 1. Fetch Dhan Security IDs for NSE Equity
sec_map = {}
try:
    csv_resp = requests.get("https://images.dhan.co/api-data/api-scrip-master.csv", timeout=20)
    df_sec = pd.read_csv(StringIO(csv_resp.text), usecols=["SEM_EXM_EXCH_ID", "SEM_INSTRUMENT_NAME", "SEM_SMST_SECURITY_ID", "SEM_TRADING_SYMBOL"], low_memory=False)
    eq_df = df_sec[(df_sec["SEM_EXM_EXCH_ID"] == "NSE") & (df_sec["SEM_INSTRUMENT_NAME"] == "EQUITY")]
    for _, row in eq_df.iterrows():
        sym = str(row["SEM_TRADING_SYMBOL"]).strip()
        if sym in FNO_SYMBOLS:
            sec_map[sym] = str(row["SEM_SMST_SECURITY_ID"]).strip()
    print(f"Mapped {len(sec_map)} F&O stocks on Dhan.")
except Exception as e:
    print("Scrip master fetch error:", e)
    exit(1)

headers = {
    "access-token": ACCESS_TOKEN,
    "client-id": CLIENT_ID,
    "Content-Type": "application/json"
}

existing_keys = set()
try:
    r = requests.get(FIREBASE_URL, timeout=10)
    if r.status_code == 200 and r.json():
        for k, v in r.json().items():
            if isinstance(v, dict) and v.get("date") == today_str:
                existing_keys.add(f"{v.get('symbol')}_{v.get('strategy')}_{v.get('type')}")
except Exception as e:
    print("Firebase GET error:", e)

signals = []

for sym, sec_id in sec_map.items():
    try:
        # Daily Historical Data
        d_payload = {
            "securityId": sec_id,
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "expiryCode": 0,
            "fromDate": from_date_daily,
            "toDate": today_str
        }
        d_res = requests.post("https://api.dhan.co/v2/charts/historical", headers=headers, json=d_payload, timeout=8)
        if d_res.status_code != 200:
            if d_res.status_code == 401:
                print("Dhan Token Expired or Invalid (401)! Please generate a fresh token.")
                break
            continue
        d_json = d_res.json()
        if not d_json.get("high") or len(d_json["high"]) < 8:
            continue

        # 5-Minute Intraday Live Data (0-Second Delay)
        i_payload = {
            "securityId": sec_id,
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "interval": "5",
            "fromDate": f"{from_date_intra} 09:15:00",
            "toDate": f"{to_date_intra} 15:30:00"
        }
        i_res = requests.post("https://api.dhan.co/v2/charts/intraday", headers=headers, json=i_payload, timeout=8)
        if i_res.status_code != 200:
            continue
        i_json = i_res.json()
        if not i_json.get("close") or len(i_json["close"]) < 20:
            continue

        df_i = pd.DataFrame({
            "timestamp": pd.to_datetime(i_json["timestamp"], unit="s", utc=True).tz_convert(ist),
            "Open": i_json["open"],
            "High": i_json["high"],
            "Low": i_json["low"],
            "Close": i_json["close"],
            "Volume": i_json["volume"]
        })
        df_i["ema20"] = df_i["Close"].ewm(span=20, adjust=False).mean()

        df_today = df_i[df_i["timestamp"].dt.strftime("%Y-%m-%d") == today_str].copy()
        if len(df_today) < 2:
            continue

        tp = (df_today["High"] + df_today["Low"] + df_today["Close"]) / 3
        df_today["vwap"] = (tp * df_today["Volume"]).cumsum() / df_today["Volume"].cumsum()

        curr = df_today.iloc[-1]
        prev = df_today.iloc[-2]
        cmp = round(float(curr["Close"]), 2)
        c_vwap = round(float(curr["vwap"]), 2)
        c_ema = round(float(curr["ema20"]), 2)
        p_close = float(prev["Close"])
        p_vwap = float(prev["vwap"])

        # Past 8 days highs/lows
        past_highs = d_json["high"][-8:]
        past_lows = d_json["low"][-8:]
        pdh = round(float(past_highs[-1]), 2)
        pdl = round(float(past_lows[-1]), 2)
        r_high = round(float(max(past_highs)), 2)
        r_low = round(float(min(past_lows)), 2)
        range_pct = ((r_high - r_low) / r_low) * 100

        # Strategy 1: 7-8D Range Breakout
        if range_pct <= 7.5:
            if cmp > r_high and cmp > c_vwap:
                signals.append((sym, "7-8D Range Breakout", "BUY", cmp, c_vwap, c_ema, round(r_high * 0.992, 2)))
            elif cmp < r_low and cmp < c_vwap:
                signals.append((sym, "7-8D Range Breakout", "SELL", cmp, c_vwap, c_ema, round(r_low * 1.008, 2)))

        # Strategy 2: PDH / PDL Breakout
        if cmp > pdh and p_close <= pdh and cmp > c_vwap:
            signals.append((sym, "PDH/PDL", "BUY", cmp, c_vwap, c_ema, round(pdh * 0.994, 2)))
        elif cmp < pdl and p_close >= pdl and cmp < c_vwap:
            signals.append((sym, "PDH/PDL", "SELL", cmp, c_vwap, c_ema, round(pdl * 1.006, 2)))

        # Strategy 3: 5m VWAP + 20 EMA Crossover
        if cmp > c_vwap and cmp > c_ema and p_close <= p_vwap:
            signals.append((sym, "5m VWAP + 20 EMA", "BUY", cmp, c_vwap, c_ema, round(float(curr["Low"]) * 0.997, 2)))
        elif cmp < c_vwap and cmp < c_ema and p_close >= p_vwap:
            signals.append((sym, "5m VWAP + 20 EMA", "SELL", cmp, c_vwap, c_ema, round(float(curr["High"]) * 1.003, 2)))

        # Strategy 4: 5m VWAP Cross with Volume
        avg_vol = df_today["Volume"].mean()
        if curr["Volume"] > avg_vol * 1.3:
            if cmp > c_vwap and p_close <= p_vwap:
                signals.append((sym, "5m VWAP Cross", "BUY", cmp, c_vwap, c_ema, round(c_vwap * 0.995, 2)))
            elif cmp < c_vwap and p_close >= p_vwap:
                signals.append((sym, "5m VWAP Cross", "SELL", cmp, c_vwap, c_ema, round(c_vwap * 1.005, 2)))

        time.sleep(0.12)
    except Exception:
        continue

print(f"Total 0-Second Dhan signals found: {len(signals)}")

pushed = 0
for s in signals:
    sym_name, strat, sig_type, cmp, vwap_v, ema_v, sl_v = s
    unique_id = f"{sym_name}_{strat}_{sig_type}"
    if unique_id in existing_keys:
        continue
    payload = {
        "symbol": sym_name,
        "strategy": strat,
        "type": sig_type,
        "cmp": cmp,
        "vwap": vwap_v,
        "ema20": ema_v,
        "sl": sl_v,
        "time": time_str,
        "date": today_str
    }
    res = requests.post(FIREBASE_URL, json=payload, timeout=10)
    if res.status_code == 200:
        pushed += 1

print(f"Done! Pushed {pushed} real-time alerts to MJ Stock.")
