import os
import json
from openai import AsyncOpenAI

class AIService:
    def __init__(self):
        key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.client = AsyncOpenAI(api_key=key) if key else None
        self.enabled = self.client is not None

    async def _ask(self, system, user):
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        result = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.65,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        )
        return json.loads(result.choices[0].message.content)

    async def generate_listing(self, data):
        system = """
Ты профессиональный редактор карточек цифровых товаров для маркетплейса.
Пиши на русском, понятно, честно, без спама, манипуляций и необоснованных обещаний.
НИКОГДА не выдумывай характеристики, наличие, сроки, гарантии, комплектацию или способ передачи.
Если данных не хватает, прямо укажи это в notes и используй нейтральную формулировку.
Не добавляй контакты вне площадки. Не обещай положительный отзыв за бонус.
Верни только JSON: title, description, features (array), buyer_gets, faq (array объектов q/a), tags (array), notes.
"""
        user = f"""
Игра: {data['game']}
Категория: {data['category']}
Исходное название: {data['name']}
Цена: {data['price']} RUB
Подтверждённые факты от продавца: {data['facts']}
Создай готовую карточку. Не придумывай отсутствующие данные.
"""
        return await self._ask(system, user)

    async def revise_listing(self, product, instruction):
        system = """
Ты редактируешь карточку цифрового товара. Сохраняй фактическую точность.
Не добавляй неподтверждённые свойства и не скрывай важные условия.
Верни JSON с полями title, description, features, buyer_gets, faq, tags, notes.
"""
        user = f"""
Текущая карточка:
{json.dumps(product['listing'], ensure_ascii=False)}
Факты:
{product['facts']}
Игра: {product['game']}; категория: {product['category']}; цена: {product['price']}
Запрос продавца: {instruction}
"""
        return await self._ask(system, user)
