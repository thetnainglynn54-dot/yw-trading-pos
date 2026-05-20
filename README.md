# YW Trading POS - Online Web App

This Streamlit POS can run as one online web app for Android, iOS, iPad, tablets, Windows, and macOS through a browser.

## Local run

```powershell
pip install -r requirements.txt
streamlit run pos_app.py
```

Open: http://localhost:8501

## Deploy checklist

1. Rotate the Google service account private key before publishing this project.
2. Do not upload `.streamlit/secrets.toml`, `*.json` service-account files, or local `*.db` files to GitHub.
3. Put the same values from `.streamlit/secrets.toml` into the hosting provider's secret manager.
4. Deploy `pos_app.py`, `assets.py`, `requirements.txt`, and `.streamlit/config.toml`.
5. Share the deployed URL with users. They can open it from phone, tablet, iPad, Windows, or Mac.

Use `.streamlit/secrets.example.toml` as the template for hosting secrets. Never paste real private keys into public files.

## Recommended hosting

- Streamlit Community Cloud for the fastest first online version.
- Render, Railway, or Google Cloud Run for a more production-style deployment.

## Phone/tablet use

After deployment, users can add the web app to their home screen from the browser menu. It will behave like an app shortcut while still using the online database.
