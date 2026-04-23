import requests

def get_exchange_rates():
    """
    Fetch the latest USD to TWD and EUR to TWD exchange rates
    using the free ExchangeRate-API.
    """
    url = "https://open.er-api.com/v6/latest/USD"
    
    try:
        print("💱 Fetching exchange rates from ExchangeRate-API...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        rates = data.get("rates", {})
        usd_twd = rates.get("TWD")
        
        if usd_twd:
            usd_twd = round(usd_twd, 2)
            
            # Fetch EUR to TWD separately for accuracy
            resp_eur = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=10)
            if resp_eur.status_code == 200:
                data_eur = resp_eur.json()
                eur_twd = round(data_eur.get("rates", {}).get("TWD", 0), 2)
            else:
                eur_twd = None
                
            exchange_info = {
                "usd_twd": usd_twd,
                "eur_twd": eur_twd,
                "summary": f"1 USD = {usd_twd} TWD | 1 EUR = {eur_twd} TWD" if eur_twd else f"1 USD = {usd_twd} TWD"
            }
            print(f"  ✔️ Rates: {exchange_info['summary']}")
            return exchange_info
            
    except Exception as e:
        print(f"  ⚠️ Could not fetch exchange rates: {e}")
        
    return {
        "usd_twd": None,
        "eur_twd": None,
        "summary": "Exchange rate data is currently unavailable."
    }

if __name__ == "__main__":
    rates = get_exchange_rates()
    for k, v in rates.items():
        print(f"  {k}: {v}")
