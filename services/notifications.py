# services/notifications.py
import logging
from telegram import Bot
from config.config import BOT_KEY
from services.wildberries_api import fetch_product_info, get_orders
from services.barcode_gen import generate_barcode
from database.db import get_all_users

logging.basicConfig(level=logging.INFO, filename='logs/bot.log', format='%(asctime)s - %(levelname)s - %(message)s')

async def send_notification(order_id: str, task: dict, wb_token: str, chat_id: str) -> None:
    bot = Bot(token=BOT_KEY)
    product_info = await fetch_product_info(task.get('article'), wb_token)
    product_name, vendor_code, brand = "Не указано", "Не указано", "Не указано"
    selected_sku, selected_size, photo_link = "Не указано", "Не указано", "Фото отсутствует."

    if product_info and product_info.get('cards'):
        product = product_info['cards'][0]
        product_name = product.get('title', product_name)
        vendor_code = product.get('vendorCode', vendor_code)
        brand = product.get('brand', brand)
        sizes = product.get('sizes', [])
        chrt_id = task.get('chrtId')
        for size in sizes:
            if size.get('chrtID') == chrt_id:
                selected_sku = size.get('skus', [''])[0]
                selected_size = size.get('wbSize', selected_size)
                break
        photos = product.get('photos', [])
        photo_link = photos[0]['big'] if photos else photo_link

    price = task.get('salePrice', 0)
    formatted_price = f"{price // 100},{price % 100:02d}"

    pdf_data = await generate_barcode(selected_sku, product_name, vendor_code, brand, selected_size)

    message = (
        f"Новый заказ!\n"
        f"ID: {order_id}\n"
        f"Артикул: {vendor_code}\n"
        f"Название: {product_name}\n"
        f"{f'Размер: {selected_size}' if selected_size != 'Не указано' else ''}\n"
        f"Баркод: {selected_sku}\n"
        f"Цена: {formatted_price} руб.\n"
        f"Фото: {photo_link}\n"
    )

    try:
        await bot.send_message(chat_id=chat_id, text=message)
        if pdf_data:
            pdf_data.seek(0)
            await bot.send_document(chat_id=chat_id, document=pdf_data, filename='barcode.pdf', caption="Этикетка с баркодом")
        else:
            await bot.send_message(chat_id=chat_id, text="Не удалось сгенерировать этикетку.")
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления: {e}")
        await bot.send_message(chat_id=chat_id, text="Произошла ошибка при обработке заказа.")

async def check_new_orders():
    users = get_all_users()
    for user in users:
        try:
            orders = await get_orders(user['wb_token'])
            if orders:
                for order in orders:
                    await send_notification(order['id'], order, user['wb_token'], user['chat_id'])
        except Exception as e:
            logging.error(f"Ошибка при проверке заказов для пользователя {user['user_id']}: {e}")