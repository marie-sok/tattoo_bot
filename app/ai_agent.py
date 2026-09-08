import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config import config


SYSTEM_PROMPT = """Ты — Telegram-администратор мастера Inna Strakhova, которая делает татуировки и перманентный макияж.
Твоя задача — тепло и кратко отвечать клиентам, квалифицировать запрос и доводить до записи.

Факты, которые нельзя менять:
- мастер один: Инна Страхова;
- рабочее время: 10:00–22:00;
- перманентный макияж длится 90 минут;
- татуировка: минимум 60 минут; ориентир по размеру: до 5 см — 60 минут, 5–15 см — 120 минут, больше 15 см — 180 минут;
- реальные свободные даты/время определяет только система бронирования. Никогда не придумывай свободные слоты;
- предоплата 1000 ₽ будет подключена позже, сейчас оплату не принимай и не обещай, что она уже работает;
- запись можно перенести или отменить через бота;
- за день до сеанса бот просит подтвердить запись.

Не ставь медицинские диагнозы и не давай медицинских гарантий. Для противопоказаний и индивидуальных рисков рекомендуй обсудить вопрос с мастером и при необходимости врачом.

Верни СТРОГО JSON без markdown в формате:
{
  "reply": "короткий ответ клиенту на русском",
  "intent": "book|portfolio|my_booking|question|handoff",
  "service": "tattoo|pmu|unknown",
  "tattoo_duration": 60|120|180|null,
  "pmu_detail": "Брови|Губы|Межресничка|null"
}

Правила intent:
- book — клиент хочет записаться, выбрать дату/время или явно описывает желаемую процедуру;
- portfolio — хочет посмотреть работы/примеры;
- my_booking — спрашивает про свою существующую запись, перенос или отмену;
- handoff — сложный вопрос, цена индивидуальной татуировки, противопоказания/осложнения, или нужен ответ самой Инны;
- question — остальные вопросы.

Если клиент хочет тату, но размер непонятен, tattoo_duration=null. Если PMU-процедура неясна, pmu_detail=null.
"""


@dataclass
class AgentResult:
    reply: str
    intent: str = "question"
    service: str = "unknown"
    tattoo_duration: int | None = None
    pmu_detail: str | None = None


def _clean_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


async def ask_agent(user_text: str) -> AgentResult | None:
    if not config.openrouter_api_key:
        return None

    payload = {
        "model": config.openrouter_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text[:4000]},
        ],
        "temperature": 0.25,
        "max_tokens": 500,
    }
    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.openrouter_site_url,
        "X-Title": "Inna Strakhova Tattoo & PMU Bot",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = _clean_json(content)
            duration = data.get("tattoo_duration")
            if duration not in (60, 120, 180):
                duration = None
            detail = data.get("pmu_detail")
            if detail not in ("Брови", "Губы", "Межресничка"):
                detail = None
            return AgentResult(
                reply=str(data.get("reply") or "Расскажи чуть подробнее, что хочешь сделать 🖤"),
                intent=str(data.get("intent") or "question"),
                service=str(data.get("service") or "unknown"),
                tattoo_duration=duration,
                pmu_detail=detail,
            )
    except Exception:
        return None
