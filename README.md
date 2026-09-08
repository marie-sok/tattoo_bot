# INNA STRAKHOVA — Tattoo & PMU Telegram Bot

Telegram booking bot for one master: Inna Strakhova.

## Features
- AI concierge via OpenRouter for free-text client messages;
- deterministic booking flow with real slot checks;
- working hours 10:00–22:00;
- PMU: 90 minutes;
- tattoo: 60/120/180 minutes by size;
- references/photos from clients;
- owner notifications for @inna_strakhova;
- cancel/reschedule;
- day-before confirmation;
- owner commands: /today, /tomorrow, /bookings;
- payment module will be connected later.

## Environment
Copy `.env.example` to `.env` locally or set variables in Render. Never commit secrets.

Required:
- `BOT_TOKEN`
- `OPENROUTER_API_KEY` for AI mode

Optional:
- `OPENROUTER_MODEL` (default `openai/gpt-5.3-chat`)
- `OWNER_USERNAME` (default `inna_strakhova`)
- `TZ` (default `Europe/Moscow`)

## Start
```bash
pip install -r requirements.txt
python run.py
```
