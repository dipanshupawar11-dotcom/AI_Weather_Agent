# 🌦️ AI Weather Agent
[Open AI Weather Agent](https://aiweatheragent-que7fcgavvxu794simgu36.streamlit.app/)

A Streamlit-based AI Weather Agent with hourly weather, 8-day forecasts, date search, date-range weather, live weather, and a Gemini-powered AI Assistant.

## Features

1. **City Search & Validation**
   - Enter a city.
   - City is resolved using Open-Meteo geocoding.

2. **Today — 24 Hours**
   - Hour-by-hour temperature.
   - Feels-like temperature.
   - Humidity.
   - Rain probability.
   - Rain amount.
   - Wind.
   - Weather condition.

3. **🤖 Talk with AI Agent**
   - Ask weather questions in English, Hindi, or Hinglish.
   - AI uses the loaded hourly weather data as context.
   - Uses Gemini through REST API, so the `google-genai` Python package is not required.

4. **8-Day Forecast**
   - Select any available forecast day.
   - View its hourly weather.

5. **Specific Date**
   - Select a date.
   - View the complete available hourly weather for that date.

6. **Between Dates**
   - Select start and end dates.
   - View hourly weather across the selected range.

7. **Live Weather**
   - Current temperature, feels-like temperature, humidity, wind, and condition.
   - Refresh button.

## Project Structure

```text
AI_Weather_Agent/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    └── config.toml
```

## Run Locally

### 1. Create a virtual environment

```bash
python -m venv venv
```

### 2. Activate it on Windows

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add Gemini API key

Create:

```text
.streamlit/secrets.toml
```

and add:

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

Never commit this file to GitHub.

### 5. Run

```bash
streamlit run app.py
```

## Streamlit Cloud Deployment

1. Push the project to GitHub.
2. Open Streamlit Community Cloud.
3. Select the GitHub repository.
4. Set the main file to:

```text
app.py
```

5. Open the app's **Secrets** settings.
6. Add:

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

7. Deploy.

## API Design

### Weather and Geocoding

The project uses **Open-Meteo** APIs. No weather API key is required.

### AI

The project calls the Gemini REST API directly with `requests`.

This intentionally avoids:

```text
google-genai
```

so the project does not depend on the Python Gemini SDK package.

## Security

- Do not put API keys inside `app.py`.
- Do not commit `.streamlit/secrets.toml`.
- Do not commit `.env`.
- Use Streamlit Cloud Secrets for deployment.

## Notes

Forecast availability depends on the weather provider's forecast window and timezone. The UI displays all hourly records returned for the selected dates.

