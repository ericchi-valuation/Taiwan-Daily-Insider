import os
import json
import requests
from datetime import datetime, timedelta
import pytz

TAIPEI_TZ = pytz.timezone("Asia/Taipei")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "exchange_rate_cache.json")


def _get_prev_business_day_from(date_str: str) -> str:
    """
    Given a date string (YYYY-MM-DD), return the closest prior business day
    (Mon-Fri) in the same format.
    """
    anchor = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TAIPEI_TZ)
    day = anchor - timedelta(days=1)
    while day.weekday() >= 5:   # 5=Saturday, 6=Sunday
        day -= timedelta(days=1)
    return day.strftime("%Y-%m-%d")


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_to_cache(date_str: str, usd_twd: float, eur_twd: float):
    cache = load_cache()
    cache[date_str] = {"usd_twd": usd_twd, "eur_twd": eur_twd}
    # Keep only the last 10 entries to avoid bloat
    sorted_keys = sorted(cache.keys())
    if len(sorted_keys) > 10:
        for k in sorted_keys[:-10]:
            del cache[k]
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4)
    except Exception as e:
        print(f"  [!] Failed to save cache: {e}")


def get_prev_rates_from_cache(latest_date: str) -> tuple:
    cache = load_cache()
    # Find the largest date in cache that is smaller than latest_date
    earlier_dates = [d for d in cache.keys() if d < latest_date]
    if earlier_dates:
        prev_date = max(earlier_dates)
        return prev_date, cache[prev_date].get("usd_twd"), cache[prev_date].get("eur_twd")
    return None, None, None


def get_exchange_rates():
    """
    Fetch the latest USD->TWD and EUR->TWD exchange rates via the free
    fawazahmed0/currency-api.
    """
    result = {
        "usd_twd":        None,
        "eur_twd":        None,
        "usd_twd_prev":   None,
        "eur_twd_prev":   None,
        "usd_change_pct": None,
        "eur_change_pct": None,
        "high_volatility": False,
        "rate_date":      None,
        "prev_date":      None,
        "summary": "Exchange rate data is currently unavailable."
    }

    VOLATILITY_THRESHOLD = 1.0

    base_url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api"
    latest_usd_url = f"{base_url}@latest/v1/currencies/usd.json"
    latest_eur_url = f"{base_url}@latest/v1/currencies/eur.json"

    latest_date = None

    # -- Fetch today (latest settled rate) --
    latest_success = False
    try:
        print("[*] Fetching latest exchange rates from fawazahmed0 API...")
        
        # USD to TWD
        resp_usd = requests.get(latest_usd_url, timeout=10)
        resp_usd.raise_for_status()
        data_usd = resp_usd.json()
        latest_date = data_usd.get("date")
        usd_twd = data_usd.get("usd", {}).get("twd")
        
        # EUR to TWD
        resp_eur = requests.get(latest_eur_url, timeout=10)
        resp_eur.raise_for_status()
        data_eur = resp_eur.json()
        eur_twd = data_eur.get("eur", {}).get("twd")
        
        if usd_twd and eur_twd:
            result["usd_twd"] = round(usd_twd, 2)
            result["eur_twd"] = round(eur_twd, 2)
            result["rate_date"] = latest_date
            print(f"  [OK] Latest ({latest_date}): 1 USD = {result['usd_twd']} TWD | 1 EUR = {result['eur_twd']} TWD")
            save_to_cache(latest_date, result["usd_twd"], result["eur_twd"])
            latest_success = True
            
    except Exception as e:
        print(f"  [!] Primary source failed ({e}). Attempting fallback open.er-api.com...")

    if not latest_success:
        try:
            resp_fallback = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
            resp_fallback.raise_for_status()
            data_fallback = resp_fallback.json()
            rates = data_fallback.get("rates", {})
            usd_twd = rates.get("TWD")
            usd_eur = rates.get("EUR")
            
            if usd_twd and usd_eur:
                eur_twd = usd_twd / usd_eur
                
                # Parse date from unix timestamp or fallback to today
                unix_time = data_fallback.get("time_last_update_unix")
                if unix_time:
                    latest_date = datetime.fromtimestamp(unix_time, pytz.utc).astimezone(TAIPEI_TZ).strftime("%Y-%m-%d")
                else:
                    latest_date = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")
                
                result["usd_twd"] = round(usd_twd, 2)
                result["eur_twd"] = round(eur_twd, 2)
                result["rate_date"] = latest_date
                print(f"  [OK] Latest (Fallback {latest_date}): 1 USD = {result['usd_twd']} TWD | 1 EUR = {result['eur_twd']} TWD")
                save_to_cache(latest_date, result["usd_twd"], result["eur_twd"])
        except Exception as e2:
            print(f"  [!] Fallback also failed: {e2}")

    # -- Determine previous business day and fetch --
    if result["rate_date"]:
        prev_day_str = _get_prev_business_day_from(result["rate_date"])
        prev_usd_url = f"{base_url}@{prev_day_str}/v1/currencies/usd.json"
        prev_eur_url = f"{base_url}@{prev_day_str}/v1/currencies/eur.json"
        
        historical_success = False
        try:
            print(f"[*] Fetching previous day rates ({prev_day_str})...")
            resp_prev_usd = requests.get(prev_usd_url, timeout=10)
            resp_prev_usd.raise_for_status()
            usd_twd_prev = resp_prev_usd.json().get("usd", {}).get("twd")
            
            resp_prev_eur = requests.get(prev_eur_url, timeout=10)
            resp_prev_eur.raise_for_status()
            eur_twd_prev = resp_prev_eur.json().get("eur", {}).get("twd")
            
            if usd_twd_prev and eur_twd_prev:
                result["usd_twd_prev"] = round(usd_twd_prev, 2)
                result["eur_twd_prev"] = round(eur_twd_prev, 2)
                result["prev_date"] = prev_day_str
                historical_success = True
                print(f"  [OK] Prev day (API): 1 USD = {result['usd_twd_prev']} TWD | 1 EUR = {result['eur_twd_prev']} TWD")
                save_to_cache(prev_day_str, result["usd_twd_prev"], result["eur_twd_prev"])
        except Exception as e:
            print(f"  [!] Historical fetch failed ({e}). Attempting cache fallback...")

        # Cache fallback
        if not historical_success:
            c_date, c_usd, c_eur = get_prev_rates_from_cache(result["rate_date"])
            if c_date and c_usd and c_eur:
                result["usd_twd_prev"] = c_usd
                result["eur_twd_prev"] = c_eur
                result["prev_date"] = c_date
                print(f"  [OK] Prev day (Cache {c_date}): 1 USD = {result['usd_twd_prev']} TWD | 1 EUR = {result['eur_twd_prev']} TWD")
            else:
                print("  [!] No previous rates available in cache.")

    # -- Calculate % change & volatility --
    if result["usd_twd"] and result["usd_twd_prev"]:
        result["usd_change_pct"] = round(
            (result["usd_twd"] - result["usd_twd_prev"]) / result["usd_twd_prev"] * 100, 3
        )
    if result["eur_twd"] and result["eur_twd_prev"]:
        result["eur_change_pct"] = round(
            (result["eur_twd"] - result["eur_twd_prev"]) / result["eur_twd_prev"] * 100, 3
        )

    usd_vol = abs(result["usd_change_pct"]) if result["usd_change_pct"] is not None else 0
    eur_vol = abs(result["eur_change_pct"]) if result["eur_change_pct"] is not None else 0
    result["high_volatility"] = (usd_vol >= VOLATILITY_THRESHOLD or eur_vol >= VOLATILITY_THRESHOLD)

    # -- Build summary string --
    if result["usd_twd"] and result["eur_twd"]:
        trend_usd = ""
        if result["usd_change_pct"] is not None:
            sign = "+" if result["usd_change_pct"] >= 0 else ""
            trend_usd = f" ({sign}{result['usd_change_pct']}% vs prev day)"

        trend_eur = ""
        if result["eur_change_pct"] is not None:
            sign = "+" if result["eur_change_pct"] >= 0 else ""
            trend_eur = f" ({sign}{result['eur_change_pct']}% vs prev day)"

        date_label = f" [as of {result['rate_date']}'s close]" if result["rate_date"] else ""
        prev_label = f" [prev: {result['prev_date']}]" if result["prev_date"] else ""
        result["summary"] = (
            f"1 USD = {result['usd_twd']} TWD{trend_usd}{date_label} | "
            f"1 EUR = {result['eur_twd']} TWD{trend_eur}{prev_label}"
        )
        vol_label = "[!] HIGH VOLATILITY" if result["high_volatility"] else "[+] Low volatility"
        print(f"  {vol_label} -- {result['summary']}")
    elif result["usd_twd"]:
        result["summary"] = f"1 USD = {result['usd_twd']} TWD"

    return result


if __name__ == "__main__":
    rates = get_exchange_rates()
    print("\nFull result:")
    for k, v in rates.items():
        print(f"  {k}: {v}")
