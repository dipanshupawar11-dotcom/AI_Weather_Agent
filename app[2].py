import streamlit as st
import requests
from datetime import datetime, timedelta

# =========================================================
# GEMINI IMPORT
# =========================================================

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
# HELPER
# =========================================================

def get_condition(code):
    return WEATHER_CODES.get(code, "Unknown")


def format_day(date_string):
    return datetime.strptime(
        date_string, "%Y-%m-%d"
    ).strftime("%A")


# =========================================================
# CITY SEARCH
# =========================================================

@st.cache_data(ttl=600)
def search_city(city_name):

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": city_name,
        "count": 10,
        "language": "en",
        "format": "json"
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

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
            "timezone": city.get("timezone", "auto")
        })

    return results


# =========================================================
# WEATHER API
# =========================================================

@st.cache_data(ttl=600)
def get_weather(latitude, longitude, timezone):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {

        "latitude": latitude,
        "longitude": longitude,

        "timezone": timezone,

        "forecast_days": 8,

        # ---------------- CURRENT ----------------

        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "rain",
            "precipitation",
            "wind_speed_10m",
            "weather_code"
        ]),

        # ---------------- HOURLY ----------------

        "hourly": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "precipitation_probability",
            "precipitation",
            "rain",
            "wind_speed_10m",
            "weather_code"
        ]),

        # ---------------- DAILY ----------------

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
            "sunset"
        ])
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# HOURLY INDEX
# =========================================================

def get_hour_indexes(weather, selected_date):

    indexes = []

    hourly_times = weather["hourly"]["time"]

    for index, value in enumerate(hourly_times):

        if value.startswith(selected_date):
            indexes.append(index)

    return indexes


# =========================================================
# DAILY INDEX
# =========================================================

def get_daily_index(weather, selected_date):

    try:

        return weather["daily"]["time"].index(
            selected_date
        )

    except ValueError:

        return None


# =========================================================
# GEMINI CLIENT
# =========================================================

def get_gemini_client():

    if genai is None:
        return None

    try:

        api_key = st.secrets["GEMINI_API_KEY"]

        if not api_key:
            return None

        api_key = str(api_key).strip()

        if not api_key:
            return None

        return genai.Client(
            api_key=api_key
        )

    except Exception:

        return None


# =========================================================
# GEMINI STATUS
# =========================================================

def gemini_status():

    if genai is None:
        return "❌ google-genai package is not installed."

    try:

        api_key = st.secrets["GEMINI_API_KEY"]

        if api_key and str(api_key).strip():
            return "✅ Gemini API key detected."

        return "❌ Gemini API key is empty."

    except Exception:

        return "❌ GEMINI_API_KEY not found in Streamlit Secrets."


# =========================================================
# ASK GEMINI
# =========================================================

def ask_gemini(prompt):

    client = get_gemini_client()

    if client is None:

        return (
            None,
            "Gemini is not configured. "
            "Please add GEMINI_API_KEY in Streamlit Secrets."
        )

    try:

        response = client.models.generate_content(

            model="gemini-2.5-flash",

            contents=prompt
        )

        if response is None:

            return (
                None,
                "Gemini returned no response."
            )

        if not response.text:

            return (
                None,
                "Gemini returned an empty response."
            )

        return (
            response.text.strip(),
            None
        )

    except Exception as error:

        return (
            None,
            f"Gemini API Error: {error}"
        )


# =========================================================
# SESSION STATE
# =========================================================

if "city" not in st.session_state:
    st.session_state.city = None

if "weather" not in st.session_state:
    st.session_state.weather = None

if "city_results" not in st.session_state:
    st.session_state.city_results = []


# =========================================================
# HEADER
# =========================================================

st.title("🌦️ AI Weather Agent")

st.caption(
    "Current weather • 8-day forecast • "
    "Full 24-hour weather • Date search • "
    "Live mode • Gemini AI"
)


# =========================================================
# CITY SELECTION
# =========================================================

if st.session_state.city is None:

    st.subheader("📍 Select Your City")

    st.write(
        "Enter your city name and choose the correct "
        "location from the results."
    )

    with st.form("city_search_form"):

        city_input = st.text_input(
            "City name",
            placeholder="Example: Bhopal, Bengaluru, Delhi, Betul"
        )

        search_clicked = st.form_submit_button(
            "🔎 Search City",
            use_container_width=True
        )

    # -----------------------------------------------------

    if search_clicked:

        if not city_input.strip():

            st.warning(
                "Please enter a city name."
            )

        else:

            try:

                with st.spinner(
                    "Searching city..."
                ):

                    results = search_city(
                        city_input.strip()
                    )

                st.session_state.city_results = results

                if not results:

                    st.error(
                        "City not found. Try another name."
                    )

            except Exception as error:

                st.error(
                    f"City search failed: {error}"
                )

    # -----------------------------------------------------

    if st.session_state.city_results:

        st.markdown(
            "### 🔎 Search Results"
        )

        labels = []

        for item in st.session_state.city_results:

            location = ", ".join(
                x
                for x in [
                    item["name"],
                    item["admin1"],
                    item["country"]
                ]
                if x
            )

            labels.append(location)

        selected_label = st.radio(
            "Choose your city:",
            labels,
            index=0
        )

        selected_index = labels.index(
            selected_label
        )

        selected_city = (
            st.session_state.city_results[
                selected_index
            ]
        )

        if st.button(
            "✅ Use This City",
            type="primary",
            use_container_width=True
        ):

            try:

                with st.spinner(
                    "Fetching weather..."
                ):

                    weather = get_weather(
                        selected_city["latitude"],
                        selected_city["longitude"],
                        selected_city["timezone"]
                    )

                st.session_state.city = selected_city

                st.session_state.weather = weather

                st.session_state.city_results = []

                st.rerun()

            except Exception as error:

                st.error(
                    f"Weather data could not be fetched: {error}"
                )

    st.stop()


# =========================================================
# WEATHER LOADED
# =========================================================

city = st.session_state.city

weather = st.session_state.weather

if weather is None:

    st.error(
        "Weather data is unavailable."
    )

    if st.button("🔄 Start Again"):

        st.session_state.city = None

        st.rerun()

    st.stop()


current = weather["current"]

daily = weather["daily"]


# =========================================================
# CITY INFO
# =========================================================

st.success(
    f"📍 {city['name']}, {city['country']} "
    f"| 🕐 {city['timezone']}"
)


change_col, refresh_col = st.columns(2)


with change_col:

    if st.button(
        "📍 Change City",
        use_container_width=True
    ):

        st.session_state.city = None

        st.session_state.weather = None

        st.session_state.city_results = []

        st.rerun()


with refresh_col:

    if st.button(
        "🔄 Refresh Weather",
        use_container_width=True
    ):

        get_weather.clear()

        new_weather = get_weather(
            city["latitude"],
            city["longitude"],
            city["timezone"]
        )

        st.session_state.weather = new_weather

        st.rerun()


# =========================================================
# CURRENT WEATHER
# =========================================================

st.header("🌤️ Current Weather")


c1, c2, c3, c4, c5, c6 = st.columns(6)


c1.metric(
    "🌡️ Temperature",
    f"{current['temperature_2m']} °C"
)

c2.metric(
    "🤒 Feels Like",
    f"{current['apparent_temperature']} °C"
)

c3.metric(
    "💧 Humidity",
    f"{current['relative_humidity_2m']} %"
)

c4.metric(
    "🌧️ Rain",
    f"{current['rain']} mm"
)

c5.metric(
    "💨 Wind",
    f"{current['wind_speed_10m']} km/h"
)

c6.metric(
    "🌤️ Condition",
    get_condition(
        current["weather_code"]
    )
)


st.caption(
    f"Updated: {current['time']}"
)


# =========================================================
# TABS
# =========================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📅 8-Day Forecast",
    "🔎 Specific Date",
    "↔️ Between Dates",
    "🔴 Live Mode",
    "🤖 AI Weather Agent"
])


# =========================================================
# TAB 1
# 8 DAY FORECAST
# =========================================================

with tab1:

    st.header("📅 Next 8 Days")

    for i, selected_date in enumerate(
        daily["time"]
    ):

        day_name = format_day(
            selected_date
        )

        condition = get_condition(
            daily["weather_code"][i]
        )

        with st.expander(
            f"{selected_date} — "
            f"{day_name} — "
            f"{condition}",
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

            e.write(
                f"🤒 Feels Max: "
                f"{daily['apparent_temperature_max'][i]} °C"
            )

            f.write(
                f"🥶 Feels Min: "
                f"{daily['apparent_temperature_min'][i]} °C"
            )

            g.write(
                f"💨 Max Wind: "
                f"{daily['wind_speed_10m_max'][i]} km/h"
            )

            h.write(
                f"🌤️ Condition: {condition}"
            )

            st.write(
                f"🌅 Sunrise: "
                f"{daily['sunrise'][i]}"
            )

            st.write(
                f"🌇 Sunset: "
                f"{daily['sunset'][i]}"
            )


# =========================================================
# TAB 2
# SPECIFIC DATE + 24 HOURS
# =========================================================

with tab2:

    st.header("🔎 Specific Date")

    min_date = datetime.strptime(
        daily["time"][0],
        "%Y-%m-%d"
    ).date()

    max_date = datetime.strptime(
        daily["time"][-1],
        "%Y-%m-%d"
    ).date()

    selected = st.date_input(
        "Select a date",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )

    selected_date = selected.strftime(
        "%Y-%m-%d"
    )

    idx = get_daily_index(
        weather,
        selected_date
    )

    if idx is not None:

        st.subheader(
            f"📅 {selected_date} — "
            f"{format_day(selected_date)}"
        )

        a, b, c, d = st.columns(4)

        a.metric(
            "🌡️ Max",
            f"{daily['temperature_2m_max'][idx]} °C"
        )

        b.metric(
            "🥶 Min",
            f"{daily['temperature_2m_min'][idx]} °C"
        )

        c.metric(
            "🌧️ Rain",
            f"{daily['rain_sum'][idx]} mm"
        )

        d.metric(
            "☔ Rain Probability",
            f"{daily['precipitation_probability_max'][idx]} %"
        )

        st.write(
            f"🌤️ Condition: "
            f"{get_condition(daily['weather_code'][idx])}"
        )

        st.write(
            f"🌅 Sunrise: "
            f"{daily['sunrise'][idx]}"
        )

        st.write(
            f"🌇 Sunset: "
            f"{daily['sunset'][idx]}"
        )

        st.divider()

        st.subheader(
            "⏰ Full 24-Hour Weather"
        )

        indexes = get_hour_indexes(
            weather,
            selected_date
        )

        if indexes:

            for i in indexes:

                time_value = (
                    weather["hourly"]["time"][i]
                )

                hour = time_value.split("T")[1]

                condition = get_condition(
                    weather["hourly"]["weather_code"][i]
                )

                with st.expander(
                    f"🕐 {hour} — {condition}"
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
                        f"🌧️ Rain: "
                        f"{weather['hourly']['rain'][i]} mm"
                    )

                    h6.write(
                        f"💧 Precipitation: "
                        f"{weather['hourly']['precipitation'][i]} mm"
                    )

                    h7.write(
                        f"💨 Wind: "
                        f"{weather['hourly']['wind_speed_10m'][i]} km/h"
                    )

                    h8.write(
                        f"🌤️ Condition: "
                        f"{condition}"
                    )

        else:

            st.warning(
                "Hourly weather data is not available "
                "for this date."
            )


# =========================================================
# TAB 3
# BETWEEN DATES
# =========================================================

with tab3:

    st.header(
        "↔️ Weather Between Two Dates"
    )

    min_date = datetime.strptime(
        daily["time"][0],
        "%Y-%m-%d"
    ).date()

    max_date = datetime.strptime(
        daily["time"][-1],
        "%Y-%m-%d"
    ).date()

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

    if st.button(
        "🔎 Show Weather",
        use_container_width=True
    ):

        if end_date < start_date:

            st.error(
                "End date cannot be before start date."
            )

        else:

            current_date = start_date

            while current_date <= end_date:

                date_text = current_date.strftime(
                    "%Y-%m-%d"
                )

                idx = get_daily_index(
                    weather,
                    date_text
                )

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
                        f"🌤️ "
                        f"{get_condition(daily['weather_code'][idx])}"
                    )

                current_date += timedelta(
                    days=1
                )


# =========================================================
# TAB 4
# LIVE MODE
# =========================================================

with tab4:

    st.header(
        "🔴 Live Weather Mode"
    )

    st.write(
        "Refresh the weather manually whenever you want."
    )

    if st.button(
        "🔴 Get Latest Weather",
        use_container_width=True
    ):

        get_weather.clear()

        live_weather = get_weather(
            city["latitude"],
            city["longitude"],
            city["timezone"]
        )

        live_current = live_weather["current"]

        st.success(
            f"Latest update: "
            f"{live_current['time']}"
        )

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


# =========================================================
# TAB 5
# GEMINI AI
# =========================================================

with tab5:

    st.header(
        "🤖 Ask AI Weather Agent"
    )

    st.write(
        "Ask questions in English, Hindi, or Hinglish."
    )

    # -----------------------------------------------------
    # GEMINI STATUS
    # -----------------------------------------------------

    status = gemini_status()

    if status.startswith("✅"):

        st.success(status)

    else:

        st.warning(status)

    # -----------------------------------------------------
    # EXAMPLES
    # -----------------------------------------------------

    st.markdown(
        "### 💡 Example questions"
    )

    examples = [

        "Will it rain tomorrow?",

        "Kal umbrella leke jau?",

        "Parso pani aayega?",

        "Which day will be hottest?",

        "Which day will have the most rain?",

        "Which day is best for outdoor activities?",

        "Tell me tomorrow's weather in simple Hindi.",

        "Tomorrow 10 AM temperature kya hoga?",

        "Kal 6 PM baarish hogi kya?"

    ]

    for example in examples:

        st.write(
            f"• {example}"
        )

    # -----------------------------------------------------
    # USER QUESTION
    # -----------------------------------------------------

    user_question = st.text_area(
        "Your question",
        placeholder="Example: Kal umbrella leke jau?",
        height=120
    )

    # -----------------------------------------------------
    # ASK BUTTON
    # -----------------------------------------------------

    if st.button(
        "🤖 Ask Gemini",
        type="primary",
        use_container_width=True
    ):

        if not user_question.strip():

            st.warning(
                "Please enter a question."
            )

        else:

            # =============================================
            # BUILD WEATHER CONTEXT
            # =============================================

            context = []

            context.append(
                f"City: {city['name']}, {city['country']}"
            )

            context.append(
                f"Timezone: {city['timezone']}"
            )

            context.append("")

            context.append(
                "CURRENT WEATHER:"
            )

            context.append(
                f"Temperature: "
                f"{current['temperature_2m']} °C"
            )

            context.append(
                f"Feels Like: "
                f"{current['apparent_temperature']} °C"
            )

            context.append(
                f"Humidity: "
                f"{current['relative_humidity_2m']} %"
            )

            context.append(
                f"Rain: "
                f"{current['rain']} mm"
            )

            context.append(
                f"Wind: "
                f"{current['wind_speed_10m']} km/h"
            )

            context.append(
                f"Condition: "
                f"{get_condition(current['weather_code'])}"
            )

            context.append("")

            # =============================================
            # DAILY DATA
            # =============================================

            context.append(
                "8-DAY FORECAST:"
            )

            for i, forecast_date in enumerate(
                daily["time"]
            ):

                context.append(
                    f"""
Date: {forecast_date}
Day: {format_day(forecast_date)}
Condition: {get_condition(daily['weather_code'][i])}
Max Temperature: {daily['temperature_2m_max'][i]} °C
Min Temperature: {daily['temperature_2m_min'][i]} °C
Feels Like Max: {daily['apparent_temperature_max'][i]} °C
Feels Like Min: {daily['apparent_temperature_min'][i]} °C
Rain: {daily['rain_sum'][i]} mm
Rain Probability: {daily['precipitation_probability_max'][i]} %
Maximum Wind: {daily['wind_speed_10m_max'][i]} km/h
Sunrise: {daily['sunrise'][i]}
Sunset: {daily['sunset'][i]}
"""
                )

            # =============================================
            # HOURLY DATA
            # =============================================

            context.append(
                "HOURLY WEATHER FOR ALL AVAILABLE DAYS:"
            )

            hourly = weather["hourly"]

            for i in range(
                len(hourly["time"])
            ):

                context.append(
                    f"""
Time: {hourly['time'][i]}
Temperature: {hourly['temperature_2m'][i]} °C
Feels Like: {hourly['apparent_temperature'][i]} °C
Humidity: {hourly['relative_humidity_2m'][i]} %
Rain Probability: {hourly['precipitation_probability'][i]} %
Rain: {hourly['rain'][i]} mm
Precipitation: {hourly['precipitation'][i]} mm
Wind: {hourly['wind_speed_10m'][i]} km/h
Condition: {get_condition(hourly['weather_code'][i])}
"""
                )

            weather_context = "\n".join(
                context
            )

            # =============================================
            # GEMINI PROMPT
            # =============================================

            prompt = f"""
You are an AI Weather Agent.

You must answer the user's question using ONLY
the weather data provided below.

IMPORTANT RULES:

1. Understand English, Hindi and Hinglish.

2. Reply in the same language/style as the user.

3. Never invent weather information.

4. Use the hourly data when the user asks about:
   - a specific hour
   - morning
   - afternoon
   - evening
   - night
   - 24-hour weather
   - temperature at a particular time
   - rain at a particular time

5. Use daily data for general day-level questions.

6. If the user asks:
   "Kal umbrella leke jau?"
   answer YES or NO first, then explain.

7. For hottest/coldest/rainiest questions,
   compare the available forecast days.

8. For outdoor activity questions,
   consider rain, rain probability,
   temperature, wind and condition.

9. If the requested date is available,
   give the actual weather data.

10. If the requested information is not available,
    clearly say that it is not available.

11. Do not make up future weather beyond the supplied data.

12. Keep the answer clear and useful.

WEATHER DATA:

{weather_context}

USER QUESTION:

{user_question}
"""

            # =============================================
            # CALL GEMINI
            # =============================================

            with st.spinner(
                "🤖 Gemini is thinking..."
            ):

                answer, error = ask_gemini(
                    prompt
                )

            if error:

                st.error(error)

            else:

                st.markdown(
                    "### 🤖 Gemini"
                )

                st.write(answer)


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Weather data provided by Open-Meteo. "
    "AI responses are generated by Google Gemini."
)
