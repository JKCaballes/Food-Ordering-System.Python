"""
app.py
Tkinter UI for the Food Ordering System.

Run with:  python app.py
"""

import tkinter as tk
from tkinter import ttk, messagebox

from database import FoodDB


class FoodOrderingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Food Ordering System")
        self.geometry("950x600")
        self.minsize(850, 550)

        self.db = FoodDB()
        self.cart = {}  # menu_item_id -> {"item": dict, "quantity": int}

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.order_tab = OrderTab(notebook, self.db, self)
        self.history_tab = HistoryTab(notebook, self.db)
        self.admin_tab = AdminTab(notebook, self.db, self)

        notebook.add(self.order_tab, text="Order Menu")
        notebook.add(self.history_tab, text="Order History")
        notebook.add(self.admin_tab, text="Manage Menu (Admin)")

        self.notebook = notebook
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, event):
        tab_text = self.notebook.tab(self.notebook.select(), "text")
        if tab_text == "Order History":
            self.history_tab.refresh()
        elif tab_text == "Manage Menu (Admin)":
            self.admin_tab.refresh()
        elif tab_text == "Order Menu":
            self.order_tab.refresh_categories()

    def refresh_all(self):
        self.order_tab.refresh_categories()
        self.order_tab.refresh_items()
        self.history_tab.refresh()


# ==========================================================================
# TAB 1: Ordering (browse menu, build cart, place order)
# ==========================================================================
class OrderTab(ttk.Frame):
    def __init__(self, parent, db: FoodDB, app: FoodOrderingApp):
        super().__init__(parent, padding=10)
        self.db = db
        self.app = app

        # ---- Left side: menu browsing ----
        left = ttk.Frame(self)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        filter_row = ttk.Frame(left)
        filter_row.pack(fill="x", pady=(0, 8))
        ttk.Label(filter_row, text="Category:").pack(side="left")
        self.category_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(
            filter_row, textvariable=self.category_var, state="readonly", width=20
        )
        self.category_combo.pack(side="left", padx=5)
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_items())

        columns = ("name", "description", "price", "category")
        self.menu_tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        self.menu_tree.heading("name", text="Item")
        self.menu_tree.heading("description", text="Description")
        self.menu_tree.heading("price", text="Price")
        self.menu_tree.heading("category", text="Category")
        self.menu_tree.column("name", width=150)
        self.menu_tree.column("description", width=280)
        self.menu_tree.column("price", width=70, anchor="e")
        self.menu_tree.column("category", width=100)
        self.menu_tree.pack(fill="both", expand=True)

        add_row = ttk.Frame(left)
        add_row.pack(fill="x", pady=8)
        ttk.Label(add_row, text="Qty:").pack(side="left")
        self.qty_var = tk.IntVar(value=1)
        qty_spin = ttk.Spinbox(add_row, from_=1, to=50, textvariable=self.qty_var, width=5)
        qty_spin.pack(side="left", padx=5)
        ttk.Button(add_row, text="Add to Cart →", command=self.add_to_cart).pack(side="left", padx=5)

        # ---- Right side: cart & checkout ----
        right = ttk.Frame(self, width=320)
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Your Cart", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        cart_columns = ("name", "qty", "subtotal")
        self.cart_tree = ttk.Treeview(right, columns=cart_columns, show="headings", height=12)
        self.cart_tree.heading("name", text="Item")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("subtotal", text="Subtotal")
        self.cart_tree.column("name", width=150)
        self.cart_tree.column("qty", width=40, anchor="center")
        self.cart_tree.column("subtotal", width=80, anchor="e")
        self.cart_tree.pack(fill="both", expand=False, pady=5)

        cart_btn_row = ttk.Frame(right)
        cart_btn_row.pack(fill="x")
        ttk.Button(cart_btn_row, text="Remove Selected", command=self.remove_from_cart).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(cart_btn_row, text="Clear Cart", command=self.clear_cart).pack(side="left")

        self.total_var = tk.StringVar(value="Total: $0.00")
        ttk.Label(right, textvariable=self.total_var, font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", pady=10
        )

        ttk.Label(right, text="Customer Name:").pack(anchor="w")
        self.customer_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.customer_var).pack(fill="x", pady=(0, 10))

        ttk.Button(right, text="Place Order", command=self.place_order).pack(fill="x")

        self.refresh_categories()
        self.refresh_items()

    def refresh_categories(self):
        categories = ["All"] + self.db.get_categories()
        self.category_combo["values"] = categories
        if self.category_var.get() not in categories:
            self.category_var.set("All")

    def refresh_items(self):
        for row in self.menu_tree.get_children():
            self.menu_tree.delete(row)
        category = self.category_var.get()
        items = self.db.get_menu_items(category=category, only_available=True)
        for item in items:
            self.menu_tree.insert(
                "", "end", iid=str(item["id"]),
                values=(item["name"], item["description"] or "", f"${item['price']:.2f}", item["category"]),
            )

    def add_to_cart(self):
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showinfo("Select an item", "Please select a menu item first.")
            return
        item_id = int(selection[0])
        qty = self.qty_var.get()
        if qty <= 0:
            messagebox.showinfo("Invalid quantity", "Quantity must be at least 1.")
            return

        item = self.db.get_menu_item(item_id)
        if item is None:
            return

        if item_id in self.cart:
            self.cart[item_id]["quantity"] += qty
        else:
            self.cart[item_id] = {"item": item, "quantity": qty}

        self._refresh_cart_view()

    def remove_from_cart(self):
        selection = self.cart_tree.selection()
        if not selection:
            return
        item_id = int(selection[0])
        if item_id in self.cart:
            del self.cart[item_id]
        self._refresh_cart_view()

    def clear_cart(self):
        self.cart = {}
        self._refresh_cart_view()

    def _refresh_cart_view(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        total = 0.0
        for item_id, entry in self.cart.items():
            item = entry["item"]
            qty = entry["quantity"]
            subtotal = item["price"] * qty
            total += subtotal
            self.cart_tree.insert(
                "", "end", iid=str(item_id),
                values=(item["name"], qty, f"${subtotal:.2f}"),
            )
        self.total_var.set(f"Total: ${total:.2f}")

    def place_order(self):
        if not self.cart:
            messagebox.showinfo("Empty cart", "Add at least one item before placing an order.")
            return
        customer_name = self.customer_var.get().strip()
        if not customer_name:
            messagebox.showinfo("Name required", "Please enter a customer name.")
            return

        cart_items = [
            {"id": item_id, "quantity": entry["quantity"]}
            for item_id, entry in self.cart.items()
        ]
        order_id = self.db.create_order(customer_name, cart_items)
        messagebox.showinfo("Order placed", f"Order #{order_id} placed successfully!")

        self.clear_cart()
        self.customer_var.set("")
        self.app.history_tab.refresh()


# ==========================================================================
# TAB 2: Order history
# ==========================================================================
class HistoryTab(ttk.Frame):
    STATUSES = ["All", "Placed", "Preparing", "Out for Delivery", "Completed", "Cancelled"]

    def __init__(self, parent, db: FoodDB):
        super().__init__(parent, padding=10)
        self.db = db

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Filter by status:").pack(side="left")
        self.status_filter = tk.StringVar(value="All")
        combo = ttk.Combobox(
            top, textvariable=self.status_filter, values=self.STATUSES, state="readonly", width=18
        )
        combo.pack(side="left", padx=5)
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=5)

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        # Orders list
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        columns = ("id", "customer", "date", "status", "total")
        self.orders_tree = ttk.Treeview(left, columns=columns, show="headings")
        for col, label, width in [
            ("id", "Order #", 60), ("customer", "Customer", 140),
            ("date", "Date", 150), ("status", "Status", 120), ("total", "Total", 80),
        ]:
            self.orders_tree.heading(col, text=label)
            self.orders_tree.column(col, width=width, anchor="center" if col in ("id", "status") else "w")
        self.orders_tree.pack(fill="both", expand=True)
        self.orders_tree.bind("<<TreeviewSelect>>", self._on_select_order)

        # Order detail panel
        right = ttk.Frame(main, width=280)
        right.pack(side="right", fill="y")
        ttk.Label(right, text="Order Details", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        detail_columns = ("item", "qty", "price")
        self.detail_tree = ttk.Treeview(right, columns=detail_columns, show="headings", height=10)
        self.detail_tree.heading("item", text="Item")
        self.detail_tree.heading("qty", text="Qty")
        self.detail_tree.heading("price", text="Price")
        self.detail_tree.column("item", width=140)
        self.detail_tree.column("qty", width=40, anchor="center")
        self.detail_tree.column("price", width=70, anchor="e")
        self.detail_tree.pack(fill="both", pady=5)

        status_row = ttk.Frame(right)
        status_row.pack(fill="x", pady=8)
        ttk.Label(status_row, text="Update status:").pack(anchor="w")
        self.update_status_var = tk.StringVar()
        self.update_combo = ttk.Combobox(
            status_row, textvariable=self.update_status_var,
            values=self.STATUSES[1:], state="readonly",
        )
        self.update_combo.pack(fill="x", pady=3)
        ttk.Button(status_row, text="Apply Status", command=self.apply_status).pack(fill="x")

        self.selected_order_id = None
        self.refresh()

    def refresh(self):
        for row in self.orders_tree.get_children():
            self.orders_tree.delete(row)
        orders = self.db.get_orders(status=self.status_filter.get())
        for o in orders:
            self.orders_tree.insert(
                "", "end", iid=str(o["id"]),
                values=(o["id"], o["customer_name"], o["created_at"], o["status"], f"${o['total']:.2f}"),
            )
        for row in self.detail_tree.get_children():
            self.detail_tree.delete(row)
        self.selected_order_id = None

    def _on_select_order(self, event):
        selection = self.orders_tree.selection()
        if not selection:
            return
        order_id = int(selection[0])
        self.selected_order_id = order_id
        for row in self.detail_tree.get_children():
            self.detail_tree.delete(row)
        for item in self.db.get_order_items(order_id):
            self.detail_tree.insert(
                "", "end",
                values=(item["item_name"], item["quantity"], f"${item['price_each']:.2f}"),
            )
        current_status = self.orders_tree.set(str(order_id), "status")
        self.update_status_var.set(current_status)

    def apply_status(self):
        if self.selected_order_id is None:
            messagebox.showinfo("No order selected", "Select an order first.")
            return
        new_status = self.update_status_var.get()
        if not new_status:
            return
        self.db.update_order_status(self.selected_order_id, new_status)
        self.refresh()


# ==========================================================================
# TAB 3: Admin - manage menu items
# ==========================================================================
class AdminTab(ttk.Frame):
    def __init__(self, parent, db: FoodDB, app: FoodOrderingApp):
        super().__init__(parent, padding=10)
        self.db = db
        self.app = app
        self.editing_id = None

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        columns = ("id", "name", "price", "category", "available")
        self.tree = ttk.Treeview(left, columns=columns, show="headings")
        for col, label, width in [
            ("id", "ID", 40), ("name", "Name", 160), ("price", "Price", 70),
            ("category", "Category", 110), ("available", "Available", 80),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center" if col in ("id", "available") else "w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        ttk.Button(left, text="Delete Selected", command=self.delete_item).pack(anchor="w", pady=6)

        # Form on the right
        form = ttk.LabelFrame(main, text="Add / Edit Menu Item", padding=10)
        form.pack(side="right", fill="y")

        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w", pady=3)
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=28).grid(row=0, column=1, pady=3)

        ttk.Label(form, text="Description:").grid(row=1, column=0, sticky="w", pady=3)
        self.desc_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.desc_var, width=28).grid(row=1, column=1, pady=3)

        ttk.Label(form, text="Price:").grid(row=2, column=0, sticky="w", pady=3)
        self.price_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.price_var, width=28).grid(row=2, column=1, pady=3)

        ttk.Label(form, text="Category:").grid(row=3, column=0, sticky="w", pady=3)
        self.cat_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.cat_var, width=28).grid(row=3, column=1, pady=3)

        self.avail_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Available", variable=self.avail_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=5
        )

        btn_row = ttk.Frame(form)
        btn_row.grid(row=5, column=0, columnspan=2, pady=8, sticky="ew")
        ttk.Button(btn_row, text="Save", command=self.save_item).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="Clear / New", command=self.clear_form).pack(side="left")

        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        items = self.db.get_menu_items(only_available=False)
        for item in items:
            self.tree.insert(
                "", "end", iid=str(item["id"]),
                values=(
                    item["id"], item["name"], f"${item['price']:.2f}",
                    item["category"], "Yes" if item["available"] else "No",
                ),
            )

    def _on_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        item_id = int(selection[0])
        item = self.db.get_menu_item(item_id)
        if not item:
            return
        self.editing_id = item_id
        self.name_var.set(item["name"])
        self.desc_var.set(item["description"] or "")
        self.price_var.set(str(item["price"]))
        self.cat_var.set(item["category"])
        self.avail_var.set(bool(item["available"]))

    def clear_form(self):
        self.editing_id = None
        self.name_var.set("")
        self.desc_var.set("")
        self.price_var.set("")
        self.cat_var.set("")
        self.avail_var.set(True)
        self.tree.selection_remove(self.tree.selection())

    def save_item(self):
        name = self.name_var.get().strip()
        description = self.desc_var.get().strip()
        category = self.cat_var.get().strip()
        price_text = self.price_var.get().strip()

        if not name or not category or not price_text:
            messagebox.showinfo("Missing fields", "Name, price, and category are required.")
            return
        try:
            price = float(price_text)
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showinfo("Invalid price", "Please enter a valid non-negative price.")
            return

        available = self.avail_var.get()

        if self.editing_id is None:
            self.db.add_menu_item(name, description, price, category, available)
            messagebox.showinfo("Added", f"'{name}' added to the menu.")
        else:
            self.db.update_menu_item(self.editing_id, name, description, price, category, available)
            messagebox.showinfo("Updated", f"'{name}' updated.")

        self.clear_form()
        self.refresh()
        self.app.refresh_all()

    def delete_item(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select an item", "Select a menu item to delete.")
            return
        item_id = int(selection[0])
        item = self.db.get_menu_item(item_id)
        name = item["name"] if item else "this item"
        if messagebox.askyesno("Confirm delete", f"Delete '{name}' from the menu?"):
            self.db.delete_menu_item(item_id)
            self.clear_form()
            self.refresh()
            self.app.refresh_all()


if __name__ == "__main__":
    app = FoodOrderingApp()
    app.mainloop()