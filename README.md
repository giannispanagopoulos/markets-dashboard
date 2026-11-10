# Markets Dashboard

A live market dashboard for US and Greek stocks, deployed on an Oracle Cloud
Always Free VM (Ubuntu 24.04, ARM).

- Backend: Python, FastAPI, uvicorn, yfinance
- Frontend: plain HTML, CSS, JavaScript with SVG charts
- Deployment: systemd service, Nginx reverse proxy, Let's Encrypt HTTPS
- Data refresh: every 60 seconds from Yahoo Finance (may be delayed)

Live demo: https://giannis-markets.duckdns.org
   ![Dashboard screenshot](Screenshot%20From%202026-11-10%2014-14-45.png)

## Run locally
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --host 127.0.0.1 --port 8000
