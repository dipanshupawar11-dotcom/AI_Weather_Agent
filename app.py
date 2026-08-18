import os
from datetime import datetime, timedelta

import requests
import streamlit as st

st.set_page_config(
    page_title="AI Weather Agent",
    page_icon="🌦️",
    layout="wide",
)

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def geocode_city(city: str):
    response = requests.get(
        GEO_URL,
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        },
        timeout=15,
    )
    response.raise_for_status()
    results = response.json().get("results", [])

    if not results:
        return None

    location = results[0]
    return {
        "name": location["name"],
        "country": location.get("country", ""),
        "latitude": location["latitude"],
        "longitude": location["longitude"],
    }


def fetch_weather(
    latitude: float,
    longitude: float,
    start_date=None,
    end_date=None,
    forecast_days=8,
):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "timezone": "auto",
    }

    if start_date and end_date:
        params["start_date"] = start_date
        params["end_date"] = end_date
    else:
        params["forecast_days"] = forecast_days

    response = requests.get(WEATHER_URL, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def weather_label(code):
    labels = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        56: "Freezing drizzle",
        57: "Heavy freezing drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Heavy freezing rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Rain showers",
        81: "Rain showers",
        82: "Heavy rain showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail",
    }
    return labels.get(code, "Unknown")


def hourly_rows(data):
    hourly = data.get("hourly", {})
    rows = []

    for i, timestamp in enumerate(hourly.get("time", [])):
        rows.append(
            {
                "Date": timestamp[:10],
                "Time": datetime.fromisoformat(timestamp).strftime("%I:%M %p"),
                "Temperature (°C)": hourly["temperature_2m"][i],
                "Feels Like (°C)": hourly["apparent_temperature"][i],
                "Humidity (%)": hourly["relative_humidity_2m"][i],
                "Rain Chance (%)": hourly["precipitation_probability"][i],
                "Rain (mm)": hourly["precipitation"][i],
                "Wind (km/h)": hourly["wind_speed_10m"][i],
                "Condition": weather_label(hourly["weather_code"][i]),
            }
        )

    return rows


def rows_for_date(rows, selected_date):
    date_text = selected_date.isoformat()
    return [row for row in rows if row["Date"] == date_text]


def get_gemini_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    return os.getenv("GEMINI_API_KEY")


def ask_ai(question, weather_context):
    api_key = get_gemini_key()

    if not api_key:
        return (
            "AI Assistant is not configured yet. Add "
            "`GEMINI_API_KEY` to Streamlit Secrets."
        )

    prompt = f"""
You are a friendly weather assistant.

Rules:
- Answer in simple English, Hindi, or Hinglish depending on the user's language.
- Use the supplied weather data for weather-specific facts.
- Do not invent temperatures, rain chances, or times.
- If the supplied data does not contain enough information, clearly say that.
- You can give practical advice such as whether an umbrella may be useful, but make it clear it is advice based on the supplied forecast.

Weather data:
{weather_context}

User question:
{question}
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.0-flash:generateContent"
    )

    try:
        response = requests.post(
            url,
            params={"key": api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        candidates = payload.get("candidates", [])
        if not candidates:
            return "AI could not generate a response right now."

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return "AI returned an empty response."

        return parts[0].get("text", "AI returned an empty response.")

    except requests.RequestException as exc:
        return f"AI service request failed: {exc}"
    except (KeyError, IndexError, TypeError, ValueError):
        return "AI returned an unexpected response."


st.title("🌦️ AI Weather Agent")
st.caption(
    "City search • 24-hour weather • AI Assistant • 8-day hourly forecast "
    "• Specific date • Date range • Live weather"
)

city = st.text_input(
    "🏙️ Enter City",
    placeholder="Example: Bangalore",
)

if not city.strip():
    st.info("Enter a city above to start.")
    st.stop()

try:
    location = geocode_city(city.strip())
except requests.RequestException as exc:
    st.error(f"Could not connect to the location service: {exc}")
    st.stop()

if not location:
    st.error("City not found. Please enter a valid city name.")
    st.stop()

st.success(
    f"📍 {location['name']}, {location['country']}"
)

try:
    weather = fetch_weather(
        location["latitude"],
        location["longitude"],
        forecast_days=8,
    )
except requests.RequestException as exc:
    st.error(f"Could not load weather data: {exc}")
    st.stop()

all_rows = hourly_rows(weather)

tabs = st.tabs(
    [
        "📅 Today 24 Hours",
        "🤖 Talk with AI Agent",
        "🗓️ 8-Day Forecast",
        "🎯 Specific Date",
        "↔️ Between Dates",
        "📡 Live",
    ]
)

today = datetime.now().date()

with tabs[0]:
    st.subheader("Today's 24-Hour Weather")

    today_rows = rows_for_date(all_rows, today)

    if today_rows:
        st.dataframe(
            today_rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(
            "Today's local-time hourly data is not available in the loaded forecast."
        )

with tabs[1]:
    st.subheader("🤖 Talk with AI Agent")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Ask: Aaj 7 baje baarish hogi?"
    )

    if question:
        st.session_state.chat_history.append(
            {"role": "user", "content": question}
        )

        context = "\n".join(
            str(row) for row in all_rows
        )

        answer = ask_ai(question, context)

        st.session_state.chat_history.append(
            {"role": "assistant", "content": answer}
        )

        st.rerun()

with tabs[2]:
    st.subheader("🗓️ 8-Day Forecast")

    available_dates = sorted(
        {row["Date"] for row in all_rows}
    )

    for date_text in available_dates[:8]:
        selected = [
            row for row in all_rows
            if row["Date"] == date_text
        ]

        date_object = datetime.fromisoformat(date_text).date()

        with st.expander(
            date_object.strftime("%A, %d %B %Y")
        ):
            if selected:
                st.dataframe(
                    selected,
                    use_container_width=True,
                    hide_index=True,
                )

with tabs[3]:
    st.subheader("🎯 Specific Date — 24 Hours")

    available_dates = sorted(
        {
            datetime.fromisoformat(row["Date"]).date()
            for row in all_rows
        }
    )

    if available_dates:
        selected_date = st.date_input(
            "Select date",
            value=available_dates[0],
            min_value=available_dates[0],
            max_value=available_dates[-1],
        )

        selected_rows = rows_for_date(
            all_rows,
            selected_date,
        )

        if selected_rows:
            st.dataframe(
                selected_rows,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No hourly data found for this date.")

with tabs[4]:
    st.subheader("↔️ Between Dates — Hourly Weather")

    min_date = today
    max_date = today + timedelta(days=7)

    col1, col2 = st.columns(2)

    start_date = col1.date_input(
        "Start date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="range_start",
    )

    end_date = col2.date_input(
        "End date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="range_end",
    )

    if start_date > end_date:
        st.warning("End date must be on or after start date.")
    else:
        range_rows = [
            row
            for row in all_rows
            if start_date.isoformat()
            <= row["Date"]
            <= end_date.isoformat()
        ]

        if range_rows:
            st.dataframe(
                range_rows,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No hourly weather data found for this range.")

with tabs[5]:
    st.subheader("📡 Live Weather")

    current = weather.get("current", {})

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Temperature",
        f"{current.get('temperature_2m', 'N/A')} °C",
    )
    col2.metric(
        "Feels Like",
        f"{current.get('apparent_temperature', 'N/A')} °C",
    )
    col3.metric(
        "Humidity",
        f"{current.get('relative_humidity_2m', 'N/A')} %",
    )
    col4.metric(
        "Wind",
        f"{current.get('wind_speed_10m', 'N/A')} km/h",
    )

    st.write(
        "Condition:",
        weather_label(current.get("weather_code")),
    )

    if st.button("🔄 Refresh Weather"):
        st.rerun()

st.divider()
st.caption(
    "Weather data: Open-Meteo • AI: Gemini REST API"
)
