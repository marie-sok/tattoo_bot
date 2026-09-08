import asyncio
from datetime import datetime, date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import config
from . import db
from .keyboards import main_kb, service_kb, tattoo_size_kb, pmu_kb, booking_actions, owner_actions
from .ai_agent import ask_agent

TZ = ZoneInfo(config.tz)
ROOT = Path(__file__).resolve().parents[1]


class Booking(StatesGroup):
    service = State(); detail = State(); reference = State(); date = State(); time = State()
    name = State(); phone = State(); comment = State(); move_date = State(); move_time = State()


def dtfmt(v):
    return datetime.fromisoformat(v).strftime('%d.%m.%Y · %H:%M')


def owner_text(r):
    user = f" (@{r['username']})" if r['username'] else ''
    return (f"🔔 <b>Запись #{r['id']}</b>\n👤 {r['name']}{user}\n☎️ {r['phone'] or 'не указан'}\n\n"
            f"✨ <b>{r['service']}</b>\n{r['detail'] or ''}\n📅 {dtfmt(r['start_at'])}\n"
            f"⏳ {r['duration']} мин\n💬 {r['comment'] or '—'}")


async def owner_id():
    value = await db.setting_get('owner_chat_id')
    return int(value) if value else None


async def maybe_bind_owner(m: Message):
    if m.from_user.username and m.from_user.username.lower() == config.owner_username:
        await db.setting_set('owner_chat_id', m.chat.id)
        return True
    return False


def date_keyboard(prefix='date', days=21):
    rows = []
    today = datetime.now(TZ).date()
    for i in range(days):
        d = today + timedelta(days=i)
        rows.append([InlineKeyboardButton(text=d.strftime('%d.%m'), callback_data=f'{prefix}:{d.isoformat()}')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def slots_for(d: date, duration: int, exclude=None):
    start = datetime.combine(d, time(10, 0), TZ)
    end = datetime.combine(d, time(22, 0), TZ)
    out = []
    cur = start
    while cur + timedelta(minutes=duration) <= end:
        finish = cur + timedelta(minutes=duration)
        if cur > datetime.now(TZ) and not await db.overlaps(cur.replace(tzinfo=None), finish.replace(tzinfo=None), exclude):
            out.append(cur)
        cur += timedelta(minutes=30)
    return out


def slots_kb(slots, prefix='slot'):
    rows = []
    for i in range(0, len(slots), 3):
        rows.append([InlineKeyboardButton(text=x.strftime('%H:%M'), callback_data=f'{prefix}:{x.isoformat()}') for x in slots[i:i+3]])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start(m: Message, state: FSMContext):
    await maybe_bind_owner(m)
    await state.clear()
    await m.answer("✨ <b>INNA STRAKHOVA · Tattoo & PMU</b>\n\nНапиши своими словами, что хочешь сделать, или используй кнопки. Работаем ежедневно с <b>10:00 до 22:00</b>.", reply_markup=main_kb())


async def begin(m: Message, state: FSMContext):
    await state.clear(); await state.set_state(Booking.service)
    await m.answer('Что планируем?', reply_markup=service_kb())


async def svc(c: CallbackQuery, state: FSMContext):
    s = c.data.split(':')[1]
    if s == 'tattoo':
        await state.update_data(service='Татуировка'); await state.set_state(Booking.detail)
        await c.message.answer('Выбери примерный размер:', reply_markup=tattoo_size_kb())
    else:
        await state.update_data(service='Перманентный макияж', duration=90); await state.set_state(Booking.detail)
        await c.message.answer('Какая процедура?', reply_markup=pmu_kb())
    await c.answer()


async def detail(c: CallbackQuery, state: FSMContext):
    if c.data.startswith('size:'):
        dur = int(c.data.split(':')[1]); labels = {60:'До 5 см', 120:'5–15 см', 180:'Больше 15 см'}
        await state.update_data(duration=dur, detail=labels[dur])
    else:
        await state.update_data(detail=c.data.split(':',1)[1])
    await state.set_state(Booking.reference)
    await c.message.answer('Пришли референс/фото одним изображением. Если нет — напиши <b>нет</b>.')
    await c.answer()


async def reference(m: Message, state: FSMContext):
    fid = m.photo[-1].file_id if m.photo else None
    await state.update_data(reference_file_id=fid); await state.set_state(Booking.date)
    await m.answer('Выбери дату:', reply_markup=date_keyboard())


async def choose_date(c: CallbackQuery, state: FSMContext):
    d = date.fromisoformat(c.data.split(':')[1]); data = await state.get_data(); slots = await slots_for(d, data['duration'])
    if not slots:
        await c.answer('На эту дату свободных окон нет', show_alert=True); return
    await state.set_state(Booking.time); await c.message.answer('Свободное время:', reply_markup=slots_kb(slots)); await c.answer()


async def choose_time(c: CallbackQuery, state: FSMContext):
    start_at = datetime.fromisoformat(c.data.split(':',1)[1]); data = await state.get_data(); end_at = start_at + timedelta(minutes=data['duration'])
    if await db.overlaps(start_at.replace(tzinfo=None), end_at.replace(tzinfo=None)):
        await c.answer('Этот слот только что заняли', show_alert=True); return
    await state.update_data(start_at=start_at.replace(tzinfo=None), end_at=end_at.replace(tzinfo=None)); await state.set_state(Booking.name)
    await c.message.answer('Как тебя зовут?'); await c.answer()


async def get_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip()); await state.set_state(Booking.phone); await m.answer('Оставь номер телефона для связи:')


async def get_phone(m: Message, state: FSMContext):
    await state.update_data(phone=m.text.strip()); await state.set_state(Booking.comment)
    await m.answer('Комментарий для Инны: зона, пожелания, особенности. Если нечего добавить — напиши <b>нет</b>.')


async def finish(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    data.update(user_id=m.from_user.id, username=m.from_user.username, comment=None if m.text.lower() == 'нет' else m.text)
    if await db.overlaps(data['start_at'], data['end_at']):
        await state.clear(); await m.answer('Пока заполняли анкету, время заняли. Начни запись заново.', reply_markup=main_kb()); return
    bid = await db.create_booking(data); r = await db.get_booking(bid)
    await m.answer(f"Готово 🖤\n\n<b>{r['service']}</b> · {r['detail']}\n📅 {dtfmt(r['start_at'])}\n\nЗа день до сеанса попрошу подтвердить запись.", reply_markup=main_kb())
    oid = await owner_id()
    if oid:
        if r['reference_file_id']:
            await bot.send_photo(oid, r['reference_file_id'], caption=owner_text(r), reply_markup=owner_actions(bid, r['username']))
        else:
            await bot.send_message(oid, owner_text(r), reply_markup=owner_actions(bid, r['username']))
    await state.clear()


async def my_booking(m: Message):
    r = await db.user_active(m.from_user.id)
    if not r:
        await m.answer('Активных записей пока нет.', reply_markup=main_kb()); return
    await m.answer(f"🖤 <b>Твоя запись</b>\n{r['service']} · {r['detail']}\n📅 {dtfmt(r['start_at'])}", reply_markup=booking_actions(r['id']))


async def cancel_cb(c: CallbackQuery, bot: Bot):
    bid = int(c.data.split(':')[1]); r = await db.get_booking(bid)
    is_owner = c.from_user.username and c.from_user.username.lower() == config.owner_username
    if not r or (c.from_user.id != r['user_id'] and not is_owner):
        await c.answer('Недоступно', show_alert=True); return
    await db.cancel(bid); await c.message.edit_text('❌ Запись отменена. Слот снова свободен.')
    oid = await owner_id()
    if oid and c.from_user.id != oid:
        await bot.send_message(oid, f"❌ Клиент отменил запись #{bid}\n{r['name']} · {dtfmt(r['start_at'])}")
    elif c.from_user.id == oid:
        await bot.send_message(r['user_id'], f"❌ Запись на {dtfmt(r['start_at'])} отменена мастером.")
    await c.answer()


async def move_begin(c: CallbackQuery, state: FSMContext):
    bid = int(c.data.split(':')[1]); r = await db.get_booking(bid)
    if not r or r['user_id'] != c.from_user.id:
        await c.answer('Недоступно', show_alert=True); return
    await state.update_data(move_bid=bid, duration=r['duration']); await state.set_state(Booking.move_date)
    await c.message.answer('Выбери новую дату:', reply_markup=date_keyboard('mdate')); await c.answer()


async def move_date(c: CallbackQuery, state: FSMContext):
    d = date.fromisoformat(c.data.split(':')[1]); data = await state.get_data(); slots = await slots_for(d, data['duration'], data['move_bid'])
    if not slots:
        await c.answer('Свободных окон нет', show_alert=True); return
    await state.set_state(Booking.move_time); await c.message.answer('Новое время:', reply_markup=slots_kb(slots,'mslot')); await c.answer()


async def move_time(c: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data(); bid = data['move_bid']; old = await db.get_booking(bid)
    start_at = datetime.fromisoformat(c.data.split(':',1)[1]); end_at = start_at + timedelta(minutes=data['duration'])
    if await db.overlaps(start_at.replace(tzinfo=None), end_at.replace(tzinfo=None), bid):
        await c.answer('Слот занят', show_alert=True); return
    await db.move(bid, start_at.replace(tzinfo=None), end_at.replace(tzinfo=None))
    await c.message.answer(f'🔄 Перенесено на {start_at.strftime("%d.%m.%Y · %H:%M")}', reply_markup=main_kb())
    oid = await owner_id()
    if oid:
        await bot.send_message(oid, f"🔄 Перенос записи #{bid}\n{old['name']}\nБыло: {dtfmt(old['start_at'])}\nСтало: {start_at.strftime('%d.%m.%Y · %H:%M')}")
    await state.clear(); await c.answer()


async def confirm(c: CallbackQuery, bot: Bot):
    bid = int(c.data.split(':')[1]); r = await db.get_booking(bid)
    if not r or r['user_id'] != c.from_user.id:
        await c.answer('Недоступно', show_alert=True); return
    await db.mark_confirmed(bid); await c.message.edit_text(f"✅ Спасибо! Запись на {dtfmt(r['start_at'])} подтверждена.")
    oid = await owner_id()
    if oid:
        await bot.send_message(oid, f"✅ {r['name']} подтвердил(а) запись #{bid} на {dtfmt(r['start_at'])}")
    await c.answer()


async def portfolio(m: Message, bot: Bot):
    await m.answer('🖤 <b>Работы Инны</b>')
    tattoo = ROOT / 'assets/portfolio/tattoo'
    pmu = ROOT / 'assets/portfolio/pmu'
    for f in list(tattoo.glob('*'))[:6] if tattoo.exists() else []:
        await bot.send_photo(m.chat.id, FSInputFile(f))
    for f in list(pmu.glob('*'))[:3] if pmu.exists() else []:
        await bot.send_photo(m.chat.id, FSInputFile(f))
    if not tattoo.exists() and not pmu.exists():
        await m.answer('Портфолио скоро появится здесь. Уже можно записаться или описать идею сообщением.')


async def owner_list(m: Message, offset=0):
    if not await maybe_bind_owner(m):
        await m.answer('Команда доступна владельцу.'); return
    now = datetime.now(); start_at = datetime.combine((now + timedelta(days=offset)).date(), time.min)
    rows = await db.list_range(start_at, start_at + timedelta(days=1))
    await m.answer('\n\n'.join(owner_text(r) for r in rows) if rows else 'Записей нет.')


async def all_bookings(m: Message):
    if not await maybe_bind_owner(m): return
    start_at = datetime.now(); rows = await db.list_range(start_at, start_at + timedelta(days=30))
    await m.answer('\n\n'.join(owner_text(r) for r in rows[:30]) if rows else 'На ближайшие 30 дней записей нет.')


async def reminder_job(bot: Bot):
    now = datetime.now(); tomorrow = (now + timedelta(days=1)).date(); s = datetime.combine(tomorrow, time.min)
    rows = await db.reminders_due(s, s + timedelta(days=1))
    for r in rows:
        try:
            await bot.send_message(r['user_id'], f"✨ <b>Завтра встречаемся</b>\n\n{r['service']} · {r['detail']}\n📅 {dtfmt(r['start_at'])}\n\nПодтверди, пожалуйста, что всё в силе.", reply_markup=booking_actions(r['id']))
            await db.mark_reminder(r['id'])
        except Exception:
            pass


async def ai_chat(m: Message, state: FSMContext):
    if not m.text or m.text.startswith('/'):
        return
    result = await ask_agent(m.text)
    if result is None:
        await m.answer('Расскажи, что хочешь сделать, или нажми «✨ Записаться» 🖤', reply_markup=main_kb()); return
    if result.intent == 'portfolio':
        await m.answer(result.reply); await portfolio(m, m.bot); return
    if result.intent == 'my_booking':
        await m.answer(result.reply); await my_booking(m); return
    if result.intent == 'handoff':
        oid = await owner_id()
        if oid:
            who = f'@{m.from_user.username}' if m.from_user.username else f'id {m.from_user.id}'
            await m.bot.send_message(oid, f'💬 Вопрос для Инны от {who}:\n\n{m.text}')
        await m.answer(result.reply); return
    if result.intent == 'book':
        await state.clear()
        if result.service == 'tattoo':
            await state.update_data(service='Татуировка')
            if result.tattoo_duration:
                labels={60:'До 5 см',120:'5–15 см',180:'Больше 15 см'}
                await state.update_data(duration=result.tattoo_duration, detail=labels[result.tattoo_duration]); await state.set_state(Booking.reference)
                await m.answer(result.reply + '\n\nПришли референс/фото идеи. Если нет — напиши <b>нет</b>.')
            else:
                await state.set_state(Booking.detail); await m.answer(result.reply + '\n\nЧтобы заложить время, выбери примерный размер:', reply_markup=tattoo_size_kb())
            return
        if result.service == 'pmu':
            await state.update_data(service='Перманентный макияж', duration=90)
            if result.pmu_detail:
                await state.update_data(detail=result.pmu_detail); await state.set_state(Booking.reference)
                await m.answer(result.reply + '\n\nЕсли есть референс — пришли фото. Если нет — напиши <b>нет</b>.')
            else:
                await state.set_state(Booking.detail); await m.answer(result.reply + '\n\nВыбери процедуру:', reply_markup=pmu_kb())
            return
        await state.set_state(Booking.service); await m.answer(result.reply + '\n\nЧто планируем?', reply_markup=service_kb()); return
    await m.answer(result.reply)


async def main():
    if not config.token:
        raise RuntimeError('BOT_TOKEN missing')
    await db.init_db()
    bot = Bot(config.token, parse_mode='HTML')
    dp = Dispatcher()
    dp.message.register(start, CommandStart())
    dp.message.register(begin, F.text == '✨ Записаться')
    dp.message.register(portfolio, F.text == '🖤 Работы Инны')
    dp.message.register(my_booking, F.text == '📅 Моя запись')
    dp.message.register(lambda m: owner_list(m,0), Command('today'))
    dp.message.register(lambda m: owner_list(m,1), Command('tomorrow'))
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
    dp.message.register(ai_chat, F.text)
    scheduler = AsyncIOScheduler(timezone=config.tz)
    scheduler.add_job(reminder_job, 'cron', hour=18, minute=0, args=[bot])
    scheduler.start()
    print('INNA booking bot started')
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
