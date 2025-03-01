# services/barcode_gen.py
import io
import logging
from barcode import Code128  # Импортируем конкретный класс
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    filename='logs/bot.log',
    encoding='utf-8',  # Явно указываем UTF-8
    format='%(asctime)s - %(levelname)s - %(message)s'
)
pdfmetrics.registerFont(TTFont("Arial", "arialmt.ttf"))

async def generate_barcode(sku, product_name, article, brand=None, size=None):
    width_inch, height_inch = 2.40, 1.57
    try:
        barcode_buffer = io.BytesIO()
        # Используем Code128 вместо barcode.get
        code128 = Code128(str(sku), writer=ImageWriter())
        code128.write(barcode_buffer)
        barcode_buffer.seek(0)
        barcode_image = Image.open(barcode_buffer)

        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=(width_inch * inch, height_inch * inch))
        c.setFont("Arial", 10)

        def draw_multiline_text(c, text, x, y, max_width, line_height):
            words = text.split(" ")
            current_line, current_y, lines_drawn = "", y, 0
            for word in words:
                if c.stringWidth(current_line + word, "Arial", 10) < max_width:
                    current_line += word + " "
                else:
                    c.drawString(x, current_y, current_line.strip())
                    current_line = word + " "
                    current_y -= line_height
                    lines_drawn += 1
                    if current_y < 0:
                        break
            if current_line and current_y >= 0:
                c.drawString(x, current_y, current_line.strip())
                lines_drawn += 1
            return lines_drawn

        texts = [product_name, f"Артикул: {article}"]
        if brand:
            texts.append(f"Бренд: {brand}")
        if size:
            texts.append(f"Размер: {size}")

        current_height = height_inch - 0.2
        max_width = width_inch * inch - 20
        for text in texts:
            lines_drawn = draw_multiline_text(c, text, 10, current_height * inch, max_width, 0.12 * inch)
            current_height -= lines_drawn * 0.12

        barcode_width, barcode_height = 90, 65
        c.drawInlineImage(barcode_image, (width_inch * inch - barcode_width) / 2, (current_height - 0.8) * inch,
                          width=barcode_width, height=barcode_height)
        c.save()
        pdf_buffer.seek(0)
        return pdf_buffer
    except Exception as e:
        logging.error(f"Ошибка при генерации PDF: {e}")
        return None