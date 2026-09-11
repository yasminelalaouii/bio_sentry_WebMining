@echo off
echo ==========================================
echo   Bio-Sentry Dashboard - Demarrage...
echo ==========================================
pip install streamlit plotly pandas numpy Pillow --quiet
streamlit run app.py
pause
