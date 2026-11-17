from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def decision(kind, item_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Подтвердить", callback_data=f"yes:{kind}:{item_id}"),
        InlineKeyboardButton(text="Отклонить", callback_data=f"no:{kind}:{item_id}")
    ]])
