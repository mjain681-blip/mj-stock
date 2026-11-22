import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone, timedelta

FIREBASE_URL = "https://mj-stock-15f1b-default-rtdb.asia-southeast1.firebasedatabase.app/mj_eod_scanners.json"

# NSE F&O स्टॉक्स की लिस्ट (100% फ्री NSE या fallback से)
def get_fno_symbols():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        res = session.get("https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json().get("data", [])
            syms = [item["symbol"] for item in data if item.get("symbol") and "NIFTY" not in item["symbol"]]
            if len(syms) > 100:
                return sorted(list(set(syms)))
    except Exception as e:
        print("NSE direct fetch fallback:", e)

    # बैकअप F&O लिस्ट (अगर NSE API ब्लॉक करे)
    url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
    try:
        df = pd.read_csv(url)
        col = [c for c in df.columns if "SYMBOL" in c.upper()][0]
        syms = [str(s).strip() for s in df[col].dropna() if "NIFTY" not in str(s).upper() and str(s).strip().isalpha()]
        if len(syms) > 100:
            return sorted(list(set(syms)))
    except Exception as e:
        print("CSV fallback error:", e)
    return []

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def main():
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    print(f"Running MJ EOD Scanner at {now_ist.strftime('%d-%b-%Y %I:%M %p IST')}")

    symbols = get_fno_symbols()
    print(f"Total F&O symbols loaded: {len(symbols)}")
    if not symbols:
        return

    tickers = [f"{s}.NS" for s in symbols]

    # 1. डेली डेटा एक साथ डाउनलोड (260 दिन ताकि 200 EMA सटीक निकले)
    daily_raw = yf.download(tickers, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)

    # 2. इंट्राडे 1-Hour डेटा (आख़िरी 1:30 PM - 3:30 PM 2-Hour कैंडल के लिए)
    intra_raw = yf.download(tickers, period="15d", interval="60m", group_by="ticker", threads=True, progress=False)

    results = {
        "updated_at": now_ist.strftime("%d-%b-%Y %I:%M %p IST"),
        "market_date": "",
        "s1_200ema_squeeze_up": [],
        "s2_200ema_breakdown": [],
        "s3_next_day_squeeze": [],
        "s4_consolidation_7d": [],
        "s5_7days_range_bound": [],
        "s6_two_hour_close": []
    }

    latest_candle_date = None

    for sym in symbols:
        tkr = f"{sym}.NS"
        try:
            df = daily_raw[tkr].dropna(subset=["Close", "High", "Low", "Volume"]).copy()
        except Exception:
            continue

        if len(df) < 205:
            continue

        last_date_str = df.index[-1].strftime("%d-%b-%Y")
        if latest_candle_date is None:
            latest_candle_date = last_date_str

        # इंडिकेटर्स
        df["ema20"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["ema50"] = df["Close"].ewm(span=50, adjust=False).mean()
        df["ema200"] = df["Close"].ewm(span=200, adjust=False).mean()
        df["rsi14"] = calc_rsi(df["Close"], 14)
        df["atr14"] = calc_atr(df, 14)
        df["atr14_sma10"] = df["atr14"].rolling(10).mean()
        df["range"] = df["High"] - df["Low"]
        df["range_sma7"] = df["range"].rolling(7).mean()

        bb_mid = df["Close"].rolling(20).mean()
        bb_std = df["Close"].rolling(20).std()
        df["bbw"] = ((bb_mid + 2 * bb_std) - (bb_mid - 2 * bb_std)) / bb_mid
        df["bbw_sma10"] = df["bbw"].rolling(10).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        pct = round(((last["Close"] - prev["Close"]) / prev["Close"]) * 100, 2)

        item = {
            "symbol": sym,
            "close": round(float(last["Close"]), 2),
            "pct": pct,
            "pdh": round(float(last["High"]), 2),
            "pdl": round(float(last["Low"]), 2),
            "vol": int(last["Volume"])
        }

        max5_h = df["High"].tail(5).max()
        min5_l = df["Low"].tail(5).min()
        range5_pct = (max5_h - min5_l) / last["Close"]

        # 1. MJ 200EMA TIGHT SQUEEZE BREAKOUT (Bullish)
        if (
            last["Close"] > last["ema200"] and
            last["Close"] <= last["ema200"] * 1.03 and
            last["ema20"] > last["ema50"] and
            range5_pct <= 0.045 and
            last["rsi14"] >= 50 and
            last["atr14"] < df["atr14_sma10"].iloc[-2] and
            last["Close"] > last["ema20"]
        ):
            results["s1_200ema_squeeze_up"].append(item)

        # 2. MJ 200EMA TIGHT BREAKDOWN (Bearish - 0.95 & 0.060)
        if (
            last["Close"] < last["ema200"] and
            last["Close"] >= last["ema200"] * 0.95 and
            last["ema20"] < last["ema50"] and
            range5_pct <= 0.060 and
            last["rsi14"] <= 50 and
            last["atr14"] < df["atr14_sma10"].iloc[-2] and
            last["Close"] < last["ema20"]
        ):
            results["s2_200ema_breakdown"].append(item)

        # 3. MJ NEXT-DAY F&O SQUEEZE
        if (
            last["range"] < (last["range_sma7"] * 0.70) and
            last["bbw"] < last["bbw_sma10"]
        ):
            results["s3_next_day_squeeze"].append(item)

        # 4. MJ CONSOLIDATION 7 DAY (<= 1.04 i.e. 4% Box)
        max7_h = df["High"].tail(7).max()
        min7_l = df["Low"].tail(7).min()
        if max7_h <= (min7_l * 1.04):
            results["s4_consolidation_7d"].append(item)

        # 5. 7 DAYS RANGE BOUND (पिछले 7 दिनों के High/Low के अंदर क्लोज़ + Close > 50)
        if len(df) >= 9 and last["Close"] > 50:
            c0 = df["Close"].iloc[-1]
            c1 = df["Close"].iloc[-2]
            in_bounds = (
                c0 < df["High"].iloc[-2] and c0 > df["Low"].iloc[-2] and
                all(c1 < df["High"].iloc[-k] and c1 > df["Low"].iloc[-k] for k in range(3, 9))
            )
            if in_bounds:
                results["s5_7days_range_bound"].append(item)

        # 6. 2 HOUR CLOSE (सिर्फ़ मार्केट बंद होने के आख़िरी 2 घंटे: 1:30 PM - 3:30 PM IST)
        try:
            idf = intra_raw[tkr].dropna(subset=["High", "Low", "Close"]).copy()
            if len(idf) >= 35:
                if idf.index.tz is None:
                    idf.index = idf.index.tz_localize("UTC").tz_convert(ist)
                else:
                    idf.index = idf.index.tz_convert(ist)

                # हर दिन को 2-घंटे के सेशन में बांटें: (9:15-11:15), (11:15-13:15), (13:15-15:30 आख़िरी 2 घंटे)
                idf["date"] = idf.index.date
                idf["hour"] = idf.index.hour
                idf["slot"] = np.where(idf["hour"] < 11, 1, np.where(idf["hour"] < 13, 2, 3))

                df_2h = idf.groupby(["date", "slot"], as_index=False).agg({
                    "High": "max",
                    "Low": "min",
                    "Close": "last"
                }).sort_values(["date", "slot"]).reset_index(drop=True)

                if len(df_2h) >= 16:
                    df_2h["atr14"] = calc_atr(df_2h, 14)
                    last_2h = df_2h.iloc[-1]
                    # कन्फर्म करें कि आख़िरी बार दिन का slot 3 (1:30 PM - 3:30 PM) ही है
                    if last_2h["slot"] == 3 and (last_2h["High"] - last_2h["Low"]) < (last_2h["atr14"] * 0.40):
                        results["s6_two_hour_close"].append(item)
        except Exception:
            pass

    results["market_date"] = latest_candle_date or ""
    requests.put(FIREBASE_URL, json=results)
    print("Firebase updated successfully for date:", results["market_date"])

if __name__ == "__main__":
    main()
    
