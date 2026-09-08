from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='✨ Записаться'),KeyboardButton(text='🖤 Работы Инны')],[KeyboardButton(text='📅 Моя запись')]],resize_keyboard=True)

def service_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🖋 Татуировка',callback_data='svc:tattoo')],[InlineKeyboardButton(text='✨ Перманентный макияж',callback_data='svc:pmu')]])

def tattoo_size_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='До 5 см · ~1 ч',callback_data='size:60')],[InlineKeyboardButton(text='5–15 см · ~2 ч',callback_data='size:120')],[InlineKeyboardButton(text='Больше 15 см · ~3 ч',callback_data='size:180')]])

def pmu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Брови',callback_data='pmu:Брови'),InlineKeyboardButton(text='Губы',callback_data='pmu:Губы')],[InlineKeyboardButton(text='Межресничка',callback_data='pmu:Межресничка')]])

def booking_actions(bid):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить',callback_data=f'confirm:{bid}')],[InlineKeyboardButton(text='🔄 Перенести',callback_data=f'move:{bid}'),InlineKeyboardButton(text='❌ Отменить',callback_data=f'cancel:{bid}')]])

def owner_actions(bid,username=None):
    rows=[[InlineKeyboardButton(text='❌ Отменить запись',callback_data=f'owncancel:{bid}')]]
    if username: rows.append([InlineKeyboardButton(text='💬 Написать клиенту',url=f'https://t.me/{username}')])
    return InlineKeyboardMarkup(inline_keyboard=rows)
