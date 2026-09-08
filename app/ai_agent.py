import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config import config


SYSTEM_PROMPT = """Ты — Telegram-администратор мастера Inna Strakhova, которая делает татуировки и перманентный макияж.
Твоя задача — тепло и кратко отвечать клиентам, квалифицировать запрос и доводить до записи.

Факты, которые нельзя менять:
- мастер один: Инна Страхова;
- рабочее время: 11:00–18:00;
- реальные свободные даты/время определяет только система бронирования. Никогда не придумывай свободные слоты;
- татуировка: один сеанс 3–4 часа — 12 000 ₽; один сеанс 6–7 часов — 16 000 ₽;
- перманентный макияж губ — 5 000 ₽;
- перманентный макияж бровей — 5 000 ₽;
- коррекция через 1–1,5 месяца — 3 000 ₽;
- рефреш бровей через 1–2 года — 4 000 ₽;
- рефреш губ через 1–2 года — 4 000 ₽;
- заживляющий крем клиент получает в подарок;
- запись можно перенести или отменить через бота;
- за день до сеанса бот просит подтвердить запись;
- уведомления Инне о заявках и записях отправляются отдельной детерминированной логикой и не зависят от AI/OpenRouter.

Не ставь медицинские диагнозы и не давай медицинских гарантий. Для противопоказаний и индивидуальных рисков рекомендуй обсудить вопрос с мастером и при необходимости врачом.

Верни СТРОГО JSON без markdown в формате:
{
  "reply": "короткий ответ клиенту на русском",
  "intent": "book|portfolio|my_booking|question|handoff",
  "service": "tattoo|pmu|unknown",
  "tattoo_duration": null,
  "pmu_detail": "Брови|Губы|Коррекция|Рефреш бровей|Рефреш губ|null"
}

Правила intent:
- book — клиент хочет записаться, выбрать дату/время или явно описывает желаемую процедуру;
- portfolio — хочет посмотреть работы/примеры;
- my_booking — спрашивает про свою существующую запись, перенос или отмену;
- handoff — сложный индивидуальный вопрос, противопоказания/осложнения, или нужен ответ самой Инны;
- question — остальные вопросы.

Для татуировки tattoo_duration всегда null: длительность сеанса клиент выбирает кнопкой 3–4 или 6–7 часов, чтобы календарь резервировал правильное окно.
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


def offline_agent(user_text: str) -> AgentResult:
    """Deterministic fallback used when OpenRouter is missing or unavailable."""
    text = user_text.lower().strip()

    if any(x in text for x in ("работы", "портфолио", "примеры", "фото работ")):
        return AgentResult("Конечно 🖤 Показываю работы Инны.", intent="portfolio")

    if any(x in text for x in ("моя запись", "перенести", "перенос", "отменить", "отмена")):
        return AgentResult("Проверяю твою активную запись.", intent="my_booking")

    tattoo = any(x in text for x in ("тату", "татую", "эскиз", "набить"))
    pmu = any(x in text for x in ("перманент", "пму", "бров", "губ", "коррекц", "рефреш"))
    booking = any(x in text for x in ("запис", "хочу", "свобод", "окно", "дата", "время"))

    if tattoo or (booking and not pmu):
        return AgentResult(
            "Поняла 🖤 Давай оформим запись на татуировку. Выберем длительность сеанса — 3–4 или 6–7 часов.",
            intent="book",
            service="tattoo",
            tattoo_duration=None,
        )

    if pmu:
        detail = None
        if "коррекц" in text:
            detail = "Коррекция"
        elif "рефреш" in text and "бров" in text:
            detail = "Рефреш бровей"
        elif "рефреш" in text and "губ" in text:
            detail = "Рефреш губ"
        elif "бров" in text:
            detail = "Брови"
        elif "губ" in text:
            detail = "Губы"
        return AgentResult(
            "Поняла 🖤 Давай оформим запись на перманентный макияж.",
            intent="book",
            service="pmu",
            pmu_detail=detail,
        )

    if any(x in text for x in ("цена", "стоимость", "сколько", "прайс")):
        return AgentResult(
            "Тату: 3–4 часа — 12 000 ₽, 6–7 часов — 16 000 ₽. Губы и брови — по 5 000 ₽, коррекция — 3 000 ₽, рефреш — 4 000 ₽. Заживляющий крем — в подарок 🖤",
            intent="question",
        )

    if booking:
        return AgentResult("Давай запишем тебя 🖤", intent="book", service="unknown")

    return AgentResult(
        "Я сейчас работаю в автономном режиме. Запись, перенос, отмена и уведомления Инне работают как обычно 🖤",
        intent="question",
    )


async def ask_agent(user_text: str) -> AgentResult:
    if not config.openrouter_api_key:
        return offline_agent(user_text)

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
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = _clean_json(content)
            detail = data.get("pmu_detail")
            allowed_details = {"Брови", "Губы", "Коррекция", "Рефреш бровей", "Рефреш губ"}
            if detail not in allowed_details:
                detail = None
            return AgentResult(
                reply=str(data.get("reply") or "Расскажи чуть подробнее, что хочешь сделать 🖤"),
                intent=str(data.get("intent") or "question"),
                service=str(data.get("service") or "unknown"),
                tattoo_duration=None,
                pmu_detail=detail,
            )
    except Exception as exc:
        print(f"OpenRouter unavailable, offline fallback enabled: {type(exc).__name__}")
        return offline_agent(user_text)
