import os
from datetime import datetime, timedelta

import requests
import streamlit as st
from google import genai

st.set_page_config(
    page_title="AI Weather Agent",
    page_icon="🌦️",
    layout="wide"
)

WEATHER_CODES = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Cloudy",
    45: "Fog", 48: "Depositing Rime Fog",
    51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
    56: "Light Freezing Drizzle", 57: "Dense Freezing Drizzle",
    61: "Light Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    66: "Light Freezing Rain", 67: "Heavy Freezing Rain",
    71: "Light Snow", 73: "Moderate Snow", 75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Rain Showers", 81: "Moderate Rain Showers", 82: "Heavy Rain Showers",
    85: "Light Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Light Hail",
    99: "Thunderstorm with Heavy Hail"
}

GEMINI_MODEL = "gemini-3.6-flash"

def condition(code):
    return WEATHER_CODES.get(code, "Unknown")

@st.cache_data(ttl=600)
def get_city(city_name):
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={
            "name": city_name,
            "count": 1,
            "language": "en",
            "format": "json"
        },
        timeout=10
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        return None
    city = results[0]
    return {
        "name": city.get("name"),
        "country": city.get("country"),
        "latitude": city.get("latitude"),
        "longitude": city.get("longitude"),
        "timezone": city.get("timezone")
    }

@st.cache_data(ttl=600)
def get_weather(latitude, longitude, timezone):
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "forecast_days": 8,
            "current": ",".join([
                "temperature_2m", "apparent_temperature",
                "relative_humidity_2m", "rain", "precipitation",
                "wind_speed_10m", "weather_code"
            ]),
            "hourly": ",".join([
                "temperature_2m", "apparent_temperature",
                "relative_humidity_2m", "precipitation_probability",
                "rain", "wind_speed_10m", "weather_code"
            ]),
            "daily": ",".join([
                "weather_code", "temperature_2m_max", "temperature_2m_min",
                "apparent_temperature_max", "apparent_temperature_min",
                "rain_sum", "precipitation_probability_max",
                "wind_speed_10m_max", "sunrise", "sunset"
            ])
        },
        timeout=15
    )
    response.raise_for_status()
    return response.json()

def weather_context(city, weather):
    d = weather["daily"]
    parts = [
        f"City: {city['name']}",
        f"Country: {city['country']}",
        f"Timezone: {city['timezone']}",
        "\n8-DAY FORECAST:"
    ]
    for i, date in enumerate(d["time"]):
        day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        parts.append(f"""
Date: {date}
Day: {day}
Condition: {condition(d['weather_code'][i])}
Maximum Temperature: {d['temperature_2m_max'][i]} °C
Minimum Temperature: {d['temperature_2m_min'][i]} °C
Feels Like Maximum: {d['apparent_temperature_max'][i]} °C
Feels Like Minimum: {d['apparent_temperature_min'][i]} °C
Total Rain: {d['rain_sum'][i]} mm
Rain Probability: {d['precipitation_probability_max'][i]} %
Maximum Wind: {d['wind_speed_10m_max'][i]} km/h
Sunrise: {d['sunrise'][i]}
Sunset: {d['sunset'][i]}
""")
    return "\n".join(parts)

def ask_gemini(prompt):
    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if not api_key:
        return "⚠️ Gemini API key is not configured. Add GEMINI_API_KEY in Streamlit Secrets."
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text.strip() if response and response.text else "Gemini returned an empty response."
    except Exception as e:
        return f"❌ Gemini error: {e}"

def daily_table(weather):
    d = weather["daily"]
    rows = []
    for i, date in enumerate(d["time"]):
        rows.append({
            "Date": date,
            "Day": datetime.strptime(date, "%Y-%m-%d").strftime("%A"),
            "Condition": condition(d["weather_code"][i]),
            "Max °C": d["temperature_2m_max"][i],
            "Min °C": d["temperature_2m_min"][i],
            "Rain mm": d["rain_sum"][i],
            "Rain Chance %": d["precipitation_probability_max"][i],
            "Max Wind km/h": d["wind_speed_10m_max"][i],
        })
    return rows

st.title("🌦️ AI Weather Agent")
st.caption("Current weather • 8-day forecast • Date search • Live refresh • Gemini AI")

with st.sidebar:
    st.header("📍 Location")
    city_name = st.text_input("Enter city", placeholder="e.g. Bangalore")

    search = st.button("🔍 Check Weather", use_container_width=True)

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if search and city_name.strip():
    try:
        with st.spinner("Finding city..."):
            city = get_city(city_name.strip())
        if city is None:
            st.error("City not found. Try another city.")
        else:
            st.session_state["city"] = city
            st.session_state["weather"] = get_weather(
                city["latitude"], city["longitude"], city["timezone"]
            )
    except Exception as e:
        st.error(f"Could not fetch weather: {e}")

city = st.session_state.get("city")
weather = st.session_state.get("weather")

if not city or not weather:
    st.info("👈 Enter a city in the sidebar and click **Check Weather**.")
    st.stop()

current = weather["current"]

st.subheader(f"📍 {city['name']}, {city['country']}")
st.caption(f"Timezone: {city['timezone']} • Updated: {current['time']}")

cols = st.columns(6)
metrics = [
    ("🌡️ Temperature", f"{current['temperature_2m']} °C"),
    ("🤒 Feels Like", f"{current['apparent_temperature']} °C"),
    ("💧 Humidity", f"{current['relative_humidity_2m']} %"),
    ("🌧️ Rain", f"{current['rain']} mm"),
    ("💨 Wind", f"{current['wind_speed_10m']} km/h"),
    ("🌤️ Condition", condition(current["weather_code"]))
]
for col, (label, value) in zip(cols, metrics):
    col.metric(label, value)

tab1, tab2, tab3, tab4 = st.tabs([
    "📅 8-Day Forecast",
    "🔎 Specific Date",
    "⏱️ Live Mode",
    "🤖 AI Weather Agent"
])

with tab1:
    st.subheader("Next 8 Days")
    st.dataframe(
        daily_table(weather),
        use_container_width=True,
        hide_index=True
    )

    d = weather["daily"]
    st.subheader("🌅 Sunrise & Sunset")
    for i, date in enumerate(d["time"]):
        with st.expander(f"{date} — {datetime.strptime(date, '%Y-%m-%d').strftime('%A')}"):
            a, b, c, e = st.columns(4)
            a.write(f"**Condition:** {condition(d['weather_code'][i])}")
            b.write(f"**Sunrise:** {d['sunrise'][i]}")
            c.write(f"**Sunset:** {d['sunset'][i]}")
            e.write(f"**Rain:** {d['rain_sum'][i]} mm")

with tab2:
    dates = weather["daily"]["time"]
    selected = st.date_input(
        "Select a date",
        value=datetime.strptime(dates[0], "%Y-%m-%d").date(),
        min_value=datetime.strptime(dates[0], "%Y-%m-%d").date(),
        max_value=datetime.strptime(dates[-1], "%Y-%m-%d").date()
    )
    selected_date = selected.strftime("%Y-%m-%d")
    i = dates.index(selected_date)
    d = weather["daily"]

    st.subheader(f"📅 {selected_date}")
    a, b, c = st.columns(3)
    a.metric("🌡️ Maximum", f"{d['temperature_2m_max'][i]} °C")
    b.metric("🥶 Minimum", f"{d['temperature_2m_min'][i]} °C")
    c.metric("☔ Rain Chance", f"{d['precipitation_probability_max'][i]} %")

    st.write(f"**Condition:** {condition(d['weather_code'][i])}")
    st.write(f"**Total Rain:** {d['rain_sum'][i]} mm")
    st.write(f"**Maximum Wind:** {d['wind_speed_10m_max'][i]} km/h")
    st.write(f"**Sunrise:** {d['sunrise'][i]}")
    st.write(f"**Sunset:** {d['sunset'][i]}")

    hourly = weather["hourly"]
    hourly_rows = []
    for j, t in enumerate(hourly["time"]):
        if t.startswith(selected_date):
            hourly_rows.append({
                "Time": t.split("T")[1],
                "Temperature °C": hourly["temperature_2m"][j],
                "Feels Like °C": hourly["apparent_temperature"][j],
                "Humidity %": hourly["relative_humidity_2m"][j],
                "Rain Chance %": hourly["precipitation_probability"][j],
                "Rain mm": hourly["rain"][j],
                "Wind km/h": hourly["wind_speed_10m"][j],
                "Condition": condition(hourly["weather_code"][j])
            })
    st.subheader("⏰ 24-Hour Weather")
    st.dataframe(hourly_rows, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("🔴 Live Weather")
    st.write("Click refresh to fetch the latest weather. The cloud app may also rerun when refreshed.")
    if st.button("🔄 Refresh Live Weather"):
        st.cache_data.clear()
        st.session_state["weather"] = get_weather(
            city["latitude"], city["longitude"], city["timezone"]
        )
        st.rerun()

    current = st.session_state["weather"]["current"]
    a, b, c, d = st.columns(4)
    a.metric("Temperature", f"{current['temperature_2m']} °C")
    b.metric("Feels Like", f"{current['apparent_temperature']} °C")
    c.metric("Humidity", f"{current['relative_humidity_2m']} %")
    d.metric("Wind", f"{current['wind_speed_10m']} km/h")
    st.info(f"Last updated: {current['time']}")

with tab4:
    st.subheader("🤖 Ask the AI Weather Agent")
    question = st.text_input(
        "Ask in English, Hindi or Hinglish",
        placeholder="Kal umbrella leke jau?"
    )
    if st.button("🤖 Ask Gemini"):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            prompt = f"""
You are an AI Weather Agent.

Use ONLY the weather data below.

{weather_context(city, weather)}

User question:
{question}

Rules:
- Understand English, Hindi and Hinglish.
- Answer in the user's language.
- Never invent weather data.
- For umbrella/raincoat questions, answer YES or NO first.
- For rain questions, mention rain probability and rainfall when useful.
- For hottest/coldest/rainiest day questions, compare all 8 days.
- For outdoor activity questions, consider rain, temperature, wind and condition.
- If the requested date is outside the 8-day forecast, say the available forecast is only the displayed 8 days.
- If unrelated to weather, say you can only answer weather-related questions.
- Keep the answer concise and practical.
"""
            with st.spinner("Gemini is thinking..."):
                st.markdown(ask_gemini(prompt))
