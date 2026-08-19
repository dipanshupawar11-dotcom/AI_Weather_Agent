import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="AI Weather Agent",
    page_icon="🌦️",
    layout="wide"
)


# =========================================================
# API URLs
# =========================================================

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


# =========================================================
# WEATHER FIELDS
# =========================================================

HOURLY_FIELDS = ",".join([
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
])


CURRENT_FIELDS = ",".join([
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
])


# =========================================================
# GEOCODING
# =========================================================

def geocode_city(city):

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


# =========================================================
# FETCH WEATHER
# =========================================================

def fetch_weather(latitude, longitude):

    response = requests.get(
        WEATHER_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "hourly": HOURLY_FIELDS,
            "current": CURRENT_FIELDS,
            "forecast_days": 8,
            "timezone": "auto",
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if "hourly" not in data:
        raise ValueError("Weather API returned no hourly data.")

    return data


# =========================================================
# WEATHER LABEL
# =========================================================

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


# =========================================================
# HOURLY ROWS
# =========================================================

def hourly_rows(data):

    hourly = data["hourly"]

    rows = []

    for i, timestamp in enumerate(hourly["time"]):

        local_dt = datetime.fromisoformat(timestamp)

        rows.append({
            "Date": local_dt.date().isoformat(),
            "Time": local_dt.strftime("%I:%M %p"),
            "Temperature (°C)": hourly["temperature_2m"][i],
            "Feels Like (°C)": hourly["apparent_temperature"][i],
            "Humidity (%)": hourly["relative_humidity_2m"][i],
            "Rain Chance (%)": hourly["precipitation_probability"][i],
            "Rain (mm)": hourly["precipitation"][i],
            "Wind (km/h)": hourly["wind_speed_10m"][i],
            "Condition": weather_label(
                hourly["weather_code"][i]
            ),
        })

    return rows


# =========================================================
# GET TODAY
# =========================================================

def get_api_today(data):

    timezone_name = data.get("timezone")

    if timezone_name:

        try:
            return datetime.now(
                ZoneInfo(timezone_name)
            ).date()

        except Exception:
            pass

    return datetime.fromisoformat(
        data["hourly"]["time"][0]
    ).date()


# =========================================================
# ROWS FOR SPECIFIC DATE
# =========================================================

def rows_for_date(rows, selected_date):

    target = selected_date.isoformat()

    return [
        row
        for row in rows
        if row["Date"] == target
    ]


# =========================================================
# NEXT 24 HOURS
# =========================================================

def next_24_hour_rows(rows, data):

    timezone_name = data.get("timezone")

    try:

        if timezone_name:
            now_local = datetime.now(
                ZoneInfo(timezone_name)
            )
        else:
            now_local = datetime.now()

    except Exception:

        now_local = datetime.now()

    # Remove timezone for comparison with API local timestamps
    now_naive = now_local.replace(
        tzinfo=None,
        minute=0,
        second=0,
        microsecond=0
    )

    all_rows = []

    for row in rows:

        try:

            row_dt = datetime.strptime(
                f'{row["Date"]} {row["Time"]}',
                "%Y-%m-%d %I:%M %p"
            )

            all_rows.append(
                (row_dt, row)
            )

        except Exception:
            continue

    all_rows.sort(
        key=lambda x: x[0]
    )

    if not all_rows:
        return []

    # Find current forecast hour
    start_index = None

    for index, (row_dt, row) in enumerate(all_rows):

        if row_dt >= now_naive:
            start_index = index
            break

    # If current time is after all available rows
    if start_index is None:
        return []

    return [
        row
        for _, row in all_rows[
            start_index:start_index + 24
        ]
    ]


# =========================================================
# GEMINI API KEY
# =========================================================

def get_gemini_key():

    try:

        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]

    except Exception:
        pass

    return os.getenv("GEMINI_API_KEY")


# =========================================================
# AI WEATHER ASSISTANT
# =========================================================

def ask_ai(question, rows, location_name):

    api_key = get_gemini_key()

    if not api_key:

        return (
            "AI Assistant is not configured yet. "
            "Add `GEMINI_API_KEY` to Streamlit Secrets."
        )

    weather_context = "\n".join(
        str(row)
        for row in rows
    )

    prompt = f"""
You are the AI weather assistant for {location_name}.

Rules:

- Reply in the same language style as the user:
  English, Hindi, or Hinglish.
- Use the supplied hourly weather data for weather facts.
- Never invent a temperature, rain chance, time, or condition.
- If the requested date/time is not in the supplied data,
  say that clearly.
- You may give practical advice based on the forecast.
- Keep answers friendly and concise.

Hourly weather data:

{weather_context}

User question:

{question}
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-3.6-flash:generateContent"
    )

    try:

        response = requests.post(
            url,
            params={
                "key": api_key
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            },
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

        candidates = payload.get(
            "candidates",
            []
        )

        if not candidates:

            return (
                "AI could not generate "
                "a response right now."
            )

        parts = candidates[0].get(
            "content",
            {}
        ).get(
            "parts",
            []
        )

        if not parts:

            return (
                "AI returned an empty response."
            )

        return parts[0].get(
            "text",
            "AI returned an empty response."
        )

    except requests.HTTPError as exc:

        try:

            details = response.json().get(
                "error",
                {}
            ).get(
                "message"
            )

        except Exception:

            details = None

        if details:

            return (
                f"Gemini API error: {details}"
            )

        return (
            f"Gemini API request failed: {exc}"
        )

    except requests.RequestException as exc:

        return (
            f"AI service request failed: {exc}"
        )


# =========================================================
# APP TITLE
# =========================================================

st.title("🌦️ AI Weather Agent")

st.caption(
    "City search • Live Weather • Next 24 Hours • "
    "AI Assistant • 8-Day Forecast • Specific Date • "
    "Between Dates"
)


# =========================================================
# CITY INPUT
# =========================================================

city = st.text_input(
    "🏙️ Enter City",
    placeholder="Example: Bhopal"
)


if not city.strip():

    st.info(
        "Enter a city above to start."
    )

    st.stop()


# =========================================================
# FIND CITY
# =========================================================

try:

    location = geocode_city(
        city.strip()
    )

except requests.RequestException as exc:

    st.error(
        f"Could not connect to the location service: {exc}"
    )

    st.stop()


if not location:

    st.error(
        "City not found. Please enter a valid city name."
    )

    st.stop()


st.success(
    f"📍 {location['name']}, {location['country']}"
)


# =========================================================
# LOAD WEATHER
# =========================================================

try:

    weather = fetch_weather(
        location["latitude"],
        location["longitude"]
    )

except requests.RequestException as exc:

    st.error(
        f"Could not load weather data: {exc}"
    )

    st.stop()

except ValueError as exc:

    st.error(str(exc))

    st.stop()


# =========================================================
# PREPARE DATA
# =========================================================

rows = hourly_rows(weather)

available_dates = sorted(
    {
        row["Date"]
        for row in rows
    }
)


if not available_dates:

    st.error(
        "No hourly forecast dates were returned."
    )

    st.stop()


api_today = get_api_today(
    weather
)


# =========================================================
# TABS
# =========================================================

tabs = st.tabs([
    "📡 Live Weather",
    "🕐 Next 24 Hours",
    "🤖 Talk with AI Agent",
    "🗓️ 8-Day Forecast",
    "🎯 Specific Date",
    "↔️ Between Dates",
])


# =========================================================
# TAB 1 — LIVE WEATHER
# =========================================================

with tabs[0]:

    st.subheader(
        "📡 Live Weather"
    )

    current = weather.get(
        "current",
        {}
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Temperature",
        f'{current.get("temperature_2m", "N/A")} °C'
    )

    col2.metric(
        "Feels Like",
        f'{current.get("apparent_temperature", "N/A")} °C'
    )

    col3.metric(
        "Humidity",
        f'{current.get("relative_humidity_2m", "N/A")} %'
    )

    col4.metric(
        "Wind",
        f'{current.get("wind_speed_10m", "N/A")} km/h'
    )

    st.write(
        "🌤️ Condition:",
        weather_label(
            current.get("weather_code")
        )
    )

    st.caption(
        f'📍 Location timezone: '
        f'{weather.get("timezone", "local time")}'
    )

    st.divider()

    st.info(
        "Live weather is shown from the weather API "
        "for the selected city."
    )

    if st.button(
        "🔄 Refresh Weather",
        key="live_refresh"
    ):

        st.rerun()


# =========================================================
# TAB 2 — NEXT 24 HOURS
# =========================================================

with tabs[1]:

    st.subheader(
        "🕐 Next 24 Hours"
    )

    next_rows = next_24_hour_rows(
        rows,
        weather
    )

    if next_rows:

        st.success(
            f"Showing the next "
            f"{len(next_rows)} hourly forecast records "
            f"from the current local forecast hour."
        )

        st.dataframe(
            next_rows,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "Next 24-hour hourly data is not available."
        )


# =========================================================
# TAB 3 — AI ASSISTANT
# =========================================================

with tabs[2]:

    st.subheader(
        "🤖 Talk with AI Agent"
    )

    if "chat_history" not in st.session_state:

        st.session_state.chat_history = []


    for message in st.session_state.chat_history:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )


    question = st.chat_input(
        "Ask: Aaj 7 baje baarish hogi?"
    )


    if question:

        st.session_state.chat_history.append(
            {
                "role": "user",
                "content": question
            }
        )

        answer = ask_ai(
            question,
            rows,
            f"{location['name']}, "
            f"{location['country']}"
        )

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        st.rerun()


# =========================================================
# TAB 4 — 8 DAY FORECAST
# =========================================================

with tabs[3]:

    st.subheader(
        "🗓️ 8-Day Forecast"
    )

    for date_text in available_dates[:8]:

        selected_rows = [
            row
            for row in rows
            if row["Date"] == date_text
        ]

        selected_date = datetime.fromisoformat(
            date_text
        ).date()

        with st.expander(
            selected_date.strftime(
                "%A, %d %B %Y"
            )
        ):

            st.dataframe(
                selected_rows,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# TAB 5 — SPECIFIC DATE
# =========================================================

with tabs[4]:

    st.subheader(
        "🎯 Specific Date — 24 Hours"
    )

    min_date = datetime.fromisoformat(
        available_dates[0]
    ).date()

    max_date = datetime.fromisoformat(
        available_dates[-1]
    ).date()


    selected_date = st.date_input(
        "Select date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="specific_date"
    )


    selected_rows = rows_for_date(
        rows,
        selected_date
    )


    if selected_rows:

        st.dataframe(
            selected_rows,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "No hourly weather data was returned "
            "for this date."
        )


# =========================================================
# TAB 6 — BETWEEN DATES
# =========================================================

with tabs[5]:

    st.subheader(
        "↔️ Between Dates — 24-Hour Data"
    )

    min_date = datetime.fromisoformat(
        available_dates[0]
    ).date()

    max_date = datetime.fromisoformat(
        available_dates[-1]
    ).date()


    col1, col2 = st.columns(2)


    start_date = col1.date_input(
        "Start date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="range_start"
    )


    end_date = col2.date_input(
        "End date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="range_end"
    )


    if start_date > end_date:

        st.warning(
            "End date must be on or after start date."
        )

    else:

        range_rows = [
            row
            for row in rows
            if start_date.isoformat()
            <= row["Date"]
            <= end_date.isoformat()
        ]


        if range_rows:

            st.success(
                f"Showing hourly weather from "
                f"{start_date.strftime('%d %b %Y')} "
                f"to "
                f"{end_date.strftime('%d %b %Y')}."
            )

            st.dataframe(
                range_rows,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "No hourly weather data was returned "
                "for this range."
            )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Weather data: Open-Meteo • AI: Gemini REST API"
)
