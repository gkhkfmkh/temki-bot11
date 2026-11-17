from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from config import settings

def _font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf"
    ]
    for p in candidates:
        try: return ImageFont.truetype(p, size)
        except OSError: pass
    return ImageFont.load_default()

def make_product_card(product_id: int, title: str, price: float, source_photo: str = "") -> str:
    out_dir = Path(settings.media_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1200, 900), (22, 27, 42))
    draw = ImageDraw.Draw(canvas)
    if source_photo and Path(source_photo).exists():
        try:
            photo = Image.open(source_photo).convert("RGB")
            photo = ImageOps.fit(photo, (1120, 590))
            canvas.paste(photo, (40, 40))
        except Exception:
            pass
    else:
        # Простая оригинальная геометрическая обложка, не имитация скриншота товара.
        draw.rounded_rectangle((40, 40, 1160, 630), radius=36, fill=(42, 56, 88))
        draw.ellipse((780, 70, 1160, 450), fill=(55, 92, 150))
        draw.ellipse((850, 150, 1080, 380), fill=(86, 132, 190))
        draw.text((85, 250), "DIGITAL ITEM", font=_font(58), fill=(230, 238, 255))
    title = title[:48]
    draw.text((55, 690), title, font=_font(46), fill=(255, 255, 255))
    draw.text((55, 785), f"{price:,.0f} {settings.currency}".replace(",", " "), font=_font(54), fill=(132, 220, 175))
    draw.text((875, 820), "DIGITAL GOODS", font=_font(20), fill=(170, 183, 207))
    out = out_dir / f"product_{product_id}_card.jpg"
    canvas.save(out, quality=92, optimize=True)
    return str(out)
