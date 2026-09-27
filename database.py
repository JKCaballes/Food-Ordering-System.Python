"""
database.py
SQLite data layer for the Food Ordering System.
Handles schema creation, seeding, and all CRUD operations.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "food_orders.db")


class FoodDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Schema setup
    # ------------------------------------------------------------------
    def _init_db(self):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Placed',
                total REAL NOT NULL DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                menu_item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_each REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                FOREIGN KEY (menu_item_id) REFERENCES menu_items (id)
            )
        """)

        conn.commit()

        # Seed sample menu items if the table is empty
        cur.execute("SELECT COUNT(*) FROM menu_items")
        if cur.fetchone()[0] == 0:
            sample_items = [
                ("Margherita Pizza", "Tomato, mozzarella, basil", 8.99, "Pizza", 1),
                ("Pepperoni Pizza", "Tomato, mozzarella, pepperoni", 10.49, "Pizza", 1),
                ("Caesar Salad", "Romaine, parmesan, croutons, caesar dressing", 6.50, "Salads", 1),
                ("Garden Salad", "Mixed greens, tomato, cucumber, vinaigrette", 5.75, "Salads", 1),
                ("Classic Burger", "Beef patty, lettuce, tomato, cheese", 9.25, "Burgers", 1),
                ("Veggie Burger", "Plant-based patty, lettuce, tomato, vegan mayo", 8.75, "Burgers", 1),
                ("Spaghetti Bolognese", "Beef ragu, parmesan", 11.00, "Pasta", 1),
                ("Fettuccine Alfredo", "Creamy parmesan sauce", 10.50, "Pasta", 1),
                ("French Fries", "Crispy fries with sea salt", 3.50, "Sides", 1),
                ("Onion Rings", "Battered and fried", 4.00, "Sides", 1),
                ("Chocolate Lava Cake", "Warm cake with molten center", 5.50, "Desserts", 1),
                ("Tiramisu", "Espresso-soaked layers with mascarpone", 5.95, "Desserts", 1),
                ("Soda", "Choice of cola, lemon-lime, or root beer", 2.25, "Drinks", 1),
                ("Iced Tea", "Freshly brewed, unsweetened or sweet", 2.25, "Drinks", 1),
            ]
            cur.executemany(
                "INSERT INTO menu_items (name, description, price, category, available) "
                "VALUES (?, ?, ?, ?, ?)",
                sample_items,
            )
            conn.commit()

        conn.close()

    # ------------------------------------------------------------------
    # Menu operations
    # ------------------------------------------------------------------
    def get_categories(self):
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT category FROM menu_items ORDER BY category"
        ).fetchall()
        conn.close()
        return [r["category"] for r in rows]

    def get_menu_items(self, category=None, only_available=True):
        conn = self._connect()
        query = "SELECT * FROM menu_items"
        conditions = []
        params = []
        if category and category != "All":
            conditions.append("category = ?")
            params.append(category)
        if only_available:
            conditions.append("available = 1")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY category, name"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_menu_item(self, item_id):
        conn = self._connect()
        row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def add_menu_item(self, name, description, price, category, available=True):
        conn = self._connect()
        cur = conn.execute(
            "INSERT INTO menu_items (name, description, price, category, available) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, description, price, category, 1 if available else 0),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id

    def update_menu_item(self, item_id, name, description, price, category, available):
        conn = self._connect()
        conn.execute(
            "UPDATE menu_items SET name=?, description=?, price=?, category=?, available=? "
            "WHERE id=?",
            (name, description, price, category, 1 if available else 0, item_id),
        )
        conn.commit()
        conn.close()

    def delete_menu_item(self, item_id):
        conn = self._connect()
        conn.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------
    def create_order(self, customer_name, cart_items):
        """
        cart_items: list of dicts like {"id": menu_item_id, "quantity": qty}
        Returns the new order id.
        """
        if not cart_items:
            raise ValueError("Cannot place an order with an empty cart.")

        conn = self._connect()
        cur = conn.cursor()

        total = 0.0
        resolved = []
        for entry in cart_items:
            item = conn.execute(
                "SELECT * FROM menu_items WHERE id = ?", (entry["id"],)
            ).fetchone()
            if item is None:
                continue
            qty = entry["quantity"]
            line_total = item["price"] * qty
            total += line_total
            resolved.append((item["id"], item["name"], qty, item["price"]))

        cur.execute(
            "INSERT INTO orders (customer_name, created_at, status, total) VALUES (?, ?, ?, ?)",
            (customer_name, datetime.now().isoformat(timespec="seconds"), "Placed", total),
        )
        order_id = cur.lastrowid

        for menu_item_id, item_name, qty, price_each in resolved:
            cur.execute(
                "INSERT INTO order_items (order_id, menu_item_id, item_name, quantity, price_each) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, menu_item_id, item_name, qty, price_each),
            )

        conn.commit()
        conn.close()
        return order_id

    def get_orders(self, status=None):
        conn = self._connect()
        if status and status != "All":
            rows = conn.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_order_items(self, order_id):
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_order_status(self, order_id, status):
        conn = self._connect()
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()
        conn.close()

    def delete_order(self, order_id):
        conn = self._connect()
        conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    # Quick self-test when run directly: python database.py
    db = FoodDB(db_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_food_orders.db"))
    print("Categories:", db.get_categories())
    items = db.get_menu_items()
    print(f"Loaded {len(items)} menu items.")
    order_id = db.create_order("Test Customer", [{"id": items[0]["id"], "quantity": 2}])
    print("Created order:", order_id)
    print("Order items:", db.get_order_items(order_id))
    print("All orders:", db.get_orders())
    os.remove(db.db_path)
    print("Self-test passed and cleaned up.")