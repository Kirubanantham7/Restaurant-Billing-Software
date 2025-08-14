import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import sqlite3
import os
import webbrowser
from datetime import datetime, timedelta
from billing import generate_pdf_bill

# =========================
# GLOBALS
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_FOLDER = os.path.join(BASE_DIR, "images")

# runtime state
menu_data = []            # [(id, name, price, image_path, tax_percent), ...]
item_entries = {}         # item_id -> qty Entry
image_refs = []           # to keep PhotoImage alive

# Tk variables (created in main_app)
order_mode = None
payment_method = None
subtotal_var = None
total_var = None
discount_entry = None
tax_entry = None

root = None


# =========================
# DB SETUP / HELPERS
# =========================
def init_db():
    """Create required tables if missing and seed a default admin user."""
    conn = sqlite3.connect("restaurant.db")
    c = conn.cursor()

    # Users (for login)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    # Menu items
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            image_path TEXT,
            tax_percent REAL DEFAULT 0
        )
    """)

    # Orders / items / payments
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            mode TEXT,
            total REAL,
            discount REAL,
            tax REAL,
            final_total REAL,
            invoice_number TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_id INTEGER,
            quantity INTEGER,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(item_id) REFERENCES menu_items(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            payment_method TEXT,
            amount_paid REAL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
    """)

    # Optional: reports log
    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_on TEXT,
            period TEXT,
            total_orders INTEGER,
            total_sales REAL,
            total_tax REAL
        )
    """)

    # Seed default admin if not present
    c.execute("SELECT COUNT(*) FROM users")
    if (c.fetchone() or [0])[0] == 0:
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "1234", "admin")
        )

    conn.commit()
    conn.close()


def load_menu():
    """Load menu into memory."""
    global menu_data
    conn = sqlite3.connect("restaurant.db")
    c = conn.cursor()
    c.execute("SELECT id, name, price, image_path, tax_percent FROM menu_items")
    menu_data = c.fetchall() or []
    conn.close()


# =========================
# CALCULATIONS
# =========================
def calculate_total():
    """Compute subtotal, per-item tax, apply discount, update UI."""
    subtotal = 0.0
    total_tax = 0.0

    for item_id, entry in item_entries.items():
        val = entry.get()
        try:
            qty = int(val) if val else 0
        except ValueError:
            messagebox.showerror("Input Error", f"Invalid quantity '{val}'")
            return

        if qty > 0:
            item = next((i for i in menu_data if i[0] == item_id), None)
            if item:
                price = float(item[2])
                tax_percent = float(item[4] or 0)
                line_total = qty * price
                subtotal += line_total
                total_tax += (line_total * tax_percent / 100.0)

    try:
        discount = float(discount_entry.get() or 0)
    except ValueError:
        messagebox.showerror("Input Error", "Enter a valid discount")
        return

    total = subtotal - discount + total_tax
    subtotal_var.set(f"{subtotal:.2f}")
    tax_entry.delete(0, tk.END)
    tax_entry.insert(0, f"{total_tax:.2f}")
    total_var.set(f"{total:.2f}")


# =========================
# EXPORT HELPERS
# =========================
def export_bill_csv(order_id, items, totals):
    """Export bill items + totals to CSV. Returns filename."""
    fname = f"bill_order_{order_id}.csv"
    import csv
    with open(fname, 'w', newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(['Item', 'Quantity', 'Price', 'Total'])
        for itm in items:
            writer.writerow([itm['name'], itm['quantity'], itm['price'], itm['quantity'] * itm['price']])
        writer.writerow([])
        writer.writerow(['Subtotal', totals['subtotal']])
        writer.writerow(['Discount', totals['discount']])
        writer.writerow(['Tax', totals['tax']])
        writer.writerow(['Final Total', totals['final_total']])
    return fname


def export_bill_json(order_id, items, totals):
    """Export bill as JSON. Returns filename."""
    fname = f"bill_order_{order_id}.json"
    import json
    data = {
        'order_id': order_id,
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'items': items,
        'totals': totals,
    }
    with open(fname, 'w', encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return fname


# =========================
# BILL PREVIEW
# =========================
def display_bill_preview(invoice_number, items, totals, pdf_path):
    win = tk.Toplevel(root)
    win.title(f"Bill Preview — Order {invoice_number}")
    win.geometry("520x640")

    # ====== Logo ======
    try:
        logo_image = Image.open("kiruba.png")
        logo_image = logo_image.resize((100, 100), Image.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_image)

        logo_label = tk.Label(win, image=logo_photo, bg="white")
        logo_label.image = logo_photo
        logo_label.pack(pady=5)
    except Exception as e:
        tk.Label(win, text="KIRUBA RESTAURANT", font=("Arial", 16, "bold"), bg="white").pack(pady=5)

    tk.Label(win, text=f"Invoice #: {invoice_number}", font=("Arial", 14, "bold")).pack(pady=5)
    tk.Label(win, text=f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}").pack()

    text = tk.Text(win, width=64, height=22, font=("Courier New", 10))
    text.pack(pady=10)
    for itm in items:
        line = f"{itm['name']:<22} x{itm['quantity']:<3} ₹{itm['price']:<7.2f} = ₹{itm['quantity'] * itm['price']:.2f}"
        text.insert(tk.END, line + "\n")
    text.insert(tk.END, f"{'-'*40}\n")
    text.insert(tk.END, f"Subtotal:   ₹{totals['subtotal']:.2f}\n")
    text.insert(tk.END, f"Discount:   ₹{totals['discount']:.2f}\n")
    text.insert(tk.END, f"Tax:        ₹{totals['tax']:.2f}\n")
    text.insert(tk.END, f"Final Total:₹{totals['final_total']:.2f}\n")
    text.insert(tk.END, f"{'-'*40}\n")
    text.insert(tk.END, "Thank You! Visit Again...\n")
    text.insert(tk.END, f"{'-'*40}\n")
    text.config(state="disabled")

    def show_pdf_path():
        messagebox.showinfo("PDF Saved", f"Saved at:\n{os.path.abspath(pdf_path)}")

    def export_csv_btn():
        p = export_bill_csv(invoice_number, items, totals)
        messagebox.showinfo("CSV", f"Saved: {p}")

    def export_json_btn():
        p = export_bill_json(invoice_number, items, totals)
        messagebox.showinfo("JSON", f"Saved: {p}")

    def share_whatsapp():
        abs_path = os.path.abspath(pdf_path)
        if os.path.exists(abs_path):
            webbrowser.open("https://web.whatsapp.com")
            messagebox.showinfo("WhatsApp", f"Attach this file manually:\n{abs_path}")
        else:
            messagebox.showerror("Error", "PDF not found.")

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Show PDF Location", command=show_pdf_path).grid(row=0, column=0, padx=5)
    tk.Button(btn_frame, text="Export CSV", command=export_csv_btn).grid(row=0, column=1, padx=5)
    tk.Button(btn_frame, text="Export JSON", command=export_json_btn).grid(row=0, column=2, padx=5)
    tk.Button(btn_frame, text="Share via WhatsApp", command=share_whatsapp).grid(row=1, column=0, columnspan=3, pady=10)


# =========================
# ORDER SUBMISSION
# =========================
def submit_order():
    calculate_total()
    final = float(total_var.get())
    if final <= 0:
        messagebox.showwarning("Empty Order", "Add items before submitting.")
        return

    conn = sqlite3.connect("restaurant.db")
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subtotal = float(subtotal_var.get())
    discount = float(discount_entry.get() or 0)
    tax = float(tax_entry.get() or 0)

    # Insert order
    c.execute("""
        INSERT INTO orders (timestamp, mode, total, discount, tax, final_total)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, order_mode.get(), subtotal, discount, tax, final))
    order_id = c.lastrowid

    # Invoice number
    year = datetime.now().year
    invoice_number = f"ORD-{year}-{order_id:04d}"

    try:
        c.execute("UPDATE orders SET invoice_number = ? WHERE id = ?", (invoice_number, order_id))
    except sqlite3.OperationalError:
        pass

    # Items
    ordered_items = []
    for item_id, entry in item_entries.items():
        try:
            qty = int(entry.get() or 0)
        except ValueError:
            qty = 0
        if qty > 0:
            c.execute("INSERT INTO order_items (order_id, item_id, quantity) VALUES (?, ?, ?)",
                      (order_id, item_id, qty))
            item = next((i for i in menu_data if i[0] == item_id), None)
            if item:
                ordered_items.append({'name': item[1], 'price': float(item[2]), 'quantity': qty})

    # Payment
    c.execute("INSERT INTO payments (order_id, payment_method, amount_paid) VALUES (?, ?, ?)",
              (order_id, payment_method.get(), final))

    conn.commit()
    conn.close()

    # Generate PDF & preview
    pdf_path = f"bill_{invoice_number}.pdf"
    totals = {'subtotal': subtotal, 'discount': discount, 'tax': tax, 'final_total': final}
    generate_pdf_bill(invoice_number, ordered_items, totals, pdf_path)
    messagebox.showinfo("Success", f"Bill saved as {pdf_path}")
    display_bill_preview(invoice_number, ordered_items, totals, pdf_path)


# =========================
# SALES DASHBOARD
# =========================
def open_sales_dashboard():
    win = tk.Toplevel(root)
    win.title("📊 Sales Report Dashboard")
    win.geometry("620x620")

    sales_data = {}

    def fetch_report(mode):
        nonlocal sales_data
        now = datetime.now()
        if mode == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif mode == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif mode == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return

        conn = sqlite3.connect("restaurant.db")
        c = conn.cursor()

        c.execute("""
            SELECT COUNT(*), SUM(final_total), SUM(tax)
            FROM orders
            WHERE timestamp >= ?
        """, (start.strftime("%Y-%m-%d %H:%M:%S"),))
        row = c.fetchone() or (0, 0.0, 0.0)
        num_orders = row[0] or 0
        total_sales = row[1] or 0.0
        total_tax = row[2] or 0.0

        c.execute("""
            SELECT mi.name, SUM(oi.quantity) as total_qty
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN menu_items mi ON mi.id = oi.item_id
            WHERE o.timestamp >= ?
            GROUP BY oi.item_id
            ORDER BY total_qty DESC
            LIMIT 5
        """, (start.strftime("%Y-%m-%d %H:%M:%S"),))
        top_items = c.fetchall() or []

        # (Optional) log to reports table
        c.execute("""
            INSERT INTO reports (generated_on, period, total_orders, total_sales, total_tax)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            mode, num_orders, total_sales, total_tax
        ))
        conn.commit()
        conn.close()

        sales_data = {
            'mode': mode,
            'start': start.strftime("%Y-%m-%d"),
            'orders': num_orders,
            'sales': total_sales,
            'tax': total_tax,
            'top_items': top_items
        }

        result_text.config(state="normal")
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, f"🕒 Period: {mode.capitalize()}\n")
        result_text.insert(tk.END, f"📅 From: {sales_data['start']}\n")
        result_text.insert(tk.END, f"🧾 Orders: {num_orders}\n")
        result_text.insert(tk.END, f"💰 Total Sales: ₹{total_sales:.2f}\n")
        result_text.insert(tk.END, f"🧮 Total Tax: ₹{total_tax:.2f}\n\n")
        result_text.insert(tk.END, "🔝 Most Sold Items:\n")
        for name, qty in top_items:
            result_text.insert(tk.END, f"  - {name} ({qty})\n")
        result_text.config(state="disabled")

    def export_to_csv():
        if not sales_data:
            messagebox.showwarning("No Data", "Generate a report first.")
            return
        filename = f"sales_report_{sales_data['mode']}_{sales_data['start']}.csv"
        with open(filename, 'w', newline='', encoding="utf-8") as f:
            import csv
            writer = csv.writer(f)
            writer.writerow(["Sales Report"])
            writer.writerow(["Period", sales_data['mode'].capitalize()])
            writer.writerow(["Start Date", sales_data['start']])
            writer.writerow(["Total Orders", sales_data['orders']])
            writer.writerow(["Total Sales", sales_data['sales']])
            writer.writerow(["Total Tax", sales_data['tax']])
            writer.writerow([])
            writer.writerow(["Most Sold Items"])
            writer.writerow(["Item", "Quantity"])
            for name, qty in sales_data['top_items']:
                writer.writerow([name, qty])
        messagebox.showinfo("Exported", f"CSV saved as {filename}")

    # Buttons
    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=10)
    for label in ["day", "week", "month"]:
        tk.Button(btn_frame, text=label.capitalize(),
                  width=10, command=lambda m=label: fetch_report(m)).pack(side="left", padx=6)

    result_text = tk.Text(win, width=66, height=22, font=("Courier New", 10))
    result_text.pack(pady=10)
    result_text.config(state="disabled")

    tk.Button(win, text="⬇ Export to CSV", command=export_to_csv, bg="#99ccff").pack(pady=10)


# =========================
# MENU RENDERING
# =========================
def render_menu(search_term: str, container: tk.Frame):
    """Render menu list with images + qty boxes, filtered by search_term."""
    for widget in container.winfo_children():
        widget.destroy()
    item_entries.clear()

    term = (search_term or "").strip().lower()

    for item_id, name, price, image_path, tax_percent in menu_data:
        if term and term not in (name or "").lower():
            continue

        row = tk.Frame(container, bg="white", pady=5)
        row.pack(fill="x", padx=10, pady=4)

        # image
        img_label = tk.Label(row, bg="white", width=50)
        img_label.pack(side="left", padx=6)
        full_path = None
        if image_path:
            full_path = os.path.join(IMAGE_FOLDER, os.path.basename(image_path))
        if full_path and os.path.exists(full_path):
            try:
                img = Image.open(full_path).convert("RGB").resize((50, 50))
                photo = ImageTk.PhotoImage(img)
                image_refs.append(photo)
                img_label.configure(image=photo)
            except Exception:
                img_label.configure(text="🖼️")
        else:
            img_label.configure(text="🖼️")

        # name + price + tax
        info = tk.Frame(row, bg="white")
        info.pack(side="left", padx=6)
        tk.Label(info, text=f"{name}", bg="white", font=("Arial", 12, "bold")).pack(anchor="w")
        tk.Label(info, text=f"₹{float(price):.2f}  |  Tax: {float(tax_percent or 0):.1f}%", bg="white",
                 font=("Arial", 10)).pack(anchor="w")

        # qty box
        qty_entry = tk.Entry(row, width=5, justify="center")
        qty_entry.pack(side="right", padx=5)
        item_entries[item_id] = qty_entry


# =========================
# MAIN APP UI
# =========================
def main_app():
    global order_mode, payment_method, subtotal_var, total_var
    global discount_entry, tax_entry, receipt_text, table_buttons, table_status

    root.deiconify()
    root.title("Kiruba Restaurant Billing System")
    root.geometry("1200x700")
    root.config(bg="#f2f2f2")

    order_mode = tk.StringVar(value="Dine-In")
    payment_method = tk.StringVar(value="Cash")
    subtotal_var = tk.StringVar(value="0.00")
    total_var = tk.StringVar(value="0.00")

    # ====== Logo at Top ======
    logo_frame = tk.Frame(root, bg="#f2f2f2")
    logo_frame.pack(pady=5)

    try:
        logo_image = Image.open("kiruba.png")
        logo_image = logo_image.resize((120, 120), Image.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_image)

        logo_label = tk.Label(logo_frame, image=logo_photo, bg="#f2f2f2")
        logo_label.image = logo_photo
        logo_label.pack()
    except:
        tk.Label(logo_frame, text="KIRUBA RESTAURANT",
                 font=("Arial", 20, "bold"), bg="#f2f2f2").pack()

    # ====== Title Below Logo ======
    tk.Label(root, text="Welcome to KIRUBA RESTAURANT",
             font=("Arial", 16), bg="#f2f2f2").pack()

    # ====== Header Bar ======
    header = tk.Frame(root, bg="#003366", height=50)
    header.pack(fill="x")
    tk.Label(header, text="🍽️ For the love of delicious food ", fg="white", bg="#003366",
             font=("Arial", 20, "bold")).pack(pady=5)

    # ====== Main Content Frame ======
    main_frame = tk.Frame(root, bg="#f2f2f2")
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)

    # LEFT FRAME (Menu)
    left_frame = tk.Frame(main_frame, bg="white", bd=2, relief="groove")
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

    # Search Bar
    search_frame = tk.Frame(left_frame, bg="white")
    search_frame.pack(fill='x', padx=10, pady=(10, 0))
    tk.Label(search_frame, text="🔍 Search:", bg="white").pack(side="left")
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True, padx=5)

    # Scrollable Menu
    tk.Label(left_frame, text="Menu", bg="white", font=("Arial", 16, "bold")).pack(anchor='w', padx=10, pady=10)
    menu_canvas = tk.Canvas(left_frame, bg="white", highlightthickness=0)
    menu_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=menu_canvas.yview)
    menu_items_frame = tk.Frame(menu_canvas, bg="white")
    menu_items_frame.bind("<Configure>", lambda e: menu_canvas.configure(scrollregion=menu_canvas.bbox("all")))
    menu_canvas.create_window((0, 0), window=menu_items_frame, anchor="nw")
    menu_canvas.configure(yscrollcommand=menu_scroll.set)
    menu_canvas.pack(side="left", fill="both", expand=True)
    menu_scroll.pack(side="right", fill="y")

    load_menu()
    render_menu("", menu_items_frame)
    search_var.trace_add("write", lambda *_: render_menu(search_var.get(), menu_items_frame))

    # ====== MIDDLE FRAME ======
    middle_frame = tk.Frame(main_frame, bg="white", bd=2, relief="groove", width=350)
    middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))

    # Live Bill Preview
    tk.Label(middle_frame, text="🧾 Live Bill Preview", bg="white", font=("Arial", 14, "bold")).pack(pady=5)
    receipt_text = tk.Text(middle_frame, width=40, height=20, font=("Courier New", 10), state="disabled", bg="#f9f9f9")
    receipt_text.pack(padx=10, pady=5)

    def update_receipt_preview():
        receipt_text.config(state="normal")
        receipt_text.delete("1.0", tk.END)
        receipt_text.insert(tk.END, "   KIRUBA RESTAURANT\n")
        receipt_text.insert(tk.END, "  -----------------------\n")
        receipt_text.insert(tk.END, "Item       Qty   Total\n")
        receipt_text.insert(tk.END, "Pizza       2    500\n")
        receipt_text.insert(tk.END, "Burger      1    120\n")
        receipt_text.insert(tk.END, "-----------------------\n")
        receipt_text.insert(tk.END, f"Total:           620\n")
        receipt_text.insert(tk.END, "Thank You! Visit Again\n")
        receipt_text.config(state="disabled")

    update_receipt_preview()

    # Table Occupancy
    tk.Label(middle_frame, text="🍽️ Table Occupancy", bg="white", font=("Arial", 14, "bold")).pack(pady=5)
    table_frame = tk.Frame(middle_frame, bg="white")
    table_frame.pack()

    table_buttons = {}
    table_status = {}

    def toggle_table(table_num, duration=5):
        if table_status[table_num] == "free":
            table_status[table_num] = "occupied"
            table_buttons[table_num].config(bg="red", text=f"Table {table_num}\n🔴 Occupied")
            root.after(duration * 1000, lambda: free_table(table_num))
        else:
            free_table(table_num)

    def free_table(table_num):
        table_status[table_num] = "free"
        table_buttons[table_num].config(bg="green", text=f"Table {table_num}\n🟢 Free")

    for t in range(1, 21):
        table_status[t] = "free"
        btn = tk.Button(table_frame, text=f"Table {t}\n🟢 Free", bg="green", fg="white",
                        width=12, height=2, command=lambda x=t: toggle_table(x, 15))
        btn.grid(row=(t - 1) // 5, column=(t - 1) % 5, padx=5, pady=5)
        table_buttons[t] = btn

    # RIGHT FRAME (Billing)
    right_frame = tk.Frame(main_frame, bg="white", bd=2, relief="groove")
    right_frame.pack(side=tk.RIGHT, fill=tk.Y)

    ttk.Combobox(right_frame, values=["Dine-In", "Takeaway"],
                 textvariable=order_mode, state="readonly").pack(fill='x', padx=10, pady=10)

    tk.Label(right_frame, text="Discount (₹):", bg="white", font=('Arial', 12)).pack(anchor='w', padx=10, pady=(10, 0))
    discount_entry = tk.Entry(right_frame)
    discount_entry.pack(fill='x', padx=10)

    tk.Label(right_frame, text="Tax (₹):", bg="white", font=('Arial', 12)).pack(anchor='w', padx=10, pady=(10, 0))
    tax_entry = tk.Entry(right_frame)
    tax_entry.pack(fill='x', padx=10)

    tk.Label(right_frame, text="Subtotal:", bg="white", font=('Arial', 12)).pack(anchor='w', padx=10, pady=(20, 0))
    tk.Label(right_frame, textvariable=subtotal_var, bg="white", font=('Arial', 12, "bold")).pack(anchor='w', padx=10)

    tk.Label(right_frame, text="Final Total:", bg="white", font=('Arial', 12)).pack(anchor='w', padx=10, pady=(10, 0))
    tk.Label(right_frame, textvariable=total_var, bg="white", font=('Arial', 12, "bold")).pack(anchor='w', padx=10)

    tk.Label(right_frame, text="Payment Method:", bg="white", font=('Arial', 12)).pack(anchor='w', padx=10, pady=(20, 0))
    ttk.Combobox(right_frame, values=["Cash", "Card", "UPI"],
                 textvariable=payment_method, state="readonly").pack(fill='x', padx=10)

    tk.Button(right_frame, text="Calculate Total", command=calculate_total, bg="#cce6ff").pack(fill='x', padx=10, pady=(15, 5))
    tk.Button(right_frame, text="Submit & Generate Bill", command=submit_order, bg="#004d00", fg="white").pack(fill='x', padx=10)
    tk.Button(right_frame, text="View Sales Report", command=open_sales_dashboard, bg="#ffcc00").pack(fill='x', padx=10, pady=10)

# =========================
# LOGIN FLOW
# =========================
def show_login():
    login_win = tk.Toplevel(root)
    login_win.title("🔐 Login")
    login_win.geometry("320x260")
    login_win.grab_set()  # modal

    # ====== Logo ======
    try:
        logo_image = Image.open("kiruba.png")
        logo_image = logo_image.resize((100, 100), Image.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_image)

        logo_label = tk.Label(login_win, image=logo_photo, bg="white")
        logo_label.image = logo_photo
        logo_label.pack(pady=5)
    except Exception as e:
        tk.Label(login_win, text="KIRUBA RESTAURANT", font=("Arial", 16, "bold"), bg="white").pack(pady=5)

    tk.Label(login_win, text="Login", font=("Arial", 16, "bold")).pack(pady=10)

    tk.Label(login_win, text="Username").pack()
    username_entry = tk.Entry(login_win)
    username_entry.pack(pady=5)

    tk.Label(login_win, text="Password").pack()
    password_entry = tk.Entry(login_win, show="*")
    password_entry.pack(pady=5)

    role_var = tk.StringVar(value="cashier")
    tk.Label(login_win, text="Role").pack()
    ttk.Combobox(login_win, textvariable=role_var, values=["admin", "cashier"], state="readonly").pack(pady=5)

    def do_login():
        username = username_entry.get().strip()
        password = password_entry.get().strip()
        role = role_var.get()

        conn = sqlite3.connect("restaurant.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE username = ? AND password = ? AND role = ?", (username, password, role))
        ok = c.fetchone()
        conn.close()

        if ok:
            messagebox.showinfo("Success", f"Welcome {role.capitalize()}!")
            login_win.destroy()
            main_app()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials")

    tk.Button(login_win, text="Login", command=do_login, bg="#d9edf7").pack(pady=10)


# =========================
# APP ENTRY
# =========================
if __name__ == "__main__":
    init_db()

    # create root hidden; show after login success
    root = tk.Tk()
    root.withdraw()

    show_login()
    root.mainloop()
 