import csv, io
from config import settings

def calc_profit(cost, price, fee=0):
    profit = float(price) - float(cost) - float(fee)
    roi = profit / float(cost) * 100 if float(cost) > 0 else 0.0
    return round(profit, 2), round(roi, 2)

def parse_csv(data: bytes):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    required = {"title", "price", "category"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("CSV должен содержать столбцы title, price, category")
    result = []
    for n, row in enumerate(reader, 2):
        title, category = (row.get("title") or "").strip(), (row.get("category") or "").strip()
        if not title or not category:
            continue
        try:
            price = float((row.get("price") or "").replace(",", ".").replace(" ", ""))
        except ValueError:
            raise ValueError(f"Неверная цена в строке {n}")
        if price < 0:
            raise ValueError(f"Отрицательная цена в строке {n}")
        result.append((title[:200], category[:100], price, (row.get("url") or "")[:500],
                       (row.get("source") or "CSV")[:100], (row.get("notes") or "")[:500]))
    return result
