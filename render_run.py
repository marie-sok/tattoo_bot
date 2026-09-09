import asyncio
import hashlib
import os
from datetime import datetime, time, timedelta
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import config
from app import db
import app.main as app_main
from app.owner_inbox import owner_inbox_cmd
from app.keyboards import main_kb, service_kb, tattoo_size_kb, pmu_kb
from app.main import (
    Booking,
    ai_chat,
    all_bookings,
    begin,
    cancel_cb,
    choose_date,
    choose_time,
    confirm,
    finish,
    get_name,
    get_phone,
    move_begin,
    move_date,
    move_time,
    my_booking,
    owner_list,
    reference,
    TZ,
    dtfmt,
    booking_actions,
)

ROOT = Path(__file__).resolve().parent
WORK_START = "11:00"
WORK_END = "18:00"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", "https://inna-tattoo-bot.onrender.com").rstrip("/")
WEBHOOK_PATH = "/telegram/webhook"
TRANSPORT = "starting"
TELEGRAM_OK = False

PRICE_TEXT = (
    "💰 <b>Цены Инны</b>\n\n"
    "🖋 Татуировка\n"
    "• 1 сеанс 3–4 часа — <b>12 000 ₽</b>\n"
    "• 1 сеанс 6–7 часов — <b>16 000 ₽</b>\n\n"
    "✨ Перманентный макияж\n"
    "• Губы — <b>5 000 ₽</b>\n"
    "• Брови — <b>5 000 ₽</b>\n"
    "• Коррекция через 1–1,5 месяца — <b>3 000 ₽</b>\n"
    "• Рефреш бровей через 1–2 года — <b>4 000 ₽</b>\n"
    "• Рефреш губ через 1–2 года — <b>4 000 ₽</b>\n\n"
    "🎁 Заживляющий крем — в подарок."
)


def _clock(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


async def runtime_slots_for(d, duration: int, exclude=None):
    start = datetime.combine(d, _clock(WORK_START), TZ)
    end = datetime.combine(d, _clock(WORK_END), TZ)
    out = []
    cur = start
    while cur + timedelta(minutes=duration) <= end:
        finish_at = cur + timedelta(minutes=duration)
        if cur > datetime.now(TZ) and not await db.overlaps(
            cur.replace(tzinfo=None), finish_at.replace(tzinfo=None), exclude
        ):
            out.append(cur)
        cur += timedelta(minutes=30)
    return out


app_main.slots_for = runtime_slots_for


async def private_start(message, state):
    username = (message.from_user.username or "").lower()
    if username == config.owner_username:
        await state.clear()
        await owner_inbox_cmd(message)
        await message.answer(
            "🖤 <b>Кабинет Инны</b>\n\n"
            "Новые записи, заявки, переносы, отмены и подтверждения будут приходить сюда автоматически.\n"
            "Этот inbox работает независимо от OpenRouter/AI.\n\n"
            "Команды: /today · /tomorrow · /bookings"
        )
        return

    await state.clear()
    await message.answer(
        "✨ <b>INNA STRAKHOVA · Tattoo & PMU</b>\n\n"
        f"Рабочее время: <b>{WORK_START}–{WORK_END}</b>.\n"
        "Напиши своими словами, что хочешь сделать, или используй кнопки.",
        reply_markup=main_kb(),
    )


async def prices_cmd(message):
    await message.answer(PRICE_TEXT, reply_markup=main_kb())


async def service_cb(c, state):
    service = c.data.split(':', 1)[1]
    if service == 'tattoo':
        await state.update_data(service='Татуировка')
        await state.set_state(Booking.detail)
        await c.message.answer(
            'Выбери длительность сеанса. Для календаря резервируем верхнюю границу времени:',
            reply_markup=tattoo_size_kb(),
        )
    else:
        await state.update_data(service='Перманентный макияж', duration=90)
        await state.set_state(Booking.detail)
        await c.message.answer('Выбери процедуру:', reply_markup=pmu_kb())
    await c.answer()


async def detail_cb(c, state):
    if c.data.startswith('size:'):
        duration = int(c.data.split(':', 1)[1])
        labels = {
            240: 'Сеанс 3–4 часа · 12 000 ₽',
            420: 'Сеанс 6–7 часов · 16 000 ₽',
        }
        label = labels.get(duration)
        if not label:
            await c.answer('Неизвестный вариант', show_alert=True)
            return
        await state.update_data(duration=duration, detail=label)
    else:
        code = c.data.split(':', 1)[1]
        labels = {
            'lips': 'Губы · 5 000 ₽',
            'brows': 'Брови · 5 000 ₽',
            'correction': 'Коррекция через 1–1,5 месяца · 3 000 ₽',
            'refresh_brows': 'Рефреш бровей через 1–2 года · 4 000 ₽',
            'refresh_lips': 'Рефреш губ через 1–2 года · 4 000 ₽',
        }
        label = labels.get(code)
        if not label:
            await c.answer('Неизвестная процедура', show_alert=True)
            return
        await state.update_data(detail=label)

    await state.set_state(Booking.reference)
    await c.message.answer(
        'Пришли референс/фото одним изображением. Если нет — напиши <b>нет</b>.\n\n'
        '🎁 Заживляющий крем — в подарок.'
    )
    await c.answer()


async def safe_portfolio(message, bot: Bot):
    """One bad image is skipped; it can never take down the portfolio handler."""
    await message.answer('🖤 <b>Работы Инны</b>')
    tattoo_dir = ROOT / 'assets' / 'portfolio' / 'tattoo'
    pmu_dir = ROOT / 'assets' / 'portfolio' / 'pmu'

    tattoo_files = sorted(
        p for p in tattoo_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ) if tattoo_dir.exists() else []
    pmu_files = sorted(
        p for p in pmu_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ) if pmu_dir.exists() else []

    sent = 0
    failed = 0
    for photo_path in tattoo_files[:9] + pmu_files[:3]:
        try:
            await bot.send_photo(message.chat.id, FSInputFile(photo_path))
            sent += 1
        except Exception as exc:
            failed += 1
            print(f"portfolio skip {photo_path.name}: {type(exc).__name__}: {exc}", flush=True)

    if sent == 0:
        await message.answer(
            'Сейчас фотографии временно недоступны, но запись и остальные функции работают 🖤',
            reply_markup=main_kb(),
        )
    elif failed:
        await message.answer(
            'Часть фотографий обновляется. Остальные работы уже показала 🖤',
            reply_markup=main_kb(),
        )


async def today_cmd(message):
    await owner_list(message, 0)


async def tomorrow_cmd(message):
    await owner_list(message, 1)


async def group_booking_entry(message, bot: Bot):
    me = await bot.get_me()
    deep_link = f"https://t.me/{me.username}?start=inna_kolor"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Записаться к Инне", url=deep_link)],
        [InlineKeyboardButton(text="💰 Цены", url=f"https://t.me/{me.username}?start=prices")],
        [InlineKeyboardButton(text="🖤 Группа Инны", url=f"https://t.me/{config.group_username}")],
    ])
    await message.answer(
        "Запись ведём в личном чате с ботом — там безопасно отправлять телефон, референс и выбирать свободное время 🖤",
        reply_markup=kb,
    )


async def reminder_job(bot: Bot):
    now = datetime.now(TZ).replace(tzinfo=None)
    tomorrow = (now + timedelta(days=1)).date()
    day_start = datetime.combine(tomorrow, time.min)
    rows = await db.reminders_due(day_start, day_start + timedelta(days=1))
    for row in rows:
        try:
            await bot.send_message(
                row['user_id'],
                f"✨ <b>Завтра встречаемся</b>\n\n{row['service']} · {row['detail']}\n📅 {dtfmt(row['start_at'])}\n\nПодтверди, пожалуйста, что всё в силе.",
                reply_markup=booking_actions(row['id']),
            )
            await db.mark_reminder(row['id'])
        except Exception as exc:
            print(f"reminder error booking={row['id']}: {exc}", flush=True)


async def health(_request):
    return web.json_response({
        "ok": True,
        "service": "inna_tattoo_bot",
        "telegram_ok": TELEGRAM_OK,
        "transport": TRANSPORT,
        "ai_configured": bool(config.openrouter_api_key),
        "offline_fallback": True,
        "owner_inbox": True,
        "work_hours": f"{WORK_START}-{WORK_END}",
        "group": f"@{config.group_username}",
    })


async def start_web_server(bot: Bot, dp: Dispatcher, secret: str):
    async def telegram_webhook(request: web.Request):
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
            return web.Response(status=403, text="forbidden")
        try:
            payload = await request.json()
            update = Update.model_validate(payload, context={"bot": bot})
            await dp.feed_update(bot, update)
            return web.Response(text="ok")
        except Exception as exc:
            # Always return 200 after logging. Telegram retries non-2xx responses;
            # a poison update must not create an endless retry storm.
            print(f"webhook update error: {type(exc).__name__}: {exc}", flush=True)
            return web.Response(text="ignored")

    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    app.router.add_post(WEBHOOK_PATH, telegram_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', config.port).start()
    return runner


def register_handlers(dp: Dispatcher):
    dp.message.register(private_start, CommandStart(), F.chat.type == 'private')
    dp.message.register(owner_inbox_cmd, Command('inbox'), F.chat.type == 'private')
    dp.message.register(owner_inbox_cmd, Command('owner'), F.chat.type == 'private')
    dp.message.register(begin, F.text == '✨ Записаться', F.chat.type == 'private')
    dp.message.register(safe_portfolio, F.text == '🖤 Работы Инны', F.chat.type == 'private')
    dp.message.register(prices_cmd, F.text == '💰 Цены', F.chat.type == 'private')
    dp.message.register(my_booking, F.text == '📅 Моя запись', F.chat.type == 'private')
    dp.message.register(today_cmd, Command('today'), F.chat.type == 'private')
    dp.message.register(tomorrow_cmd, Command('tomorrow'), F.chat.type == 'private')
    dp.message.register(all_bookings, Command('bookings'), F.chat.type == 'private')
    dp.message.register(group_booking_entry, Command('book'), F.chat.type.in_({'group', 'supergroup'}))
    dp.message.register(group_booking_entry, Command('booking'), F.chat.type.in_({'group', 'supergroup'}))

    dp.callback_query.register(service_cb, F.data.startswith('svc:'))
    dp.callback_query.register(detail_cb, F.data.startswith('size:') | F.data.startswith('pmu:'))
    dp.message.register(reference, Booking.reference, F.photo | F.text)
    dp.callback_query.register(choose_date, Booking.date, F.data.startswith('date:'))
    dp.callback_query.register(choose_time, Booking.time, F.data.startswith('slot:'))
    dp.message.register(get_name, Booking.name)
    dp.message.register(get_phone, Booking.phone)
    dp.message.register(finish, Booking.comment)
    dp.callback_query.register(cancel_cb, F.data.startswith('cancel:') | F.data.startswith('owncancel:'))
    dp.callback_query.register(move_begin, F.data.startswith('move:'))
    dp.callback_query.register(move_date, Booking.move_date, F.data.startswith('mdate:'))
    dp.callback_query.register(move_time, Booking.move_time, F.data.startswith('mslot:'))
    dp.callback_query.register(confirm, F.data.startswith('confirm:'))

    # OpenRouter is optional; ai_chat has deterministic offline fallback.
    dp.message.register(ai_chat, F.text, F.chat.type == 'private')


async def polling_fallback(bot: Bot, dp: Dispatcher):
    global TRANSPORT, TELEGRAM_OK
    TRANSPORT = "polling-fallback"
    while True:
        try:
            await asyncio.wait_for(bot.delete_webhook(drop_pending_updates=False), timeout=15)
            me = await asyncio.wait_for(bot.get_me(), timeout=15)
            TELEGRAM_OK = True
            print(f"polling fallback auth OK @{me.username}", flush=True)
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                polling_timeout=20,
                close_bot_session=False,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            TELEGRAM_OK = False
            print(f"polling fallback restart: {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(5)


async def main():
    global TRANSPORT, TELEGRAM_OK
    if not config.token:
        raise RuntimeError('BOT_TOKEN missing')

    await db.init_db()
    bot = Bot(config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    register_handlers(dp)

    scheduler = AsyncIOScheduler(timezone=config.tz)
    scheduler.add_job(reminder_job, 'cron', hour=18, minute=0, args=[bot])
    scheduler.start()

    secret = hashlib.sha256(config.token.encode("utf-8")).hexdigest()[:48]
    web_runner = await start_web_server(bot, dp, secret)
    print(f"HTTP health ready on port {config.port}", flush=True)

    try:
        try:
            me = await asyncio.wait_for(bot.get_me(), timeout=15)
            await asyncio.wait_for(
                bot.set_webhook(
                    f"{PUBLIC_URL}{WEBHOOK_PATH}",
                    secret_token=secret,
                    allowed_updates=dp.resolve_used_update_types(),
                    drop_pending_updates=False,
                ),
                timeout=15,
            )
            TELEGRAM_OK = True
            TRANSPORT = "webhook"
            print(
                f"INNA bot ready | telegram=@{me.username} | transport=webhook | "
                f"offline_fallback=True | work={WORK_START}-{WORK_END}",
                flush=True,
            )
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"webhook startup failed: {type(exc).__name__}: {exc}; using polling fallback", flush=True)
            await polling_fallback(bot, dp)
    finally:
        scheduler.shutdown(wait=False)
        await web_runner.cleanup()
        await bot.session.close()


def cli():
    asyncio.run(main())


if __name__ == '__main__':
    cli()
