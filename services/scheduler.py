# services/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.notifications import send_notification
from services.wildberries_api import get_orders, get_sales_report, get_orders_in_transit, get_stock_data
from database.db import get_all_users
from utils.messages import sales_report_message, generate_sales_excel, generate_sales_chart
from telegram import Bot
from config.config import BOT_KEY, CHAT_ID
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    filename='logs/bot.log',
    encoding='utf-8',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

scheduler = AsyncIOScheduler()
sent_orders = set()  # Множество для хранения отправленных заказов

async def check_for_new_orders():
    users = get_all_users()
    for user in users:
        try:
            orders = await get_orders(user['wb_token'])  # Теперь get_orders доступна
            if orders:
                for order in orders:
                    order_id = order['id']
                    if order_id not in sent_orders:  # Проверяем, отправляли ли уже
                        await send_notification(order_id, order, user['wb_token'], user['chat_id'])
                        sent_orders.add(order_id)  # Добавляем в отправленные
                        logging.info(f"Processed new order ID: {order_id}")
                    else:
                        logging.info(f"Order ID {order_id} already processed, skipping.")
        except Exception as e:
            logging.error(f"Ошибка при проверке заказов для пользователя {user['user_id']}: {e}")


async def weekly_sales_report():
    bot = Bot(token=BOT_KEY)
    users = get_all_users()
    if not users:
        logging.warning("No users found for weekly report.")
        return

    date_to = datetime.now().strftime('%Y-%m-%d')
    date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    for user in users:
        try:
            sales_data = await get_sales_report(date_from, date_to, user['wb_token'])
            stock_data = await get_stock_data(date_from, user['wb_token'])
            transit_data = await get_orders_in_transit(user['wb_token'])

            result = generate_sales_excel(sales_data, stock_data, transit_data, date_from, date_to, user['user_id'])
            if result is None:
                await bot.send_message(chat_id=CHAT_ID,
                                       text=f"Еженедельный отчёт ({date_from} - {date_to}): Не удалось сгенерировать из-за отсутствия данных.")
                continue

            excel_file, metrics = result
            text, _ = sales_report_message(metrics, user['user_id'])
            chart_file = generate_sales_chart(sales_data, stock_data, date_from, date_to)

            await bot.send_message(chat_id=CHAT_ID,
                                   text=f"Еженедельный отчёт по продажам ({date_from} - {date_to}):\n{text}")
            if excel_file:
                with open(excel_file, 'rb') as f:
                    await bot.send_document(chat_id=CHAT_ID, document=f, filename=excel_file)
            if chart_file:
                with open(chart_file, 'rb') as f:
                    await bot.send_photo(chat_id=CHAT_ID, photo=f, filename=chart_file)
        except Exception as e:
            logging.error(f"Error in weekly sales report for user {user['user_id']}: {e}")

async def start_scheduler(context=None):
    logging.info("Starting scheduler...")
    scheduler.add_job(check_for_new_orders, 'interval', seconds=120)
    scheduler.add_job(weekly_sales_report, 'cron', day_of_week='mon', hour=9, minute=0)  # Понедельник, 09:00
    scheduler.start()