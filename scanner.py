import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta

FIREBASE_URL = "https://mj-stock-15f1b-default-rtdb.asia-southeast1.firebasedatabase.app/alerts.json"

FNO_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "BHARTIARTL.NS",
    "SBIN.NS", "LT.NS", "ITC.NS", "AXISBANK.NS", "KOTAKBANK.NS", "HINDUNILVR.NS",
    "BAJFINANCE.NS", "MARUTI.NS", "M&M.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "BAJAJFINSV.NS", "BAJAJ-AUTO.NS",
    "EICHERMOT.NS", "HEROMOTOCO.NS", "TVSMOTOR.NS", "TRENT.NS", "BEL.NS", "HAL.NS",
    "BHEL.NS", "RECLTD.NS", "PFC.NS", "IRCTC.NS", "INDIGO.NS", "DLF.NS", "GODREJPROP.NS",
    "LODHA.NS", "OBEROIRLTY.NS", "ASIANPAINT.NS", "PIDILITIND.NS", "BRITANNIA.NS",
    "NESTLEIND.NS", "TATACONSUM.NS", "VBL.NS", "DABUR.NS", "MARICO.NS", "COLPAL.NS",
    "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "LUPIN.NS", "AUROPHARMA.NS", "APOLLOHOSP.NS",
    "MAXHEALTH.NS", "FORTIS.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "PERSISTENT.NS",
    "COFORGE.NS", "MPHASIS.NS", "KPITTECH.NS", "TATAELXSI.NS", "INDUSINDBK.NS",
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "AUBANK.NS", "BANDHANBNK.NS", "PNB.NS", "BANKBARODA.NS",
    "CANBK.NS", "UNIONBANK.NS", "CHOLAFIN.NS", "SHRIRAMFIN.NS", "MUTHOOTFIN.NS",
    "MANAPPURAM.NS", "SBILIFE.NS", "HDFCLIFE.NS", "ICICIGI.NS", "SBICARD.NS", "MCX.NS",
    "BSE.NS", "CDSL.NS", "ANGELONE.NS", "JIOFIN.NS", "ETERNAL.NS", "POLYCAB.NS",
    "HAVELLS.NS", "VOLTAS.NS", "BLUESTARCO.NS", "DIXON.NS", "AMBER.NS", "ABB.NS",
    "SIEMENS.NS", "CGPOWER.NS", "CUMMINSIND.NS", "ASTRAL.NS", "SUPREMEIND.NS",
    "GRASIM.NS", "AMBUJACEM.NS", "SHREECEM.NS", "ACC.NS", "DALBHARAT.NS", "UPL.NS",
    "PIIND.NS", "SRF.NS", "DEEPAKNTR.NS", "NAVINFLUOR.NS", "TATACHEM.NS", "GAIL.NS",
    "BPCL.NS", "IOC.NS", "HINDPETRO.NS", "PETRONET.NS", "IGL.NS", "MGL.NS", "TATAPOWER.NS",
    "NHPC.NS", "SJVN.NS", "CESC.NS", "INDUSTOWER.NS", "IDEA.NS", "SAIL.NS", "NMDC.NS",
    "VEDL.NS", "NATIONALUM.NS", "JINDALSTEL.NS", "EXIDEIND.NS", "AMARAJABAT.NS",
    "MOTHERSON.NS", "BOSCHLTD.NS", "MRF.NS", "APOLLOTYRE.NS", "BALKRISIND.NS",
    "ASHOKLEY.NS", "ESCORTS.NS", "CONCOR.NS", "GMRINFRA.NS", "IRFC.NS", "RVNL.NS"
]

ist = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(ist)
today_str = now_ist.strftime("%Y-%m-%d")
time_str = now_ist.strftime("%I:%M %p")

print(f"Starting MJ Stock Scan at {today_str} {time_str} IST...")

daily_data = yf.download(FNO_STOCKS, period="15d", interval="1d", group_by="ticker", progress=False, threads=True)
intra_data = yf.download(FNO_STOCKS, period="2d", interval="5m", group_by="ticker", progress=False, threads=True)

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

for sym in FNO_STOCKS:
    try:
        df_d = daily_data[sym].dropna()
        df_i = intra_data[sym].dropna()
        if len(df_d) < 9 or len(df_i) < 10:
            continue

        df_i_ist = df_i.copy()
        if df_i_ist.index.tz is None:
            df_i_ist.index = df_i_ist.index.tz_localize("UTC").tz_convert(ist)
        else:
            df_i_ist.index = df_i_ist.index.tz_convert(ist)

        df_today = df_i_ist[df_i_ist.index.strftime("%Y-%m-%d") == today_str]
        if len(df_today) < 2:
            continue

        # VWAP & 20 EMA
        tp = (df_today["High"] + df_today["Low"] + df_today["Close"]) / 3
        vwap = (tp * df_today["Volume"]).cumsum() / df_today["Volume"].cumsum()
        ema20 = df_i_ist["Close"].ewm(span=20, adjust=False).mean().loc[df_today.index]

        curr = df_today.iloc[-1]
        prev = df_today.iloc[-2]
        cmp = round(float(curr["Close"]), 2)
        c_vwap = round(float(vwap.iloc[-1]), 2)
        c_ema = round(float(ema20.iloc[-1]), 2)
        p_close = float(prev["Close"])
        p_vwap = float(vwap.iloc[-2])

        # Previous days excluding today
        past_d = df_d[df_d.index.strftime("%Y-%m-%d") < today_str]
        if len(past_d) < 8:
            continue

        pdh = round(float(past_d.iloc[-1]["High"]), 2)
        pdl = round(float(past_d.iloc[-1]["Low"]), 2)

        # 7-8 Days Consolidation Range
        last_8d = past_d.tail(8)
        r_high = round(float(last_8d["High"].max()), 2)
        r_low = round(float(last_8d["Low"].min()), 2)
        range_pct = ((r_high - r_low) / r_low) * 100

        clean_sym = sym.replace(".NS", "")

        # Strategy 1: 7-8D Range Breakout / Breakdown
        if range_pct <= 7.5:
            if cmp > r_high and cmp > c_vwap:
                signals.append((clean_sym, "7-8D Range Breakout", "BUY", cmp, c_vwap, c_ema, round(r_high * 0.992, 2)))
            elif cmp < r_low and cmp < c_vwap:
                signals.append((clean_sym, "7-8D Range Breakout", "SELL", cmp, c_vwap, c_ema, round(r_low * 1.008, 2)))

        # Strategy 2: PDH / PDL Breakout
        if cmp > pdh and p_close <= pdh and cmp > c_vwap:
            signals.append((clean_sym, "PDH/PDL", "BUY", cmp, c_vwap, c_ema, round(pdh * 0.994, 2)))
        elif cmp < pdl and p_close >= pdl and cmp < c_vwap:
            signals.append((clean_sym, "PDH/PDL", "SELL", cmp, c_vwap, c_ema, round(pdl * 1.006, 2)))

        # Strategy 3: 5m VWAP + 20 EMA Crossover
        if cmp > c_vwap and cmp > c_ema and (p_close <= p_vwap):
            signals.append((clean_sym, "5m VWAP + 20 EMA", "BUY", cmp, c_vwap, c_ema, round(float(curr["Low"]) * 0.997, 2)))
        elif cmp < c_vwap and cmp < c_ema and (p_close >= p_vwap):
            signals.append((clean_sym, "5m VWAP + 20 EMA", "SELL", cmp, c_vwap, c_ema, round(float(curr["High"]) * 1.003, 2)))

        # Strategy 4: Pure 5m VWAP Cross with volume
        avg_vol = df_today["Volume"].mean()
        if curr["Volume"] > avg_vol * 1.3:
            if cmp > c_vwap and p_close <= p_vwap:
                signals.append((clean_sym, "5m VWAP Cross", "BUY", cmp, c_vwap, c_ema, round(c_vwap * 0.995, 2)))
            elif cmp < c_vwap and p_close >= p_vwap:
                signals.append((clean_sym, "5m VWAP Cross", "SELL", cmp, c_vwap, c_ema, round(c_vwap * 1.005, 2)))

    except Exception:
        continue

print(f"Total signals found in this run: {len(signals)}")

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
    print(f"Pushed {unique_id} -> Status {res.status_code}")
    if res.status_code == 200:
        pushed += 1

print(f"Done! New alerts pushed to Firebase: {pushed}")
        
