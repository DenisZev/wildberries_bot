# bot/handlers.py
import logging
import re
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, filters
from database.db import init_db, add_user, get_user, get_all_users, remove_user, add_product, get_product, load_products
from services.wildberries_api import get_orders, fetch_product_info, get_sales_report, get_orders_in_transit, get_stock_data, get_product_cards
from utils.messages import orders_message, sales_report_message, generate_sales_excel
from config.config import BOT_KEY
from services.barcode_gen import generate_barcode

logging.basicConfig(
    level=logging.INFO,
    filename='logs/bot.log',
    encoding='utf-8',  # Явно указываем UTF-8
    format='%(asctime)s - %(levelname)s - %(message)s'
)
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [['Проверить заказы'], ['Помощь']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Добро пожаловать! Используйте команду /register для регистрации.", reply_markup=reply_markup)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используйте: /register <wb_token> <chat_id>")
        return
    wb_token, chat_id = args[0], args[1]
    add_user(user_id, username, wb_token, chat_id)
    await update.message.reply_text("Вы успешно зарегистрированы!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "/start - Начать\n"
        "/register <wb_token> <chat_id> - Зарегистрироваться\n"
        "/check_orders - Проверить заказы\n"
        "/help - Помощь"
    )
    await update.message.reply_text(help_text)

async def check_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, зарегистрируйтесь с помощью /register.")
        return
    try:
        orders = await get_orders(user['wb_token'])
        await update.message.reply_text(orders_message(orders))
    except Exception as e:
        logging.error(f"Error while checking orders: {e}")
        await update.message.reply_text("Ошибка при получении заказов.")


async def sales_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, зарегистрируйтесь с помощью /register.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Используйте: /sales_report YYYY-MM-DD YYYY-MM-DD")
        return

    date_from, date_to = args[0], args[1]
    try:
        sales_data = await get_sales_report(date_from, date_to, user['wb_token'])
        stock_data = await get_stock_data(date_from, user['wb_token'])
        transit_data = await get_orders_in_transit(user['wb_token'])

        result = generate_sales_excel(sales_data, stock_data, transit_data, date_from, date_to,
                                      user_id)  # Передаём user_id
        if result is None:
            await update.message.reply_text("Не удалось сгенерировать отчёт из-за отсутствия данных.")
            return

        excel_file, metrics = result
        text, _ = sales_report_message(metrics, user_id)

        await update.message.reply_text(text)
        if excel_file:
            with open(excel_file, 'rb') as f:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=excel_file)
    except Exception as e:
        logging.error(f"Error fetching sales report: {e}")
        await update.message.reply_text("Ошибка при получении отчета по продажам.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, зарегистрируйтесь с помощью /register.")
        return
    text = update.message.text
    if text == 'Проверить заказы':
        await check_orders(update, context)
    elif text == 'Помощь':
        await help_command(update, context)
    else:
        article = re.search(r'артикул:\s*(\w+)', text, re.IGNORECASE)
        if article:
            product_info = await fetch_product_info(article.group(1), user['wb_token'])
            if product_info and product_info['cards']:
                product = product_info['cards'][0]
                title = product.get('title', 'Не указано')
                vendor_code = product.get('vendorCode', 'Не указано')
                brand = product.get('brand', 'Не указано')
                sku = product.get('sizes', [])[0].get('skus', [''])[0]
                size = product.get('sizes', [])[0].get('wbSize', 'Не указано')
                pdf_data = await generate_barcode(sku, title, vendor_code, brand, size)
                response = f"Товар:\nНазвание: {title}\nБренд: {brand}\nАртикул: {vendor_code}\n"
                await update.message.reply_text(response)
                if pdf_data:
                    pdf_data.seek(0)
                    await context.bot.send_document(chat_id=update.effective_chat.id, document=pdf_data, filename='barcode.pdf')
            else:
                await update.message.reply_text("Товар не найден.")
        else:
            await update.message.reply_text('Укажите артикул в формате "артикул: ___".')

async def add_product_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, зарегистрируйтесь с помощью /register.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используйте: /add_product <article> <cost> (например, /add_product пн2.2 300.50)")
        return

    article = args[0].lower()
    cost = args[1]
    try:
        purchase_cost = float(cost)
        current_product = get_product(user_id, article)
        name = current_product.get('name', article) if current_product else article
        nmID = current_product.get('nmID') if current_product else None
        category = current_product.get('category') if current_product else None
        add_product(user_id, article, name, purchase_cost, nmID, category)
        await update.message.reply_text(f"Товар '{article}' обновлён с закупочной стоимостью {purchase_cost} руб.")
    except ValueError:
        await update.message.reply_text("Стоимость должна быть числом (например, 300.50).")


async def load_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, зарегистрируйтесь с помощью /register.")
        return

    try:
        products = await get_product_cards(user['wb_token'])
        if not products:
            await update.message.reply_text("Не удалось загрузить товары. Проверьте токен или логи.")
            return

        load_products(user_id, products)
        await update.message.reply_text(
            f"Загружено {len(products)} товаров в базу для вашего аккаунта. Укажите закупочную стоимость через /add_product.")
    except Exception as e:
        logging.error(f"Error loading products: {e}", exc_info=True)
        await update.message.reply_text(f"Ошибка при загрузке товаров: {str(e)}")

async def import_costs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, зарегистрируйтесь с помощью /register.")
        return

    if not update.message.document:
        await update.message.reply_text("Прикрепите CSV-файл с колонками 'article,cost'.")
        return

    file = await update.message.document.get_file()
    file_data = await file.download_as_bytearray()
    import csv
    from io import StringIO

    try:
        csv_content = file_data.decode('utf-8')
        reader = csv.DictReader(StringIO(csv_content))
        updated = 0
        for row in reader:
            article = row['article'].lower()
            cost = float(row['cost'])
            current_product = get_product(article)
            name = current_product.get('name', article) if current_product else article
            nmID = current_product.get('nmID') if current_product else None
            category = current_product.get('category') if current_product else None
            add_product(article, name, cost, nmID, category)
            updated += 1
        await update.message.reply_text(f"Обновлено {updated} товаров из файла.")
    except Exception as e:
        logging.error(f"Error importing costs: {e}", exc_info=True)
        await update.message.reply_text(f"Ошибка при загрузке: {str(e)}")