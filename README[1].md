# 🌦️ AI Weather Agent Web

A Streamlit weather application with:

- User-selected city
- Current weather
- 8-day forecast
- Specific date search
- Full 24-hour hourly weather for the selected date
- Weather between two dates
- Live weather refresh
- Gemini AI weather chat
- English / Hindi / Hinglish questions

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Gemini API key

For Streamlit Cloud, add this in:

App Settings → Secrets

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

Do NOT put the API key in GitHub, app.py, or requirements.txt.

## Deploy

Upload these files to the root of your GitHub repository:

- app.py
- requirements.txt
- README.md
- .gitignore

In Streamlit, select:

Repository: your GitHub repository
Branch: main
Main file path: app.py
