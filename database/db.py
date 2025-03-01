# database/db.py
import sqlite3

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
        (user_id INTEGER PRIMARY KEY, username TEXT, wb_token TEXT, chat_id TEXT)''')
    # Новая таблица products с user_id
    cursor.execute('''CREATE TABLE IF NOT EXISTS products
        (user_id INTEGER, article TEXT, name TEXT, purchase_cost REAL DEFAULT 0.0, nmID INTEGER, category TEXT,
         PRIMARY KEY (user_id, article))''')
    conn.commit()
    conn.close()

def add_user(user_id, username, wb_token, chat_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username, wb_token, chat_id) VALUES (?, ?, ?, ?)",
                   (user_id, username, wb_token, chat_id))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {'user_id': user[0], 'username': user[1], 'wb_token': user[2], 'chat_id': user[3]}
    return None

def get_all_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return [{'user_id': user[0], 'username': user[1], 'wb_token': user[2], 'chat_id': user[3]} for user in users]

def remove_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def add_product(user_id, article, name, purchase_cost=0.0, nmID=None, category=None):
    article = article.lower()
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO products (user_id, article, name, purchase_cost, nmID, category) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, article, name, purchase_cost, nmID, category))
    conn.commit()
    conn.close()


def get_product(user_id, article):
    article = article.lower()
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT article, name, purchase_cost, nmID, category FROM products WHERE user_id = ? AND article = ?",
        (user_id, article))
    product = cursor.fetchone()
    conn.close()
    return {'article': product[0], 'name': product[1], 'purchase_cost': product[2], 'nmID': product[3],
            'category': product[4]} if product else {'purchase_cost': 0.0}


def load_products(user_id, products):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT article, purchase_cost FROM products WHERE user_id = ?", (user_id,))
    existing_products = {row[0]: row[1] for row in cursor.fetchall()}

    for product in products:
        article = product.get('vendorCode', 'Unknown').lower()
        name = product.get('title', 'Unknown')
        nmID = product.get('nmID')
        category = product.get('subjectName')
        purchase_cost = existing_products.get(article, 0.0)
        cursor.execute(
            "INSERT OR REPLACE INTO products (user_id, article, name, purchase_cost, nmID, category) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, article, name, purchase_cost, nmID, category))

    conn.commit()
    conn.close()


def get_all_products(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT article, name, purchase_cost, nmID, category FROM products WHERE user_id = ?", (user_id,))
    products = cursor.fetchall()
    conn.close()
    return [{'article': p[0], 'name': p[1], 'purchase_cost': p[2], 'nmID': p[3], 'category': p[4]} for p in products]