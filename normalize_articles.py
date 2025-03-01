import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Получаем все товары
cursor.execute("SELECT article, name, purchase_cost, nmID, category FROM products")
products = cursor.fetchall()

# Обновляем артикулы
for product in products:
    old_article = product[0]
    new_article = old_article.lower()
    if old_article != new_article:
        cursor.execute("UPDATE products SET article = ? WHERE article = ?",
                       (new_article, old_article))

conn.commit()
conn.close()
print("Артикулы нормализованы.")