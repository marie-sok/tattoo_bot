from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='✨ Записаться'), KeyboardButton(text='🖤 Работы Инны')],
            [KeyboardButton(text='💰 Цены'), KeyboardButton(text='📅 Моя запись')],
        ],
        resize_keyboard=True,
    )


def service_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🖋 Татуировка', callback_data='svc:tattoo')],
        [InlineKeyboardButton(text='✨ Перманентный макияж', callback_data='svc:pmu')],
    ])


def tattoo_size_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='3–4 часа · 12 000 ₽', callback_data='size:240')],
        [InlineKeyboardButton(text='6–7 часов · 16 000 ₽', callback_data='size:420')],
    ])


def pmu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Губы · 5 000 ₽', callback_data='pmu:lips')],
        [InlineKeyboardButton(text='Брови · 5 000 ₽', callback_data='pmu:brows')],
        [InlineKeyboardButton(text='Коррекция · 3 000 ₽', callback_data='pmu:correction')],
        [InlineKeyboardButton(text='Рефреш бровей · 4 000 ₽', callback_data='pmu:refresh_brows')],
        [InlineKeyboardButton(text='Рефреш губ · 4 000 ₽', callback_data='pmu:refresh_lips')],
    ])


def booking_actions(bid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Подтвердить', callback_data=f'confirm:{bid}')],
        [
            InlineKeyboardButton(text='🔄 Перенести', callback_data=f'move:{bid}'),
            InlineKeyboardButton(text='❌ Отменить', callback_data=f'cancel:{bid}'),
        ],
    ])


def owner_actions(bid, username=None):
    rows = [[InlineKeyboardButton(text='❌ Отменить запись', callback_data=f'owncancel:{bid}')]]
    if username:
        rows.append([InlineKeyboardButton(text='💬 Написать клиенту', url=f'https://t.me/{username}')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def portfolio_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🖋 Татуировки', callback_data='portfolio:tattoo')],
        [InlineKeyboardButton(text='✨ Перманентный макияж', callback_data='portfolio:pmu')],
        [InlineKeyboardButton(text='✨ Записаться', callback_data='portfolio:book')],
    ])


def portfolio_work_kb(kind: str, index: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🖤 Хочу похожую', callback_data=f'work:{kind}:{index}')],
        [InlineKeyboardButton(text='← К работам', callback_data='portfolio:menu')],
    ])
