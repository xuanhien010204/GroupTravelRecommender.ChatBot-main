@echo off
echo Starting Group Travel Recommender...
echo.
echo Make sure you have:
echo 1. Created a .env file with your Azure OpenAI credentials
echo 2. Installed dependencies with: pip install -r requirements.txt
echo.
pause
streamlit run app.py
