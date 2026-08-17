# AI Weather Agent

A Streamlit web app with:
- Current weather
- 8-day forecast
- Specific date + 24-hour forecast
- Live refresh
- Gemini AI weather chat
- English / Hindi / Hinglish questions

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

For Gemini AI locally, either set:
GEMINI_API_KEY=your_key

or use Streamlit secrets.

## Deploy

Push this folder to GitHub and deploy `app.py` on Streamlit Community Cloud.
Add `GEMINI_API_KEY` in the app's Secrets settings.
