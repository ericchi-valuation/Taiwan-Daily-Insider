import requests
from datetime import datetime, timedelta
import pytz

TAIPEI_TZ = pytz.timezone("Asia/Taipei")


def _get_prev_business_day_str():
    """
    Return the most recent past business day (Mon-Fri) in YYYY-MM-DD format
    (Taipei time). Needed because the ExchangeRate-API may not update on weekends.
    """
    day = datetime.now(TAIPEI_TZ) - timedelta(days=1)
    while day.weekday() >= 5:   # 5=Saturday, 6=Sunday
        day -= timedelta(days=1)
    return day.strftime("%Y-%m-%d")


def get_exchange_rates():
    """
    Fetch the latest USD→TWD and EUR→TWD exchange rates via open.er-api.com.
    Also captures yesterday's rates to calculate daily % change and flag
    high volatility (>= 1%), enabling smart commentary in the script generator.

    Returns a dict with:
      - usd_twd, eur_twd          : today's rates
      - usd_twd_prev, eur_twd_prev: previous business day's rates (may be None)
      - usd_change_pct, eur_change_pct: % change vs. prev day
      - high_volatility           : True if either pair moved >= 1%
      - summary                   : one-line summary for the script
    """
    result = {
        "usd_twd":        None,
        "eur_twd":        None,
        "usd_twd_prev":   None,
        "eur_twd_prev":   None,
        "usd_change_pct": None,
        "eur_change_pct": None,
        "high_volatility": False,
        "summary": "Exchange rate data is currently unavailable."
    }

    VOLATILITY_THRESHOLD = 1.0   # percent

    prev_day_str = _get_prev_business_day_str()

    # ── Fetch today ───────────────────────────────────────────────────────────
    try:
        print("💱 Fetching today's USD→TWD rate from ExchangeRate-API...")
        resp_usd = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        resp_usd.raise_for_status()
        data_usd = resp_usd.json()
        usd_twd = data_usd.get("rates", {}).get("TWD")
        if usd_twd:
            result["usd_twd"] = round(usd_twd, 2)

        resp_eur = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=10)
        resp_eur.raise_for_status()
        data_eur = resp_eur.json()
        eur_twd = data_eur.get("rates", {}).get("TWD")
        if eur_twd:
            result["eur_twd"] = round(eur_twd, 2)

        if result["usd_twd"] and result["eur_twd"]:
            print(f"  ✔️  Today: 1 USD = {result['usd_twd']} TWD | 1 EUR = {result['eur_twd']} TWD")

    except Exception as e:
        print(f"  ⚠️  Could not fetch today's exchange rates: {e}")

    # ── Fetch previous business day via Frankfurter (covers TWD via cross rate) ──
    # open.er-api.com free tier does NOT support historical queries,
    # so we use Frankfurter (EUR base) and derive TWD via USD cross.
    # Frankfurter does NOT have TWD, so we fall back to a lightweight approach:
    # store previous USD/TWD from the "time_last_update_utc" field and compare
    # against today, OR simply re-query the same endpoint which returns a
    # "time_next_update_unix" that we can compare.
    # Simplest reliable method: use the `data_usd["time_last_update_utc"]` date
    # to detect if rates are actually from today; we always get the "latest" so
    # prev-day comparison is done via the exchangerate.host historical endpoint.
    try:
        print(f"💱 Fetching previous business day's rates ({prev_day_str}) for volatility check...")
        hist_usd = requests.get(
            f"https://api.exchangerate.host/historical?date={prev_day_str}&base=USD&symbols=TWD",
            timeout=10
        )
        hist_eur = requests.get(
            f"https://api.exchangerate.host/historical?date={prev_day_str}&base=EUR&symbols=TWD",
            timeout=10
        )

        if hist_usd.status_code == 200:
            usd_prev = hist_usd.json().get("rates", {}).get("TWD")
            if usd_prev:
                result["usd_twd_prev"] = round(float(usd_prev), 2)

        if hist_eur.status_code == 200:
            eur_prev = hist_eur.json().get("rates", {}).get("TWD")
            if eur_prev:
                result["eur_twd_prev"] = round(float(eur_prev), 2)

        if result["usd_twd_prev"] and result["eur_twd_prev"]:
            print(f"  ✔️  Prev day: 1 USD = {result['usd_twd_prev']} TWD | 1 EUR = {result['eur_twd_prev']} TWD")

    except Exception as e:
        print(f"  ⚠️  Could not fetch previous day's exchange rates: {e}")

    # ── Calculate % change & volatility ──────────────────────────────────────
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

    # ── Build summary string ──────────────────────────────────────────────────
    if result["usd_twd"] and result["eur_twd"]:
        trend_usd = ""
        if result["usd_change_pct"] is not None:
            sign = "+" if result["usd_change_pct"] >= 0 else ""
            trend_usd = f" ({sign}{result['usd_change_pct']}% vs prev day)"

        trend_eur = ""
        if result["eur_change_pct"] is not None:
            sign = "+" if result["eur_change_pct"] >= 0 else ""
            trend_eur = f" ({sign}{result['eur_change_pct']}% vs prev day)"

        result["summary"] = (
            f"1 USD = {result['usd_twd']} TWD{trend_usd} | "
            f"1 EUR = {result['eur_twd']} TWD{trend_eur}"
        )
        vol_label = "⚠️  HIGH VOLATILITY" if result["high_volatility"] else "✅ Low volatility"
        print(f"  {vol_label} — {result['summary']}")
    elif result["usd_twd"]:
        result["summary"] = f"1 USD = {result['usd_twd']} TWD"

    return result


if __name__ == "__main__":
    rates = get_exchange_rates()
    print("\nFull result:")
    for k, v in rates.items():
        print(f"  {k}: {v}")
