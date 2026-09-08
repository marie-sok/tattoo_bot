import asyncio
from datetime import datetime, time, timedelta

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import config
from app import db
from app.main import (
    Booking,
    ai_chat,
    all_bookings,
    begin,
    cancel_cb,
    choose_date,
    choose_time,
    confirm,
    detail,
    finish,
    get_name,
    get_phone,
    move_begin,
    move_date,
    move_time,
    my_booking,
    owner_list,
    portfolio,
    reference,
    start,
    svc,
    TZ,
    dtfmt,
    booking_actions,
)


async def today_cmd(message):
    await owner_list(message, 0)


async def tomorrow_cmd(message):
    await owner_list(message, 1)


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
            print(f"reminder error booking={row['id']}: {exc}")


async def health(_request):
    return web.json_response({
        "ok": True,
        "service": "inna_tattoo_bot",
        "ai": bool(config.openrouter_api_key),
        "model": config.openrouter_model,
    })


async def start_health_server():
    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', config.port).start()
    return runner


async def main():
    if not config.token:
        raise RuntimeError('BOT_TOKEN missing')

    await db.init_db()
    bot = Bot(
        config.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.register(start, CommandStart())
    dp.message.register(begin, F.text == '✨ Записаться')
    dp.message.register(portfolio, F.text == '🖤 Работы Инны')
    dp.message.register(my_booking, F.text == '📅 Моя запись')
    dp.message.register(today_cmd, Command('today'))
    dp.message.register(tomorrow_cmd, Command('tomorrow'))
    dp.message.register(all_bookings, Command('bookings'))

    dp.callback_query.register(svc, F.data.startswith('svc:'))
    dp.callback_query.register(detail, F.data.startswith('size:') | F.data.startswith('pmu:'))
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

    # Last handler: all free-text messages go to OpenRouter concierge.
    dp.message.register(ai_chat, F.text)

    scheduler = AsyncIOScheduler(timezone=config.tz)
    scheduler.add_job(reminder_job, 'cron', hour=18, minute=0, args=[bot])
    scheduler.start()
    health_runner = await start_health_server()

    print(
        f"INNA bot started | ai={bool(config.openrouter_api_key)} | "
        f"model={config.openrouter_model} | port={config.port}"
    )
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await health_runner.cleanup()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
