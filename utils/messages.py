# utils/messages.py
from datetime import datetime
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
from database.db import get_product
import os
import logging

def format_date(date_str):
    try:
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime('%d.%m.%Y %H:%M:%S')
    except ValueError:
        return date_str

def orders_message(orders):
    if not orders:
        return "Нет новых заказов."
    order_list = []
    for order in orders:
        order_id = order.get('id', 'неизвестно')
        skus = order.get('skus', [])
        article = order.get('article', 'неизвестно')
        price = order.get('price', 0)
        converted_price = order.get('convertedPrice')
        sale_price = converted_price if (converted_price is not None and isinstance(converted_price, (int, float))) else price
        if sale_price is None or not isinstance(sale_price, (int, float)):
            sale_price = 0
        formatted_price = f"{sale_price // 100},{sale_price % 100:02d}" if sale_price else "Не указано"
        order_list.append(
            f"Заказ ID: {order_id}\n"
            f"SKUs: {', '.join(skus)}\n"
            f"Артикул: {article}\n"
            f"Цена: {formatted_price} руб.\n"
            f"{'-' * 30}"
        )
    return f"Вот ваши новые заказы:\n" + "\n".join(order_list)

def sales_report_message(metrics, user_id):
    """Формирует текстовый отчет по продажам с уведомлением о товарах без стоимости."""
    if not metrics['sales_data']:
        return "Нет данных по продажам за указанный период.", None

    missing_costs = set()
    for sale in [s for s in metrics['sales_data'] if s.get('supplier_oper_name') == 'Продажа']:
        product = get_product(user_id, sale.get('sa_name', ''))
        if product and product['purchase_cost'] == 0.0:
            missing_costs.add(sale.get('sa_name', ''))

    warning = ""
    if missing_costs:
        warning = f"\n⚠️ Товары без закупочной стоимости: {', '.join(missing_costs)}. Укажите через /add_product.\n"

    text = (
        f"Отчёт по продажам:\n"
        f"Всего продаж: {metrics['total_sales']}\n"
        f"Общая выручка: {metrics['formatted_revenue']} руб.\n"
        f"Средняя выручка на продажу: {metrics['formatted_avg_sale']} руб.\n"
        f"Продано единиц: {metrics['items_sold']}\n"
        f"Возвраты: {metrics['total_returns']} шт.\n"
        f"Затраты на товары: {metrics['formatted_cost']} руб.\n"
        f"Комиссия WB: {metrics['formatted_commission']} руб.\n"
        f"Затраты на доставку: {metrics['formatted_delivery']} руб.\n"
        f"Чистая прибыль: {metrics['formatted_profit']} руб.\n"
        f"{metrics['top_products']}"
        f"{warning}"
    )
    return text, None


def generate_sales_chart(sales_data, stock_data, date_from, date_to):
    if not sales_data:
        return None

    sales = [s for s in sales_data if s.get('supplier_oper_name') == 'Продажа']
    if not sales:
        return None

    df_sales = pd.DataFrame([{
        'Дата': pd.to_datetime(s.get('sale_dt', '')),
        'Выручка': s.get('ppvz_for_pay', 0),
        'Затраты': get_product(s.get('sa_name', ''))['purchase_cost'] * s.get('quantity', 0),
        'Комиссия': s.get('ppvz_sales_commission', 0),
        'Доставка': s.get('delivery_rub', 0, 0)
    } for s in sales])
    daily_data = df_sales.groupby(df_sales['Дата'].dt.date).agg({
        'Выручка': 'sum',
        'Затраты': 'sum',
        'Комиссия': 'sum',
        'Доставка': 'sum'
    })
    daily_data['Прибыль'] = daily_data['Выручка'] - daily_data['Затраты'] - daily_data['Комиссия'] - daily_data['Доставка']

    plt.figure(figsize=(10, 5))
    plt.plot(daily_data.index, daily_data['Прибыль'], marker='o', label='Прибыль (руб.)', color='green')
    plt.xlabel("Дата")
    plt.ylabel("Прибыль (руб.)", color='green')
    plt.title(f"Динамика прибыли ({date_from} - {date_to})")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.legend(loc='upper left')
    chart_file = f"sales_chart_{date_from}_{date_to}.png"
    plt.savefig(chart_file, bbox_inches='tight')
    plt.close()
    return chart_file


def generate_sales_excel(sales_data, stock_data, transit_data, date_from, date_to, user_id):
    """Генерирует Excel-файл с продажами, остатками и товарами в пути."""
    logging.info("Starting generate_sales_excel")
    if not any([sales_data, stock_data, transit_data]):
        logging.warning("No data provided to generate_sales_excel")
        return None, {}

    try:
        # 1. Детализация продаж
        logging.info("Processing sales data")
        sales = [sale for sale in sales_data if sale.get('supplier_oper_name') == 'Продажа'] if sales_data else []
        detail_data = [{
            'Дата продажи': sale.get('sale_dt', ''),
            'Артикул продавца': sale.get('sa_name', 'Неизвестно'),
            'Название товара': sale.get('subject_name', 'Неизвестно'),
            'Количество': sale.get('quantity', 0),
            'Сумма к выплате (руб.)': sale.get('ppvz_for_pay', 0),
            'Розничная цена (руб.)': sale.get('retail_price_withdisc_rub', 0),
            'Комиссия WB (руб.)': sale.get('ppvz_sales_commission', 0),
            'Закупочная стоимость (руб.)': get_product(user_id, sale.get('sa_name', ''))['purchase_cost'],
            'Склад': sale.get('office_name', '')
        } for sale in sales]

        # 2. Итоги продаж
        logging.info("Calculating summary metrics")
        total_sales = len(sales)
        total_revenue = sum(int(sale.get('ppvz_for_pay', 0) * 100) for sale in sales)
        items_sold = sum(sale.get('quantity', 0) for sale in sales)
        total_returns = sum(sale.get('return_amount', 0) for sale in sales_data) if sales_data else 0
        total_commission = sum(int(sale.get('ppvz_sales_commission', 0) * 100) for sale in sales)
        total_delivery = sum(int(sale.get('delivery_rub', 0) * 100) for sale in sales_data) if sales_data else 0
        total_cost = sum(int((get_product(user_id, sale.get('sa_name', '')) or {'purchase_cost': 0})['purchase_cost'] * sale.get('quantity', 0) * 100) for sale in sales)
        total_profit = total_revenue - total_cost - total_commission - total_delivery

        avg_sale = total_revenue / total_sales if total_sales > 0 else 0
        product_counts = Counter(sale.get('sa_name', 'Неизвестно') for sale in sales)
        top_products = "\nТоп-3 продаваемых товара:\n" + "\n".join(f"- {p}: {c} шт." for p, c in product_counts.most_common(3))

        formatted_revenue = f"{total_revenue // 100},{total_revenue % 100:02d}"
        formatted_cost = f"{total_cost // 100},{total_cost % 100:02d}"
        formatted_commission = f"{total_commission // 100},{total_commission % 100:02d}"
        formatted_delivery = f"{total_delivery // 100},{total_delivery % 100:02d}"
        formatted_profit = f"{total_profit // 100},{total_profit % 100:02d}"
        formatted_avg_sale = f"{int(avg_sale) // 100},{int(avg_sale) % 100:02d}"

        summary_data = {
            'Метрика': ['Всего продаж', 'Общая выручка (руб.)', 'Средняя выручка на продажу (руб.)', 'Продано единиц',
                        'Возвраты (шт.)', 'Затраты на товары (руб.)', 'Комиссия WB (руб.)', 'Затраты на доставку (руб.)',
                        'Чистая прибыль (руб.)', 'Топ-3 товара'],
            'Значение': [total_sales, formatted_revenue, formatted_avg_sale, items_sold, total_returns,
                         formatted_cost, formatted_commission, formatted_delivery, formatted_profit, top_products]
        }

        # 3. Остатки на складах
        logging.info("Processing stock data")
        stock_data_formatted = [{
            'Артикул': stock.get('supplierArticle', 'Неизвестно'),
            'Название': stock.get('subject', 'Неизвестно'),
            'Количество': stock.get('quantity', 0),
            'Склад': stock.get('warehouseName', '')
        } for stock in stock_data] if stock_data else []

        # 4. Товары в пути
        logging.info("Processing transit data")
        transit_data_formatted = [{
            'ID заказа': transit.get('id', ''),
            'Артикул': transit.get('article', 'Неизвестно'),
            'Создано': transit.get('createdAt', ''),
            'Склад': transit.get('offices', [''])[0]
        } for transit in transit_data] if transit_data else []

        # Создание Excel
        logging.info("Generating Excel file")
        filename = f"sales_report_{date_from}_{date_to}.xlsx"
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            if detail_data:
                pd.DataFrame(detail_data).to_excel(writer, sheet_name='Детализация', index=False)
            if total_sales > 0:
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Итоги', index=False)
            if stock_data_formatted:
                pd.DataFrame(stock_data_formatted).to_excel(writer, sheet_name='Остатки', index=False)
            if transit_data_formatted:
                pd.DataFrame(transit_data_formatted).to_excel(writer, sheet_name='В пути', index=False)

        metrics = {
            'sales_data': sales_data,
            'total_sales': total_sales,
            'total_revenue': total_revenue,
            'items_sold': items_sold,
            'total_returns': total_returns,
            'total_commission': total_commission,
            'total_delivery': total_delivery,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'formatted_revenue': formatted_revenue,
            'formatted_cost': formatted_cost,
            'formatted_commission': formatted_commission,
            'formatted_delivery': formatted_delivery,
            'formatted_profit': formatted_profit,
            'formatted_avg_sale': formatted_avg_sale,
            'top_products': top_products
        }
        logging.info(f"Excel file generated: {filename}")
        return filename, metrics

    except Exception as e:
        logging.error(f"Error in generate_sales_excel: {e}", exc_info=True)
        return None, {}