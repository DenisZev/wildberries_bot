# services/wildberries_api.py
import logging
import aiohttp
from aiohttp import ClientTimeout
from config.config import API_KEY, BASE_URL, CONTENT_URL
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.DEBUG,
    filename='logs/bot.log',
    encoding='utf-8',  # Явно указываем UTF-8
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def fetch_data(url, headers, params=None, timeout=10):
    logging.info(f"Sending GET request to {url} with params: {params}")
    timeout = ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"API response data: {data}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Request failed: {str(e)} to {url}")
            return None

async def fetch_product_info(article, wb_token):
    async with aiohttp.ClientSession(timeout=ClientTimeout(total=10)) as session:
        url = CONTENT_URL + "/list"
        headers = {"Authorization": f"Bearer {wb_token}", "Content-Type": "application/json"}
        body = {"settings": {"cursor": {"limit": 100}, "filter": {"textSearch": article, "withPhoto": -1}}}
        logging.info(f"Fetching product info for article: {article}")
        try:
            async with session.post(url, headers=headers, json=body) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Successfully fetched product info for article: {article}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Request failed: {str(e)} for article {article}")
            return None

async def get_orders(wb_token):
    url = BASE_URL + "/orders/new"
    headers = {"Authorization": f"Bearer {wb_token}"}
    data = await fetch_data(url, headers)
    if not data:
        logging.error("Нет данных от API.")
        return []
    orders = data.get('orders', [])
    logging.info(f"Получено {len(orders)} новых заказов.")
    return orders


async def get_sales_report(date_from: str, date_to: str, wb_token: str) -> dict:
    url = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
    headers = {"Authorization": f"Bearer {wb_token}"}
    params = {
        "dateFrom": date_from,
        "dateTo": date_to,
        "limit": 100000
    }

    logging.info(f"Fetching sales report from {date_from} to {date_to}")
    timeout = ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Received {len(data)} sales records")
                logging.debug(f"Sample data: {data[:2]}")  # Логируем первые 2 записи для отладки
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Failed to fetch sales report: {e}")
            return {}

async def get_stock_data(date_from: str, wb_token: str) -> list:
    """Получение данных по остаткам на складах."""
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
    headers = {"Authorization": f"Bearer {wb_token}"}
    params = {"dateFrom": date_from}

    logging.info(f"Fetching stock data from {date_from}")
    timeout = ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Received {len(data)} stock records")
                logging.debug(f"Sample stock data: {data[:2]}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Failed to fetch stock data: {e}")
            return []

async def get_orders_in_transit(wb_token: str) -> list:
    """Получение заказов в пути (сборочные задания)."""
    url = "https://marketplace-api.wildberries.ru/api/v3/orders"
    headers = {"Authorization": f"Bearer {wb_token}"}
    params = {
        "limit": 1000,  # Максимально допустимое значение
        "next": 0       # Обязательный параметр для первого запроса
    }

    logging.info(f"Fetching orders in transit with params: {params}")
    timeout = ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                orders = data.get('orders', [])
                logging.info(f"Received {len(orders)} orders in transit")
                logging.debug(f"Sample transit data: {orders[:2]}")
                return orders
        except aiohttp.ClientError as e:
            logging.error(f"Failed to fetch orders in transit: {e}")
            if hasattr(e, 'response') and e.response:
                error_text = await e.response.text()
                logging.error(f"Full error response: {error_text}")
            return []


async def get_product_cards(wb_token: str) -> list:
    """Получение полного списка карточек товаров продавца с пагинацией."""
    url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
    headers = {
        "Authorization": f"Bearer {wb_token}",
        "Content-Type": "application/json"
    }
    all_cards = []
    cursor = {"limit": 100}  # Максимальный лимит 100, как указано в ошибке API

    logging.info(f"Fetching product cards with token: {wb_token[:10]}...")
    timeout = ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            payload = {
                "settings": {
                    "cursor": cursor,
                    "filter": {"withPhoto": -1}
                }
            }
            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    status = response.status
                    logging.info(f"API response status: {status}")
                    if status != 200:
                        error_text = await response.text()
                        logging.error(f"API error: {status} - {error_text}")
                        break
                    data = await response.json()
                    cards = data.get('cards', [])
                    logging.info(f"Received {len(cards)} product cards in this batch")
                    if cards:
                        logging.debug(f"Sample product cards: {cards[:2]}")
                        all_cards.extend(cards)
                    else:
                        logging.warning("No cards returned in response")
                        break

                    # Обновляем курсор для следующего запроса
                    if 'cursor' in data:
                        next_cursor = data['cursor']
                        cursor = {
                            "limit": 100,
                            "updatedAt": next_cursor.get('updatedAt'),
                            "nmID": next_cursor.get('nmID')
                        }
                    else:
                        break  # Нет курсора — конец данных

                    if len(cards) < cursor['limit']:
                        break  # Последняя страница

            except aiohttp.ClientError as e:
                logging.error(f"Failed to fetch product cards: {e}")
                if hasattr(e, 'response') and e.response:
                    error_text = await e.response.text()
                    logging.error(f"Full error response: {error_text}")
                break
            except Exception as e:
                logging.error(f"Unexpected error in get_product_cards: {e}", exc_info=True)
                break

    logging.info(f"Total product cards fetched: {len(all_cards)}")
    return all_cards