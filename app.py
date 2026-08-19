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
# API URLS
# =========================================================

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# PincodeAPI.in
PIN_URL = "https://api.pincodeapi.in/api/v1/search"


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
# PINCODE SEARCH
# =========================================================

def search_pincode_locations(search_text):

    try:

        response = requests.get(
            PIN_URL,
            params={
                "q": search_text,
                "limit": 500
            },
            timeout=20
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            return []

        if payload.get("status") != "success":
            return []

        data = payload.get(
            "data",
            []
        )

        if not isinstance(data, list):
            return []

        locations = []

        for office in data:

            if not isinstance(
                office,
                dict
            ):
                continue

            office_name = str(
                office.get(
                    "officename",
                    ""
                )
            ).strip()

            pincode = str(
                office.get(
                    "pincode",
                    ""
                )
            ).strip()

            district = str(
                office.get(
                    "district",
                    ""
                )
            ).strip()

            state = str(
                office.get(
                    "statename",
                    ""
                )
            ).strip()

            office_type = str(
                office.get(
                    "officetype",
                    ""
                )
            ).strip()

            delivery = str(
                office.get(
                    "delivery",
                    ""
                )
            ).strip()

            latitude = office.get(
                "latitude"
            )

            longitude = office.get(
                "longitude"
            )

            if not office_name:
                continue

            if not pincode:
                continue

            locations.append({
                "post_office": office_name,
                "pincode": pincode,
                "district": district,
                "state": state,
                "office_type": office_type,
                "delivery": delivery,
                "latitude": latitude,
                "longitude": longitude,
            })

        return locations

    except (
        requests.RequestException,
        ValueError,
        TypeError
    ):

        return []


# =========================================================
# OPEN-METEO GEOCODING
# =========================================================

def geocode_city(city):

    response = requests.get(
        GEO_URL,
        params={
            "name": city,
            "count": 20,
            "language": "en",
            "format": "json",
            "countryCode": "IN",
        },
        timeout=20,
    )

    response.raise_for_status()

    results = response.json().get(
        "results",
        []
    )

    if not results:
        return []

    return results


# =========================================================
# GET COORDINATES FOR POST OFFICE
# =========================================================

def get_post_office_coordinates(
    office_name,
    district,
    state
):

    search_queries = [
        f"{office_name}, {district}, {state}, India",
        f"{office_name}, {state}, India",
        f"{district}, {state}, India",
    ]

    for query in search_queries:

        try:

            response = requests.get(
                GEO_URL,
                params={
                    "name": query,
                    "count": 5,
                    "language": "en",
                    "format": "json",
                    "countryCode": "IN",
                },
                timeout=15,
            )

            response.raise_for_status()

            results = response.json().get(
                "results",
                []
            )

            if results:

                # Prefer result matching state/district
                for result in results:

                    result_state = str(
                        result.get(
                            "admin1",
                            ""
                        )
                    ).lower()

                    result_district = str(
                        result.get(
                            "admin2",
                            ""
                        )
                    ).lower()

                    if (
                        state.lower() in result_state
                        or result_state in state.lower()
                    ) and (
                        not district
                        or district.lower() in result_district
                        or result_district in district.lower()
                    ):

                        return (
                            result.get("latitude"),
                            result.get("longitude"),
                            result.get("name", office_name)
                        )

                # fallback to first result
                result = results[0]

                return (
                    result.get("latitude"),
                    result.get("longitude"),
                    result.get(
                        "name",
                        office_name
                    )
                )

        except (
            requests.RequestException,
            ValueError,
            TypeError
        ):

            continue

    return (
        None,
        None,
        office_name
    )


# =========================================================
# BUILD LOCATION LIST
# =========================================================

def build_locations(search_text):

    postal_locations = search_pincode_locations(
        search_text
    )

    geo_locations = geocode_city(
        search_text
    )

    final_locations = []

    # -----------------------------------------------------
    # FIRST: USE POSTAL SEARCH RESULTS
    # -----------------------------------------------------

    for office in postal_locations:

        latitude = office[
            "latitude"
        ]

        longitude = office[
            "longitude"
        ]

        office_name = office[
            "post_office"
        ]

        district = office[
            "district"
        ]

        state = office[
            "state"
        ]

        # API may return null coordinates
        if (
            latitude is None
            or longitude is None
        ):

            latitude, longitude, _ = (
                get_post_office_coordinates(
                    office_name,
                    district,
                    state
                )
            )

        # Only add location if coordinates exist
        if (
            latitude is None
            or longitude is None
        ):
            continue

        final_locations.append({
            "name": office_name,
            "post_office": office_name,
            "district": district,
            "state": state,
            "country": "India",
            "pincode": office[
                "pincode"
            ],
            "office_type": office[
                "office_type"
            ],
            "delivery": office[
                "delivery"
            ],
            "latitude": float(latitude),
            "longitude": float(longitude),
        })

    # -----------------------------------------------------
    # SECOND: IF POSTAL SEARCH DID NOT FIND ANYTHING
    # USE OPEN-METEO CITY RESULTS
    # -----------------------------------------------------

    if not final_locations:

        for location in geo_locations:

            final_locations.append({
                "name": location.get(
                    "name",
                    search_text
                ),
                "post_office": "",
                "district": location.get(
                    "admin2",
                    ""
                ),
                "state": location.get(
                    "admin1",
                    ""
                ),
                "country": location.get(
                    "country",
                    "India"
                ),
                "pincode": (
                    ", ".join(
                        location.get(
                            "postcodes",
                            []
                        )
                    )
                    if location.get(
                        "postcodes"
                    )
                    else "Not available"
                ),
                "office_type": "",
                "delivery": "",
                "latitude": location.get(
                    "latitude"
                ),
                "longitude": location.get(
                    "longitude"
                ),
            })

    # -----------------------------------------------------
    # REMOVE DUPLICATES
    # -----------------------------------------------------

    unique_locations = []

    seen = set()

    for location in final_locations:

        key = (
            location["post_office"].lower(),
            location["district"].lower(),
            location["state"].lower(),
            location["pincode"],
            round(
                float(location["latitude"]),
                4
            ),
            round(
                float(location["longitude"]),
                4
            )
        )

        if key in seen:
            continue

        seen.add(key)

        unique_locations.append(
            location
        )

    return unique_locations


# =========================================================
# WEATHER
# =========================================================

def fetch_weather(
    latitude,
    longitude
):

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
# SPECIFIC DATE
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
# GEMINI KEY
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
            "Add GEMINI_API_KEY to Streamlit Secrets."
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
- Use only the supplied weather data for weather facts.
- Never invent temperature, rain chance, time or condition.
- If requested data is unavailable, say that clearly.
- Give practical weather advice when useful.
- Keep the answer friendly and concise.

Hourly weather data:

{weather_context}

User question:

{question}
"""

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-3.6-flash:generateContent"
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
                "AI could not generate a response right now."
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
# TITLE
# =========================================================

st.title(
    "🌦️ AI Weather Agent"
)

st.caption(
    "Search Location • Select Exact Place • "
    "PIN Code • Live Weather • Next 24 Hours • "
    "AI Assistant • 8-Day Forecast"
)


# =========================================================
# SEARCH INPUT
# =========================================================

city = st.text_input(
    "🏙️ Search City / Location",
    placeholder="Example: Betul"
)


if not city.strip():

    st.info(
        "Enter a city or location above to start."
    )

    st.stop()


# =========================================================
# SEARCH LOCATIONS
# =========================================================

try:

    with st.spinner(
        "Searching locations and PIN codes..."
    ):

        locations = build_locations(
            city.strip()
        )

except requests.RequestException as exc:

    st.error(
        f"Location service error: {exc}"
    )

    st.stop()


if not locations:

    st.error(
        "No matching location found."
    )

    st.stop()


# =========================================================
# LOCATION SELECTOR
# =========================================================

st.subheader(
    "📍 Select Your Exact Location"
)

st.info(
    f"Found {len(locations)} matching location(s). "
    "Select the place you want to see weather for."
)


location_labels = []

for index, location in enumerate(
    locations
):

    post_office = location[
        "post_office"
    ]

    district = location[
        "district"
    ]

    state = location[
        "state"
    ]

    pincode = location[
        "pincode"
    ]

    office_type = location[
        "office_type"
    ]

    if post_office:

        label = (
            f"{index + 1}. "
            f"{post_office} "
            f"({office_type}) — "
            f"{district}, {state} "
            f"• PIN: {pincode}"
        )

    else:

        label = (
            f"{index + 1}. "
            f"{location['name']} — "
            f"{district}, {state} "
            f"• PIN: {pincode}"
        )

    location_labels.append(
        label
    )


selected_index = st.selectbox(
    "Choose location",
    range(
        len(location_labels)
    ),
    format_func=lambda i:
        location_labels[i]
)


selected_location = locations[
    selected_index
]


# =========================================================
# SELECTED LOCATION
# =========================================================

st.success(
    f"📍 Selected: "
    f"{selected_location['post_office'] or selected_location['name']}, "
    f"{selected_location['district']}, "
    f"{selected_location['state']}, "
    f"{selected_location['country']} "
    f"• PIN: {selected_location['pincode']}"
)


st.caption(
    f"📮 Post Office: "
    f"{selected_location['post_office'] or 'N/A'}"
    f"  |  "
    f"📍 Coordinates: "
    f"{selected_location['latitude']:.5f}, "
    f"{selected_location['longitude']:.5f}"
)


# =========================================================
# LOAD WEATHER FOR SELECTED LOCATION
# =========================================================

try:

    with st.spinner(
        "Loading weather..."
    ):

        weather = fetch_weather(
            selected_location["latitude"],
            selected_location["longitude"]
        )

except requests.RequestException as exc:

    st.error(
        f"Could not load weather data: {exc}"
    )

    st.stop()

except ValueError as exc:

    st.error(
        str(exc)
    )

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
        "No hourly forecast data available."
    )

    st.stop()


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
# LIVE WEATHER
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
            current.get(
                "weather_code"
            )
        )
    )

    st.caption(
        f"📍 Timezone: "
        f"{weather.get('timezone', 'local time')}"
    )

    st.divider()

    if st.button(
        "🔄 Refresh Weather",
        key="live_refresh"
    ):

        st.rerun()


# =========================================================
# NEXT 24 HOURS
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
            f"Showing next "
            f"{len(next_rows)} hourly records."
        )

        st.dataframe(
            next_rows,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "Next 24-hour data is unavailable."
        )


# =========================================================
# AI ASSISTANT
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

        st.session_state.chat_history.append({
            "role": "user",
            "content": question
        })

        answer = ask_ai(
            question,
            rows,
            (
                f"{selected_location['post_office'] or selected_location['name']}, "
                f"{selected_location['district']}, "
                f"{selected_location['state']}"
            )
        )

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer
        })

        st.rerun()


# =========================================================
# 8 DAY FORECAST
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
# SPECIFIC DATE
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
            "No hourly data for this date."
        )


# =========================================================
# BETWEEN DATES
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
                "No hourly data for this range."
            )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Weather: Open-Meteo • "
    "PIN/Post Office: PincodeAPI.in • "
    "AI: Gemini"
)
