# INNA STRAKHOVA — Tattoo & PMU Telegram Bot

Telegram booking bot for one master: Inna Strakhova.

## Features
- AI concierge via OpenRouter for free-text client messages;
- deterministic booking flow with real slot checks;
- production working hours are configured as 11:00–18:00;
- tattoo sessions: 3–4 hours — 12,000 ₽; 6–7 hours — 16,000 ₽;
- PMU: lips 5,000 ₽; brows 5,000 ₽; correction 3,000 ₽; refresh 4,000 ₽;
- healing cream included as a gift;
- references/photos from clients;
- private owner inbox for @inna_strakhova;
- cancel/reschedule;
- day-before confirmation;
- owner commands: /today, /tomorrow, /bookings;
- portfolio assets for tattoo and PMU;
- payment module will be connected later.

## Environment
Copy `.env.example` to `.env` locally or set variables in Render. Never commit secrets.

Required:
- `BOT_TOKEN`

Optional:
- `OPENROUTER_API_KEY` for AI mode; booking and owner notifications still work without it
- `OPENROUTER_MODEL`
- `OWNER_USERNAME` (default `inna_strakhova`)
- `OWNER_CHAT_ID`
- `TZ` (default `Europe/Moscow`)
- `WORK_START` (production: `11:00`)
- `WORK_END` (production: `18:00`)

## Start
```bash
pip install -r requirements.txt
python render_run.py
```
