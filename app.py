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

# Free Indian Pincode API
PINCODE_URL = "https://api.pincodeapi.in/api/v1/search"


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
# PINCODE LOOKUP
# =========================================================

def get_pincode(city, state=""):

    try:

        # First search with city name
        response = requests.get(
            PINCODE_URL,
            params={
                "q": city,
                "limit": 50
            },
            timeout=15,
        )

        response.raise_for_status()

        result = response.json()

        # API normally returns:
        # {
        #   "status": "success",
        #   "data": [...]
        # }

        data = result.get("data", [])

        if not isinstance(data, list):
            return "Not available"

        # -------------------------------------------------
        # Match city + state
        # -------------------------------------------------

        city_lower = city.strip().lower()
        state_lower = state.strip().lower()

        matched = []

        for office in data:

            office_name = str(
                office.get("officename", "")
            ).lower()

            office_state = str(
                office.get("statename", "")
            ).lower()

            office_pincode = str(
                office.get("pincode", "")
            ).strip()

            if not office_pincode:
                continue

            # State must match if available
            state_match = (
                not state_lower
                or state_lower in office_state
                or office_state in state_lower
            )

            # City can appear in office name
            city_match = (
                city_lower in office_name
                or city_lower in office_state
                or city_lower in str(
                    office.get("district", "")
                ).lower()
            )

            if state_match and city_match:

                matched.append(
                    office_pincode
                )

        # -------------------------------------------------
        # If exact city/state matching worked
        # -------------------------------------------------

        if matched:

            # Remove duplicates while preserving order
            unique_pins = list(
                dict.fromkeys(matched)
            )

            return ", ".join(
                unique_pins[:5]
            )

        # -------------------------------------------------
        # Second fallback:
        # Match state only
        # -------------------------------------------------

        state_matched = []

        for office in data:

            office_state = str(
                office.get("statename", "")
            ).lower()

            office_pincode = str(
                office.get("pincode", "")
            ).strip()

            if (
                office_pincode
                and state_lower
                and (
                    state_lower in office_state
                    or office_state in state_lower
                )
            ):

                state_matched.append(
                    office_pincode
                )

        if state_matched:

            unique_pins = list(
                dict.fromkeys(state_matched)
            )

            return ", ".join(
                unique_pins[:5]
            )

        # -------------------------------------------------
        # Final fallback:
        # Return first valid PIN
        # -------------------------------------------------

        all_pins = []

        for office in data:

            pincode = str(
                office.get("pincode", "")
            ).strip()

            if pincode:

                all_pins.append(
                    pincode
                )

        if all_pins:

            unique_pins = list(
                dict.fromkeys(all_pins)
            )

            return ", ".join(
                unique_pins[:5]
            )

    except requests.RequestException:

        pass

    except Exception:

        pass

    return "Not available"


# =========================================================
# GEOCODING
# =========================================================

def geocode_city(city):

    response = requests.get(
        GEO_URL,
        params={
            "name": city,
            "count": 5,
            "language": "en",
            "format": "json",
        },
        timeout=15,
    )

    response.raise_for_status()

    results = response.json().get(
        "results",
        []
    )

    if not results:
        return None

    # -----------------------------------------------------
    # Prefer India when user searches Indian city
    # -----------------------------------------------------

    india_results = [
        location
        for location in results
        if location.get("country_code") == "IN"
    ]

    if india_results:
        location = india_results[0]
    else:
        location = results[0]

    city_name = location.get(
        "name",
        city
    )

    state_name = location.get(
        "admin1",
        ""
    )

    country_name = location.get(
        "country",
        ""
    )

    # -----------------------------------------------------
    # Get PIN from separate PIN API
    # -----------------------------------------------------

    pin_code = get_pincode(
        city_name,
        state_name
    )

    return {
        "name": city_name,
        "state": state_name,
        "country": country_name,
        "pin_code": pin_code,
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
        raise ValueError(
            "Weather API returned no hourly data."
        )

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

    return labels.get(
        code,
        "Unknown"
    )


# =========================================================
# HOURLY ROWS
# =========================================================

def hourly_rows(data):

    hourly = data["hourly"]

    rows = []

    for i, timestamp in enumerate(
        hourly["time"]
    ):

        local_dt = datetime.fromisoformat(
            timestamp
        )

        rows.append({
            "Date": local_dt.date().isoformat(),
            "Time": local_dt.strftime(
                "%I:%M %p"
            ),
            "Temperature (°C)": hourly[
                "temperature_2m"
            ][i],
            "Feels Like (°C)": hourly[
                "apparent_temperature"
            ][i],
            "Humidity (%)": hourly[
                "relative_humidity_2m"
            ][i],
            "Rain Chance (%)": hourly[
                "precipitation_probability"
            ][i],
            "Rain (mm)": hourly[
                "precipitation"
            ][i],
            "Wind (km/h)": hourly[
                "wind_speed_10m"
            ][i],
            "Condition": weather_label(
                hourly["weather_code"][i]
            ),
        })

    return rows


# =========================================================
# GET TODAY
# =========================================================

def get_api_today(data):

    timezone_name = data.get(
        "timezone"
    )

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

def rows_for_date(
    rows,
    selected_date
):

    target = selected_date.isoformat()

    return [
        row
        for row in rows
        if row["Date"] == target
    ]


# =========================================================
# NEXT 24 HOURS
# =========================================================

def next_24_hour_rows(
    rows,
    data
):

    timezone_name = data.get(
        "timezone"
    )

    try:

        if timezone_name:

            now_local = datetime.now(
                ZoneInfo(timezone_name)
            )

        else:

            now_local = datetime.now()

    except Exception:

        now_local = datetime.now()

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

    start_index = None

    for index, (
        row_dt,
        row
    ) in enumerate(all_rows):

        if row_dt >= now_naive:

            start_index = index

            break

    if start_index is None:

        return []

    return [
        row
        for _, row
        in all_rows[
            start_index:
            start_index + 24
        ]
    ]


# =========================================================
# GEMINI API KEY
# =========================================================

def get_gemini_key():

    try:

        if "GEMINI_API_KEY" in st.secrets:

            return st.secrets[
                "GEMINI_API_KEY"
            ]

    except Exception:

        pass

    return os.getenv(
        "GEMINI_API_KEY"
    )


# =========================================================
# AI WEATHER ASSISTANT
# =========================================================

def ask_ai(
    question,
    rows,
    location_name
):

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

st.title(
    "🌦️ AI Weather Agent"
)

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
        "Could not connect to the location service: "
        f"{exc}"
    )

    st.stop()


if not location:

    st.error(
        "City not found. Please enter a valid city name."
    )

    st.stop()


# =========================================================
# LOCATION DETAILS
# =========================================================

st.success(
    f"📍 {location['name']}, "
    f"{location['state']}, "
    f"{location['country']} "
    f"• PIN: {location['pin_code']}"
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

rows = hourly_rows(
    weather
)

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
    "Weather data: Open-Meteo • "
    "PIN data: PincodeAPI.in • "
    "AI: Gemini REST API"
)
