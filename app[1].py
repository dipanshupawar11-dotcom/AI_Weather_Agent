import streamlit as st
import requests
from datetime import datetime, date, timedelta
import time

# Gemini SDK is optional at startup; AI features use it when a key is configured.
try:
    from google import genai
except ImportError:
    genai = None


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="AI Weather Agent",
    page_icon="🌦️",
    layout="wide"
)

# =========================================================
# WEATHER CODES
# =========================================================
WEATHER_CODES = {
    0: "Clear Sky",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Cloudy",
    45: "Fog",
    48: "Depositing Rime Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Dense Drizzle",
    56: "Light Freezing Drizzle",
    57: "Dense Freezing Drizzle",
    61: "Light Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    66: "Light Freezing Rain",
    67: "Heavy Freezing Rain",
    71: "Light Snow",
    73: "Moderate Snow",
    75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Rain Showers",
    81: "Moderate Rain Showers",
    82: "Heavy Rain Showers",
    85: "Light Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm with Light Hail",
    99: "Thunderstorm with Heavy Hail",
}


# =========================================================
# API FUNCTIONS
# =========================================================
@st.cache_data(ttl=600)
def search_city(city_name):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city_name,
        "count": 8,
        "language": "en",
        "format": "json",
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    results = []
    for city in data.get("results", []):
        results.append({
            "name": city.get("name", ""),
            "country": city.get("country", ""),
            "admin1": city.get("admin1", ""),
            "latitude": city.get("latitude"),
            "longitude": city.get("longitude"),
            "timezone": city.get("timezone", "auto"),
        })

    return results


@st.cache_data(ttl=600)
def get_weather(latitude, longitude, timezone):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "forecast_days": 8,

        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "rain",
            "precipitation",
            "wind_speed_10m",
            "weather_code",
        ]),

        "hourly": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "precipitation_probability",
            "precipitation",
            "rain",
            "wind_speed_10m",
            "weather_code",
        ]),

        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "rain_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "sunrise",
            "sunset",
        ]),
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def get_condition(code):
    return WEATHER_CODES.get(code, "Unknown")


def get_hour_indexes(weather, selected_date):
    return [
        i for i, value in enumerate(weather["hourly"]["time"])
        if value.startswith(selected_date)
    ]


def get_daily_index(weather, selected_date):
    try:
        return weather["daily"]["time"].index(selected_date)
    except ValueError:
        return None


def get_gemini_client():
    if genai is None:
        return None

    api_key = None

    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        pass

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


def ask_gemini(prompt):
    client = get_gemini_client()

    if client is None:
        return None, "Gemini is not configured. Add GEMINI_API_KEY in Streamlit Secrets."

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            if response and response.text:
                return response.text.strip(), None

            return None, "Gemini returned an empty response."

        except Exception as exc:
            if attempt < 2:
                time.sleep((attempt + 1) * 2)
            else:
                return None, f"Gemini error: {exc}"

    return None, "Gemini request failed."


# =========================================================
# SESSION STATE
# =========================================================
if "city" not in st.session_state:
    st.session_state.city = None

if "weather" not in st.session_state:
    st.session_state.weather = None

if "city_results" not in st.session_state:
    st.session_state.city_results = []

if "selected_date" not in st.session_state:
    st.session_state.selected_date = None


# =========================================================
# HEADER
# =========================================================
st.title("🌦️ AI Weather Agent")
st.caption("Current weather • 8-day forecast • Full 24-hour weather • Date search • Live mode • Gemini AI")


# =========================================================
# CITY SELECTION
# =========================================================
if st.session_state.city is None:

    st.subheader("📍 Select Your City")
    st.write("Enter any city. The app will search and let you choose the correct location.")

    with st.form("city_search_form"):
        city_input = st.text_input(
            "City name",
            placeholder="Example: Bhopal, Bangalore, Delhi, Betul"
        )
        search_clicked = st.form_submit_button("🔎 Search City", use_container_width=True)

    if search_clicked:
        if not city_input.strip():
            st.warning("Please enter a city name.")
        else:
            try:
                with st.spinner("Finding city..."):
                    results = search_city(city_input.strip())

                st.session_state.city_results = results

                if not results:
                    st.error("City not found. Try another city name.")

            except Exception as exc:
                st.error(f"City search failed: {exc}")

    if st.session_state.city_results:
        st.markdown("### 🔎 Search Results")

        labels = []
        for item in st.session_state.city_results:
            location = ", ".join(
                x for x in [item["name"], item["admin1"], item["country"]]
                if x
            )
            labels.append(location)

        selected_label = st.radio(
            "Choose your city:",
            labels,
            index=0
        )

        selected_index = labels.index(selected_label)
        selected_city = st.session_state.city_results[selected_index]

        if st.button("✅ Use This City", type="primary", use_container_width=True):
            try:
                with st.spinner("Fetching weather..."):
                    weather = get_weather(
                        selected_city["latitude"],
                        selected_city["longitude"],
                        selected_city["timezone"]
                    )

                st.session_state.city = selected_city
                st.session_state.weather = weather
                st.session_state.city_results = []
                st.rerun()

            except Exception as exc:
                st.error(f"Weather data could not be fetched: {exc}")

    st.stop()


# =========================================================
# CITY + WEATHER LOADED
# =========================================================
city = st.session_state.city
weather = st.session_state.weather

if weather is None:
    st.error("Weather data is unavailable.")
    if st.button("🔄 Start Again"):
        st.session_state.city = None
        st.rerun()
    st.stop()

current = weather["current"]
daily = weather["daily"]

st.success(
    f"📍 {city['name']}, {city['country']}  |  🕐 {city['timezone']}"
)

col_change, col_refresh = st.columns(2)

with col_change:
    if st.button("📍 Change City", use_container_width=True):
        st.session_state.city = None
        st.session_state.weather = None
        st.session_state.city_results = []
        st.rerun()

with col_refresh:
    if st.button("🔄 Refresh Weather", use_container_width=True):
        get_weather.clear()
        weather = get_weather(
            city["latitude"],
            city["longitude"],
            city["timezone"]
        )
        st.session_state.weather = weather
        st.rerun()


# =========================================================
# CURRENT WEATHER
# =========================================================
st.header("🌤️ Current Weather")

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("🌡️ Temperature", f"{current['temperature_2m']} °C")
c2.metric("🤒 Feels Like", f"{current['apparent_temperature']} °C")
c3.metric("💧 Humidity", f"{current['relative_humidity_2m']} %")
c4.metric("🌧️ Rain", f"{current['rain']} mm")
c5.metric("💨 Wind", f"{current['wind_speed_10m']} km/h")
c6.metric("🌤️ Condition", get_condition(current["weather_code"]))

st.caption(f"Updated: {current['time']}")


# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📅 8-Day Forecast",
    "🔎 Specific Date",
    "↔️ Between Dates",
    "🔴 Live Mode",
    "🤖 AI Weather Agent",
])


# =========================================================
# TAB 1 - 8 DAYS
# =========================================================
with tab1:
    st.header("📅 Next 8 Days")

    for i, selected_date in enumerate(daily["time"]):
        day_name = datetime.strptime(
            selected_date, "%Y-%m-%d"
        ).strftime("%A")

        with st.expander(
            f"{selected_date} — {day_name} — {get_condition(daily['weather_code'][i])}",
            expanded=(i == 0)
        ):
            a, b, c, d = st.columns(4)

            a.metric(
                "🌡️ Max",
                f"{daily['temperature_2m_max'][i]} °C"
            )
            b.metric(
                "🥶 Min",
                f"{daily['temperature_2m_min'][i]} °C"
            )
            c.metric(
                "🌧️ Rain",
                f"{daily['rain_sum'][i]} mm"
            )
            d.metric(
                "☔ Rain Probability",
                f"{daily['precipitation_probability_max'][i]} %"
            )

            e, f, g, h = st.columns(4)

            e.write(f"🤒 Feels Max: {daily['apparent_temperature_max'][i]} °C")
            f.write(f"🥶 Feels Min: {daily['apparent_temperature_min'][i]} °C")
            g.write(f"💨 Max Wind: {daily['wind_speed_10m_max'][i]} km/h")
            h.write(f"🌤️ Condition: {get_condition(daily['weather_code'][i])}")

            st.write(f"🌅 Sunrise: {daily['sunrise'][i]}")
            st.write(f"🌇 Sunset: {daily['sunset'][i]}")


# =========================================================
# TAB 2 - SPECIFIC DATE + FULL 24 HOURS
# =========================================================
with tab2:
    st.header("🔎 Specific Date")

    min_date = datetime.strptime(daily["time"][0], "%Y-%m-%d").date()
    max_date = datetime.strptime(daily["time"][-1], "%Y-%m-%d").date()

    selected = st.date_input(
        "Select a date",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )

    selected_date = selected.strftime("%Y-%m-%d")
    idx = get_daily_index(weather, selected_date)

    if idx is not None:
        st.subheader(
            f"📅 {selected_date} — "
            f"{datetime.strptime(selected_date, '%Y-%m-%d').strftime('%A')}"
        )

        a, b, c, d = st.columns(4)

        a.metric("🌡️ Max", f"{daily['temperature_2m_max'][idx]} °C")
        b.metric("🥶 Min", f"{daily['temperature_2m_min'][idx]} °C")
        c.metric("🌧️ Rain", f"{daily['rain_sum'][idx]} mm")
        d.metric(
            "☔ Rain Probability",
            f"{daily['precipitation_probability_max'][idx]} %"
        )

        st.write(f"🌤️ Condition: {get_condition(daily['weather_code'][idx])}")
        st.write(f"🌅 Sunrise: {daily['sunrise'][idx]}")
        st.write(f"🌇 Sunset: {daily['sunset'][idx]}")

        st.divider()
        st.subheader("⏰ Full 24-Hour Weather")

        indexes = get_hour_indexes(weather, selected_date)

        if indexes:
            for i in indexes:
                time_value = weather["hourly"]["time"][i]
                hour = time_value.split("T")[1]

                with st.expander(
                    f"🕐 {hour} — {get_condition(weather['hourly']['weather_code'][i])}"
                ):
                    h1, h2, h3, h4 = st.columns(4)

                    h1.metric(
                        "🌡️ Temperature",
                        f"{weather['hourly']['temperature_2m'][i]} °C"
                    )
                    h2.metric(
                        "🤒 Feels Like",
                        f"{weather['hourly']['apparent_temperature'][i]} °C"
                    )
                    h3.metric(
                        "💧 Humidity",
                        f"{weather['hourly']['relative_humidity_2m'][i]} %"
                    )
                    h4.metric(
                        "☔ Rain Probability",
                        f"{weather['hourly']['precipitation_probability'][i]} %"
                    )

                    h5, h6, h7, h8 = st.columns(4)

                    h5.write(
                        f"🌧️ Rain: {weather['hourly']['rain'][i]} mm"
                    )
                    h6.write(
                        f"💧 Precipitation: {weather['hourly']['precipitation'][i]} mm"
                    )
                    h7.write(
                        f"💨 Wind: {weather['hourly']['wind_speed_10m'][i]} km/h"
                    )
                    h8.write(
                        f"🌤️ Condition: {get_condition(weather['hourly']['weather_code'][i])}"
                    )


# =========================================================
# TAB 3 - BETWEEN DATES
# =========================================================
with tab3:
    st.header("↔️ Weather Between Two Dates")

    min_date = datetime.strptime(daily["time"][0], "%Y-%m-%d").date()
    max_date = datetime.strptime(daily["time"][-1], "%Y-%m-%d").date()

    start_date = st.date_input(
        "Start date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="start_date"
    )

    end_date = st.date_input(
        "End date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="end_date"
    )

    if st.button("🔎 Show Weather", use_container_width=True):
        if end_date < start_date:
            st.error("End date cannot be before start date.")
        else:
            current_date = start_date

            while current_date <= end_date:
                date_text = current_date.strftime("%Y-%m-%d")
                idx = get_daily_index(weather, date_text)

                if idx is not None:
                    st.subheader(
                        f"📅 {date_text} — "
                        f"{current_date.strftime('%A')}"
                    )

                    x1, x2, x3, x4 = st.columns(4)

                    x1.metric(
                        "🌡️ Max",
                        f"{daily['temperature_2m_max'][idx]} °C"
                    )
                    x2.metric(
                        "🥶 Min",
                        f"{daily['temperature_2m_min'][idx]} °C"
                    )
                    x3.metric(
                        "🌧️ Rain",
                        f"{daily['rain_sum'][idx]} mm"
                    )
                    x4.metric(
                        "☔ Probability",
                        f"{daily['precipitation_probability_max'][idx]} %"
                    )

                    st.write(
                        f"🌤️ {get_condition(daily['weather_code'][idx])}"
                    )

                current_date += timedelta(days=1)


# =========================================================
# TAB 4 - LIVE MODE
# =========================================================
with tab4:
    st.header("🔴 Live Weather Mode")
    st.write("Live mode refreshes the current weather automatically.")

    refresh_seconds = st.selectbox(
        "Refresh interval",
        [60, 300, 600],
        format_func=lambda x: {
            60: "1 minute",
            300: "5 minutes",
            600: "10 minutes"
        }[x]
    )

    live_on = st.toggle("🔴 Start Live Mode", value=False)

    if live_on:
        placeholder = st.empty()

        # Refreshes while the user keeps the toggle enabled.
        while st.session_state.get("live_mode_running", True):
            live_weather = get_weather(
                city["latitude"],
                city["longitude"],
                city["timezone"]
            )
            live_current = live_weather["current"]

            with placeholder.container():
                st.info(f"Last update: {live_current['time']}")

                l1, l2, l3, l4, l5 = st.columns(5)

                l1.metric(
                    "🌡️ Temperature",
                    f"{live_current['temperature_2m']} °C"
                )
                l2.metric(
                    "🤒 Feels Like",
                    f"{live_current['apparent_temperature']} °C"
                )
                l3.metric(
                    "💧 Humidity",
                    f"{live_current['relative_humidity_2m']} %"
                )
                l4.metric(
                    "🌧️ Rain",
                    f"{live_current['rain']} mm"
                )
                l5.metric(
                    "💨 Wind",
                    f"{live_current['wind_speed_10m']} km/h"
                )

                st.write(
                    f"🌤️ Condition: "
                    f"{get_condition(live_current['weather_code'])}"
                )

            time.sleep(refresh_seconds)

            # Streamlit reruns on interaction; stop if toggle is no longer active.
            break

        st.caption("Toggle Live Mode off/on to refresh the live session again.")


# =========================================================
# TAB 5 - AI CHAT
# =========================================================
with tab5:
    st.header("🤖 Ask AI Weather Agent")

    if get_gemini_client() is None:
        st.warning(
            "Gemini is not configured. Add GEMINI_API_KEY in Streamlit Secrets."
        )

    st.write("Ask questions in English, Hindi, or Hinglish.")

    examples = [
        "Will it rain tomorrow?",
        "Kal umbrella leke jau?",
        "Parso pani aayega?",
        "Which day will be hottest?",
        "Which day will have the most rain?",
        "Which day is best for outdoor activities?",
        "Tell me tomorrow's weather in simple Hindi.",
    ]

    st.markdown("### 💡 Example questions")
    for example in examples:
        st.write(f"• {example}")

    user_question = st.text_area(
        "Your question",
        placeholder="Example: Kal umbrella leke jau?",
        height=100
    )

    if st.button("🤖 Ask Gemini", type="primary", use_container_width=True):
        if not user_question.strip():
            st.warning("Please enter a weather question.")
        else:
            weather_context_parts = [
                f"City: {city['name']}, {city['country']}",
                f"Timezone: {city['timezone']}",
                "",
                "8-DAY WEATHER DATA:"
            ]

            for i, d in enumerate(daily["time"]):
                weather_context_parts.append(
                    f"""
Date: {d}
Day: {datetime.strptime(d, "%Y-%m-%d").strftime("%A")}
Condition: {get_condition(daily["weather_code"][i])}
Max temperature: {daily["temperature_2m_max"][i]} °C
Min temperature: {daily["temperature_2m_min"][i]} °C
Feels-like max: {daily["apparent_temperature_max"][i]} °C
Feels-like min: {daily["apparent_temperature_min"][i]} °C
Rain: {daily["rain_sum"][i]} mm
Rain probability: {daily["precipitation_probability_max"][i]} %
Max wind: {daily["wind_speed_10m_max"][i]} km/h
Sunrise: {daily["sunrise"][i]}
Sunset: {daily["sunset"][i]}
"""
                )

            prompt = f"""
You are an AI Weather Agent.

Answer the user's question using ONLY the weather data supplied below.

Rules:
- Understand English, Hindi, and Hinglish.
- Reply in the same language style as the user.
- Never invent weather data.
- If the requested date is within the 8-day forecast, answer it.
- For rain questions, use rain amount, probability, and condition when useful.
- For umbrella/raincoat questions, give YES or NO first, then the reason.
- For hottest/coolest/rainiest questions, compare all available forecast days.
- For outdoor activities, consider rain probability, rain amount, temperature, wind, and condition.
- If the question is unrelated to weather, say that you can only answer weather-related questions.

WEATHER DATA:
{''.join(weather_context_parts)}

USER QUESTION:
{user_question}
"""

            with st.spinner("Gemini is thinking..."):
                answer, error = ask_gemini(prompt)

            if error:
                st.error(error)
            else:
                st.markdown("### 🤖 Gemini")
                st.write(answer)


# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption("Weather data provided by Open-Meteo. AI responses are generated by Google Gemini when configured.")
