import os
from datetime import datetime, timedelta
import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai

st.set_page_config(page_title="AI Weather Agent", page_icon="🌦️", layout="wide")
load_dotenv()

try:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
except Exception:
    GEMINI_API_KEY = None
GEMINI_API_KEY = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.6-flash"
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

WEATHER_CODES = {
    0:"Clear Sky",1:"Mainly Clear",2:"Partly Cloudy",3:"Cloudy",45:"Fog",48:"Depositing Rime Fog",
    51:"Light Drizzle",53:"Moderate Drizzle",55:"Dense Drizzle",56:"Light Freezing Drizzle",57:"Dense Freezing Drizzle",
    61:"Light Rain",63:"Moderate Rain",65:"Heavy Rain",66:"Light Freezing Rain",67:"Heavy Freezing Rain",
    71:"Light Snow",73:"Moderate Snow",75:"Heavy Snow",77:"Snow Grains",80:"Light Rain Showers",
    81:"Moderate Rain Showers",82:"Heavy Rain Showers",85:"Light Snow Showers",86:"Heavy Snow Showers",
    95:"Thunderstorm",96:"Thunderstorm with Light Hail",99:"Thunderstorm with Heavy Hail"
}

def icon(code):
    if code == 0: return "☀️"
    if code in (1,2): return "🌤️"
    if code == 3: return "☁️"
    if code in (45,48): return "🌫️"
    if code in (51,53,55,56,57): return "🌦️"
    if code in (61,63,65,66,67,80,81,82): return "🌧️"
    if code in (71,73,75,77,85,86): return "❄️"
    if code in (95,96,99): return "⛈️"
    return "🌤️"

def day_name(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%A")

def city_search(name):
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": name, "count": 5, "language": "en", "format": "json"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("results", [])

def get_weather(lat, lon, timezone):
    params = {
        "latitude": lat, "longitude": lon, "timezone": timezone, "forecast_days": 8,
        "current": ",".join([
            "temperature_2m","apparent_temperature","relative_humidity_2m","rain",
            "precipitation","wind_speed_10m","weather_code"
        ]),
        "hourly": ",".join([
            "temperature_2m","apparent_temperature","relative_humidity_2m",
            "precipitation_probability","rain","wind_speed_10m","weather_code"
        ]),
        "daily": ",".join([
            "weather_code","temperature_2m_max","temperature_2m_min",
            "apparent_temperature_max","apparent_temperature_min","rain_sum",
            "precipitation_probability_max","wind_speed_10m_max","sunrise","sunset"
        ]),
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def ask_gemini(prompt):
    if not gemini_client:
        return None, "Gemini API key is not configured."
    try:
        response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return (response.text.strip() if response and response.text else None), None
    except Exception as e:
        return None, str(e)

def context(city, weather):
    d = weather["daily"]
    lines = [
        f"City: {city['name']}, {city.get('country','')}",
        f"Timezone: {city['timezone']}",
        "CURRENT:",
        f"Temperature: {weather['current']['temperature_2m']} °C",
        f"Feels like: {weather['current']['apparent_temperature']} °C",
        f"Humidity: {weather['current']['relative_humidity_2m']} %",
        f"Rain: {weather['current']['rain']} mm",
        f"Precipitation: {weather['current']['precipitation']} mm",
        f"Wind: {weather['current']['wind_speed_10m']} km/h",
        f"Condition: {WEATHER_CODES.get(weather['current']['weather_code'], 'Unknown')}",
        "8-DAY FORECAST:"
    ]
    for i, ds in enumerate(d["time"]):
        lines += [
            f"Date: {ds} ({day_name(ds)})",
            f"Condition: {WEATHER_CODES.get(d['weather_code'][i], 'Unknown')}",
            f"Max: {d['temperature_2m_max'][i]} °C; Min: {d['temperature_2m_min'][i]} °C",
            f"Feels max: {d['apparent_temperature_max'][i]} °C; Feels min: {d['apparent_temperature_min'][i]} °C",
            f"Rain: {d['rain_sum'][i]} mm; Rain probability: {d['precipitation_probability_max'][i]} %",
            f"Max wind: {d['wind_speed_10m_max'][i]} km/h",
            f"Sunrise: {d['sunrise'][i]}; Sunset: {d['sunset'][i]}",
        ]
    return "\n".join(lines)

def daily_index(weather, ds):
    try: return weather["daily"]["time"].index(ds)
    except ValueError: return None

def daily_analysis(city, weather, ds):
    i = daily_index(weather, ds)
    if i is None: return None, "Date is outside the 8-day forecast."
    d = weather["daily"]
    info = f"""
City: {city['name']}, {city.get('country','')}
Date: {ds} ({day_name(ds)})
Condition: {WEATHER_CODES.get(d['weather_code'][i], 'Unknown')}
Max temperature: {d['temperature_2m_max'][i]} °C
Min temperature: {d['temperature_2m_min'][i]} °C
Feels-like max: {d['apparent_temperature_max'][i]} °C
Feels-like min: {d['apparent_temperature_min'][i]} °C
Rain: {d['rain_sum'][i]} mm
Rain probability: {d['precipitation_probability_max'][i]} %
Maximum wind: {d['wind_speed_10m_max'][i]} km/h
Sunrise: {d['sunrise'][i]}
Sunset: {d['sunset'][i]}
"""
    return ask_gemini(f"""You are an AI Weather Assistant. Use ONLY this data:
{info}

Give a concise practical answer covering overall condition, rain likelihood, umbrella/raincoat advice, temperature, wind, best outdoor time if supportable, warning, and final recommendation. Never invent data.""")

def chat_answer(city, weather, question):
    prompt = f"""You are an AI Weather Agent. Answer ONLY from the supplied weather data.

WEATHER DATA:
{context(city, weather)}

USER QUESTION:
{question}

Rules:
- Understand English, Hindi and Hinglish and answer in the user's language/style.
- Interpret kal as tomorrow and parso as day after tomorrow when appropriate.
- For umbrella/raincoat questions give YES or NO first, then reason.
- For rain questions mention probability and rainfall when available.
- Compare all 8 days for hottest, coolest, rainiest and best outdoor day questions.
- If a requested date is outside these 8 days, say so.
- Never invent data.
- If unrelated to weather, say you can only answer weather-related questions.
- Keep it clear and concise."""
    return ask_gemini(prompt)

# -------------------- SESSION STATE --------------------
if "city" not in st.session_state:
    st.session_state.city = None
if "weather" not in st.session_state:
    st.session_state.weather = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# -------------------- SIDEBAR --------------------
st.sidebar.title("🌦️ AI Weather Agent")
query = st.sidebar.text_input("📍 Enter city", value=st.session_state.city["name"] if st.session_state.city else "Betul")
if st.sidebar.button("🔎 Search Weather", use_container_width=True):
    try:
        results = city_search(query.strip())
        if not results:
            st.sidebar.error("City not found.")
        else:
            labels = [f"{x.get('name')}, {x.get('admin1')+', ' if x.get('admin1') else ''}{x.get('country')}" for x in results]
            choice = st.sidebar.selectbox("Choose location", labels) if len(results) > 1 else labels[0]
            selected = results[labels.index(choice)]
            city = {
                "name": selected.get("name"), "country": selected.get("country"),
                "latitude": selected.get("latitude"), "longitude": selected.get("longitude"),
                "timezone": selected.get("timezone") or "auto"
            }
            weather = get_weather(city["latitude"], city["longitude"], city["timezone"])
            st.session_state.city, st.session_state.weather = city, weather
            st.session_state.messages = []
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Search failed: {e}")

# Default city only if nothing has been searched yet.
if st.session_state.city is None:
    st.session_state.city = {
        "name":"Betul","country":"India","latitude":21.91,"longitude":77.90,"timezone":"Asia/Kolkata"
    }
if st.session_state.weather is None:
    try:
        st.session_state.weather = get_weather(
            st.session_state.city["latitude"], st.session_state.city["longitude"], st.session_state.city["timezone"]
        )
    except Exception as e:
        st.error(f"Could not load weather: {e}")
        st.stop()

city, weather = st.session_state.city, st.session_state.weather
current, daily = weather["current"], weather["daily"]

# -------------------- HEADER --------------------
st.title("🌦️ AI Weather Agent")
st.caption("Current Weather • 8-Day Forecast • Date Search • Live Refresh • Gemini AI")
st.info(f"📍 **{city['name']}, {city['country']}**  |  🕐 **{city['timezone']}**  |  Updated: **{current['time']}**")

st.subheader("🌤️ Current Weather")
a,b,c,d = st.columns(4)
a.metric("🌡️ Temperature", f"{current['temperature_2m']} °C")
b.metric("🤒 Feels Like", f"{current['apparent_temperature']} °C")
c.metric("💧 Humidity", f"{current['relative_humidity_2m']} %")
d.metric("💨 Wind", f"{current['wind_speed_10m']} km/h")
a,b,c = st.columns(3)
a.metric("🌧️ Rain", f"{current['rain']} mm")
b.metric("☔ Precipitation", f"{current['precipitation']} mm")
c.metric(f"{icon(current['weather_code'])} Condition", WEATHER_CODES.get(current['weather_code'], 'Unknown'))

# -------------------- TABS --------------------
t1,t2,t3,t4,t5 = st.tabs(["📅 8-Day Forecast","🔎 Specific Date","📆 Between Dates","🔴 Live Mode","🤖 AI Weather Agent"])

with t1:
    st.subheader("📅 Next 8 Days")
    for i, ds in enumerate(daily["time"]):
        code = daily["weather_code"][i]
        with st.container(border=True):
            st.markdown(f"### {icon(code)} {ds} — {day_name(ds)}")
            a,b,c,d = st.columns(4)
            a.metric("🌡️ Max", f"{daily['temperature_2m_max'][i]} °C")
            b.metric("❄️ Min", f"{daily['temperature_2m_min'][i]} °C")
            c.metric("🤒 Feels Max", f"{daily['apparent_temperature_max'][i]} °C")
            d.metric("🥶 Feels Min", f"{daily['apparent_temperature_min'][i]} °C")
            a,b,c,d = st.columns(4)
            a.write(f"🌤️ **Condition:** {WEATHER_CODES.get(code,'Unknown')}")
            b.write(f"🌧️ **Rain:** {daily['rain_sum'][i]} mm")
            c.write(f"☔ **Probability:** {daily['precipitation_probability_max'][i]} %")
            d.write(f"💨 **Max Wind:** {daily['wind_speed_10m_max'][i]} km/h")
            st.write(f"🌅 **Sunrise:** {daily['sunrise'][i]}   |   🌇 **Sunset:** {daily['sunset'][i]}")

with t2:
    st.subheader("🔎 Specific Date")
    first = datetime.strptime(daily["time"][0], "%Y-%m-%d").date()
    last = datetime.strptime(daily["time"][-1], "%Y-%m-%d").date()
    selected_obj = st.date_input("Select date", first, min_value=first, max_value=last, format="YYYY-MM-DD")
    ds = selected_obj.strftime("%Y-%m-%d")
    i = daily_index(weather, ds)
    if i is not None:
        code = daily["weather_code"][i]
        st.markdown(f"## {icon(code)} {ds} — {day_name(ds)}")
        a,b,c,d = st.columns(4)
        a.metric("🌡️ Maximum", f"{daily['temperature_2m_max'][i]} °C")
        b.metric("❄️ Minimum", f"{daily['temperature_2m_min'][i]} °C")
        c.metric("🤒 Feels Max", f"{daily['apparent_temperature_max'][i]} °C")
        d.metric("🥶 Feels Min", f"{daily['apparent_temperature_min'][i]} °C")
        a,b,c,d = st.columns(4)
        a.metric("🌧️ Rain", f"{daily['rain_sum'][i]} mm")
        b.metric("☔ Probability", f"{daily['precipitation_probability_max'][i]} %")
        c.metric("💨 Max Wind", f"{daily['wind_speed_10m_max'][i]} km/h")
        d.metric("🌤️ Condition", WEATHER_CODES.get(code,'Unknown'))
        st.write(f"🌅 **Sunrise:** {daily['sunrise'][i]} | 🌇 **Sunset:** {daily['sunset'][i]}")
        st.divider()
        st.subheader("⏰ 24-Hour Weather")
        for j, tv in enumerate(weather["hourly"]["time"]):
            if tv.startswith(ds):
                h = tv.split("T")[1]
                hc = weather["hourly"]["weather_code"][j]
                with st.expander(f"🕐 {h} — {icon(hc)} {WEATHER_CODES.get(hc,'Unknown')}"):
                    x,y,z,w = st.columns(4)
                    x.write(f"🌡️ **Temperature:** {weather['hourly']['temperature_2m'][j]} °C")
                    y.write(f"🤒 **Feels Like:** {weather['hourly']['apparent_temperature'][j]} °C")
                    z.write(f"💧 **Humidity:** {weather['hourly']['relative_humidity_2m'][j]} %")
                    w.write(f"☔ **Probability:** {weather['hourly']['precipitation_probability'][j]} %")
                    st.write(f"🌧️ **Rain:** {weather['hourly']['rain'][j]} mm | 💨 **Wind:** {weather['hourly']['wind_speed_10m'][j]} km/h")
        if st.button("🤖 Analyze This Date with Gemini", use_container_width=True):
            with st.spinner("Gemini is analyzing..."):
                answer,error = daily_analysis(city,weather,ds)
            if answer: st.markdown(answer)
            else: st.error(error)

with t3:
    st.subheader("📆 Between Two Dates")
    first = datetime.strptime(daily["time"][0], "%Y-%m-%d").date()
    last = datetime.strptime(daily["time"][-1], "%Y-%m-%d").date()
    a,b = st.columns(2)
    start = a.date_input("Start date", first, min_value=first, max_value=last, format="YYYY-MM-DD", key="start")
    end = b.date_input("End date", last, min_value=first, max_value=last, format="YYYY-MM-DD", key="end")
    if start > end:
        st.error("End date cannot be before start date.")
    elif st.button("🔎 Show Selected Range", use_container_width=True):
        cur = start
        while cur <= end:
            ds = cur.strftime("%Y-%m-%d")
            i = daily_index(weather,ds)
            if i is not None:
                code = daily["weather_code"][i]
                with st.container(border=True):
                    st.markdown(f"### {icon(code)} {ds} — {day_name(ds)}")
                    st.write(f"🌤️ **{WEATHER_CODES.get(code,'Unknown')}** | 🌡️ Max {daily['temperature_2m_max'][i]} °C | ❄️ Min {daily['temperature_2m_min'][i]} °C | 🌧️ Rain {daily['rain_sum'][i]} mm | ☔ Probability {daily['precipitation_probability_max'][i]} % | 💨 Wind {daily['wind_speed_10m_max'][i]} km/h")
            cur += timedelta(days=1)

with t4:
    st.subheader("🔴 Live Weather Mode")
    st.write("Automatically refreshes current weather every 10 minutes.")
    live = st.toggle("🔴 Enable Live Mode")
    if live:
        @st.fragment(run_every=600)
        def live_panel():
            try:
                w = get_weather(city["latitude"],city["longitude"],city["timezone"])
                c = w["current"]
                st.success(f"🔄 Updated: {c['time']}")
                a,b,cx,d = st.columns(4)
                a.metric("🌡️ Temperature",f"{c['temperature_2m']} °C")
                b.metric("🤒 Feels Like",f"{c['apparent_temperature']} °C")
                cx.metric("💧 Humidity",f"{c['relative_humidity_2m']} %")
                d.metric("💨 Wind",f"{c['wind_speed_10m']} km/h")
                a,b,cx = st.columns(3)
                a.metric("🌧️ Rain",f"{c['rain']} mm")
                b.metric("☔ Precipitation",f"{c['precipitation']} mm")
                cx.metric(f"{icon(c['weather_code'])} Condition",WEATHER_CODES.get(c['weather_code'],'Unknown'))
            except Exception as e:
                st.error(f"Live refresh failed: {e}")
        live_panel()
    else:
        st.info("Turn on Live Mode to start automatic 10-minute refresh.")

with t5:
    st.subheader("🤖 Ask AI Weather Agent")
    if not gemini_client:
        st.warning("Gemini is not configured. Add GEMINI_API_KEY in Streamlit Secrets.")
    with st.expander("💡 Example questions"):
        st.markdown("""- Will it rain tomorrow?\n- Kal umbrella leke jau?\n- Parso pani aayega?\n- Which day will have the most rain?\n- Which day will be hottest?\n- Which day will be coolest?\n- Which day is best for outdoor activities?\n- What will the weather be like on Sunday?""")
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    question = st.chat_input("Ask anything about the 8-day weather...")
    if question:
        st.session_state.messages.append({"role":"user","content":question})
        with st.chat_message("user"): st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Gemini is thinking..."):
                answer,error = chat_answer(city,weather,question)
            if answer:
                st.markdown(answer)
                st.session_state.messages.append({"role":"assistant","content":answer})
            else:
                msg=f"AI response failed: {error}"
                st.error(msg)
                st.session_state.messages.append({"role":"assistant","content":msg})

st.divider()
st.caption("🌦️ Weather data: Open-Meteo • AI: Gemini")
