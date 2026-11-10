import os
import json
from google import genai
from google.genai import types


class AIService:
    """Gemini-powered text generation for Playerok Manager PRO."""

    def __init__(self):
        key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        self.client = genai.Client(api_key=key) if key else None
        self.async_client = self.client.aio if self.client else None
        self.enabled = self.async_client is not None

    async def _ask(self, system, user):
        if not self.async_client:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        result = await self.async_client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.65,
                response_mime_type="application/json",
            ),
        )
        text = (result.text or "").strip()
        if not text:
            raise RuntimeError("Gemini вернул пустой ответ")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini вернул некорректный JSON: {text[:300]}") from exc

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

    async def close(self):
        if self.async_client:
            await self.async_client.aclose()
        if self.client:
            self.client.close()
