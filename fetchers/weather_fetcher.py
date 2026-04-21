import requests

# Taipei coordinates
TAIPEI_LAT = 25.0330
TAIPEI_LON = 121.5654

# WMO Weather interpretation codes → human-readable
WMO_CODES = {
    0:  "Clear sky",
    1:  "Mainly clear",
    2:  "Partly cloudy",
    3:  "Overcast",
    45: "Foggy",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}

def get_taipei_weather():
    """
    Fetch today's Taipei weather from Open-Meteo (free, no API key needed).
    Returns a dict with weather data for use in the podcast script.
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={TAIPEI_LAT}&longitude={TAIPEI_LON}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "weathercode,windspeed_10m_max"
        "&current_weather=true"
        "&timezone=Asia%2FTaipei"
    )

    try:
        print("🌤️  Fetching Taipei weather from Open-Meteo...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        daily   = data.get("daily", {})
        current = data.get("current_weather", {})

        # Today is index 0 in the daily arrays
        temp_max  = daily.get("temperature_2m_max", [None])[0]
        temp_min  = daily.get("temperature_2m_min", [None])[0]
        precip    = daily.get("precipitation_sum",  [None])[0]
        wind      = daily.get("windspeed_10m_max",  [None])[0]
        wmo_code  = int(daily.get("weathercode", [0])[0] or 0)
        condition = WMO_CODES.get(wmo_code, "Variable conditions")
        current_c = current.get("temperature")

        def to_f(c):
            return round(c * 9 / 5 + 32, 1) if c is not None else None

        weather_info = {
            "condition":  condition,
            "temp_max_c": temp_max,
            "temp_min_c": temp_min,
            "temp_max_f": to_f(temp_max),
            "temp_min_f": to_f(temp_min),
            "current_c":  current_c,
            "current_f":  to_f(current_c),
            "precip_mm":  precip,
            "wind_kmh":   wind,
            "summary": (
                f"{condition}. High {temp_max}°C ({to_f(temp_max)}°F), "
                f"Low {temp_min}°C ({to_f(temp_min)}°F). "
                f"Wind up to {wind} km/h. "
                f"Precipitation: {precip} mm."
            ),
        }

        print(f"  ✔️ Weather: {weather_info['summary']}")
        return weather_info

    except Exception as e:
        print(f"  ⚠️ Could not fetch weather data: {e}")
        return {
            "condition":  "Data unavailable",
            "temp_max_c": None,
            "temp_min_c": None,
            "temp_max_f": None,
            "temp_min_f": None,
            "current_c":  None,
            "current_f":  None,
            "precip_mm":  None,
            "wind_kmh":   None,
            "summary":    "Weather data is currently unavailable. Please check a local forecast.",
        }


if __name__ == "__main__":
    w = get_taipei_weather()
    for k, v in w.items():
        print(f"  {k}: {v}")
