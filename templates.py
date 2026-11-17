"""Редактируйте тексты под свой товар. Не обещайте того, чего товар не гарантирует."""

def buyer_message(stage: str, buyer: str, order_id: str, product: str, details: str = "") -> str:
    name = buyer.strip() or "Здравствуйте"
    base = f"{name}, "
    if stage == "welcome":
        return (base + f"спасибо за заказ «{product}»! Заказ №{order_id} принят. "
                "Если возникнут вопросы, напишите сюда.")
    if stage == "clarify":
        return (base + f"по заказу №{order_id} нужно уточнить один момент: {details or '[укажите вопрос]'}. "
                "Пожалуйста, ответьте в чате заказа.")
    if stage == "delivery":
        return (base + f"ваш заказ №{order_id} — «{product}».\\n\\n"
                f"{details or '[вставьте инструкцию/данные выдачи вручную в защищённом чате площадки]'}\\n\\n"
                "Если что-то не получается, напишите — помогу разобраться.")
    if stage == "complete":
        return (base + f"заказ №{order_id} по товару «{product}» выполнен. "
                "Спасибо за покупку! Если всё в порядке, буду благодарен за отзыв.")
    if stage == "problem":
        return (base + f"вижу проблему по заказу №{order_id}. "
                f"{details or 'Опишите, пожалуйста, что именно не работает, и я помогу.'}")
    raise ValueError("Неизвестный тип шаблона")
