import sqlite3
import os

# Base project directory (folder containing this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Images folder (must exist)
image_dir = os.path.join(BASE_DIR, "images")

# Ensure image folder exists
if not os.path.exists(image_dir):
    os.makedirs(image_dir)
    print(f"[INFO] Created image folder: {image_dir}")
else:
    print(f"[INFO] Using image folder: {image_dir}")

# Connect to the database
db_path = os.path.join(BASE_DIR, "restaurant.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# --- Drop (optional: development only) ---
# cursor.execute("DROP TABLE IF EXISTS menu_items")  # Uncomment if you want to reset

# --- Create Tables ---

cursor.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_on TEXT,
        period TEXT,  -- 'day', 'week', 'month'
        total_orders INTEGER,
        total_sales REAL,
        total_tax REAL
    )
''')
print("[INFO] Created 'reports' table (if not exists).")

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT  -- 'admin' or 'cashier'
    )
''')
print("[INFO] Created 'users' table (if not exists).")

# Insert default users (optional, only if table is empty)
cursor.execute("SELECT COUNT(*) FROM users")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "admin123", "admin"))
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("cashier", "cashier123", "cashier"))
    print("[INFO] Inserted default users (admin/cashier)")
    
cursor.execute('''
    CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        price REAL,
        image_path TEXT
    )
''')

# --- Try adding `tax_percent` column if missing ---
try:
    cursor.execute("ALTER TABLE menu_items ADD COLUMN tax_percent REAL DEFAULT 0")
    print("[INFO] Added missing column: tax_percent")
except sqlite3.OperationalError:
    print("[INFO] Column tax_percent already exists.")

cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        mode TEXT,
        total REAL,
        discount REAL,
        tax REAL,
        final_total REAL
    )
''')

# --- Try adding `invoice_number` column if missing ---
try:
    cursor.execute("ALTER TABLE orders ADD COLUMN invoice_number TEXT")
    print("[INFO] Added missing column: invoice_number")
except sqlite3.OperationalError:
    print("[INFO] Column invoice_number already exists.")

cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        item_id INTEGER,
        quantity INTEGER,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(item_id) REFERENCES menu_items(id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        payment_method TEXT,
        amount_paid REAL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
''')



# --- Menu Items with Image Paths ---
def resolve_image(filename):
    path = os.path.join(image_dir, filename)
    if os.path.exists(path):
        return filename
    else:
        print(f"[WARNING] Image file not found: {path}")
        return None

# ID, Name, Category, Price, Image File, Tax %
menu_data = [
    (1, 'Burger', 'Food', 120, resolve_image('burger.png'), 5),
    (2, 'Pizza', 'Food', 250, resolve_image('pizza.png'), 7),
    (3, 'Coke', 'Drink', 50, resolve_image('coke.png'), 3),
    (4, 'Water', 'Drink', 20, resolve_image('water.png'), 2),
    (5, 'Fries', 'Snack', 80, resolve_image('fries.png'), 4),
    (6, 'Paneer Butter Masala', 'Indian', 180, resolve_image('paneer_butter_masala.png'), 5),
    (7, 'Chicken Biryani', 'Indian', 220, resolve_image('chicken_biryani.png'), 6),
    (8, 'Masala Dosa', 'Indian', 100, resolve_image('masala_dosa.png'), 4),
    (9, 'Idli Sambar', 'Indian', 80, resolve_image('idli_sambar.png'), 3),
    (10, 'Medu Vada', 'Indian', 90, resolve_image('medu_vada.png'), 4),
    (11, 'Roti (2 pcs)', 'Indian', 30, resolve_image('roti.png'), 2),
    (12, 'Naan', 'Indian', 40, resolve_image('naan.png'), 2),
    (13, 'Butter Chicken', 'Indian', 240, resolve_image('butter_chicken.png'), 6),
    (14, 'Dal Tadka', 'Indian', 130, resolve_image('dal_tadka.png'), 4),
    (15, 'Chole Bhature', 'Indian', 110, resolve_image('chole_bhature.png'), 4),
    (16, 'Palak Paneer', 'Indian', 170, resolve_image('palak_paneer.png'), 5),
    (17, 'Pav Bhaji', 'Indian', 90, resolve_image('pav_bhaji.png'), 3),
    (18, 'Veg Pulao', 'Indian', 120, resolve_image('veg_pulao.png'), 4),
    (19, 'Samosa (2 pcs)', 'Snack', 40, resolve_image('samosa.png'), 2),
    (20, 'Kachori', 'Snack', 35, resolve_image('kachori.png'), 2),
    (21, 'Dhokla', 'Snack', 60, resolve_image('dhokla.png'), 3),
    (22, 'Aloo Paratha', 'Indian', 70, resolve_image('aloo_paratha.png'), 3),
    (23, 'Onion Pakora', 'Snack', 50, resolve_image('onion_pakora.png'), 2),
    (24, 'Momo (8 pcs)', 'Snack', 110, resolve_image('momo.png'), 4),
    (25, 'Spring Rolls', 'Snack', 100, resolve_image('spring_rolls.png'), 4),
    (26, 'Manchurian Dry', 'Chinese', 130, resolve_image('manchurian.png'), 5),
    (27, 'Fried Rice', 'Chinese', 140, resolve_image('fried_rice.png'), 5),
    (28, 'Hakka Noodles', 'Chinese', 150, resolve_image('hakka_noodles.png'), 5),
    (29, 'Chilli Chicken', 'Chinese', 180, resolve_image('chilli_chicken.png'), 6),
    (30, 'Tomato Soup', 'Starter', 90, resolve_image('tomato_soup.png'), 3),
    (31, 'Hot & Sour Soup', 'Starter', 100, resolve_image('hot_sour_soup.png'), 3),
    (32, 'Greek Salad', 'Salad', 130, resolve_image('greek_salad.png'), 4),
    (33, 'Caesar Salad', 'Salad', 150, resolve_image('caesar_salad.png'), 4),
    (34, 'Grilled Sandwich', 'Snack', 90, resolve_image('grilled_sandwich.png'), 4),
    (35, 'Cheese Sandwich', 'Snack', 100, resolve_image('cheese_sandwich.png'), 4),
    (36, 'Paneer Tikka', 'Indian', 160, resolve_image('paneer_tikka.png'), 5),
    (37, 'Tandoori Chicken', 'Indian', 210, resolve_image('tandoori_chicken.png'), 6),
    (38, 'Veg Thali', 'Indian', 200, resolve_image('veg_thali.png'), 5),
    (39, 'Non-Veg Thali', 'Indian', 250, resolve_image('nonveg_thali.png'), 6),
    (40, 'Ice Cream (Scoop)', 'Dessert', 60, resolve_image('ice_cream.png'), 2),
    (41, 'Gulab Jamun (2 pcs)', 'Dessert', 50, resolve_image('gulab_jamun.png'), 2),
    (42, 'Rasgulla (2 pcs)', 'Dessert', 50, resolve_image('rasgulla.png'), 2),
    (43, 'Lassi', 'Drink', 70, resolve_image('lassi.png'), 3),
    (44, 'Cold Coffee', 'Drink', 90, resolve_image('cold_coffee.png'), 3),
    (45, 'Fresh Lime Soda', 'Drink', 60, resolve_image('lime_soda.png'), 3),
    (46, 'Masala Chai', 'Drink', 40, resolve_image('masala_chai.png'), 2),
    (47, 'Espresso', 'Drink', 70, resolve_image('espresso.png'), 3),
    (48, 'Latte', 'Drink', 90, resolve_image('latte.png'), 3),
    (49, 'Chocolate Brownie', 'Dessert', 100, resolve_image('brownie.png'), 4),
    (50, 'Fruit Salad', 'Salad', 80, resolve_image('fruit_salad.png'), 3),
]

# Insert or update menu data
for item in menu_data:
    cursor.execute("""
        INSERT INTO menu_items (id, name, category, price, image_path, tax_percent)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            category=excluded.category,
            price=excluded.price,
            image_path=excluded.image_path,
            tax_percent=excluded.tax_percent
    """, item)

conn.commit()
conn.close()

print("✅ Database and menu items set up successfully.")
