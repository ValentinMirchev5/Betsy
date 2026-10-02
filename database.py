import sqlite3


DB_NAME = "betsy.db"


def get_connection():
    connection = sqlite3.connect(DB_NAME)

    # This lets us access columns by name later:
    # row["name"] instead of row[0]
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    # -----------------------------
    # Inventory table
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            current_stock INTEGER NOT NULL,
            daily_usage REAL NOT NULL,
            safety_stock INTEGER NOT NULL,
            reorder_threshold_days REAL NOT NULL
        )
    """)

    # -----------------------------
    # Suppliers table
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            reliability REAL NOT NULL
        )
    """)

    # -----------------------------
    # Supplier offers table
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            inventory_id INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            delivery_hours INTEGER NOT NULL,
            available INTEGER NOT NULL DEFAULT 1,

            FOREIGN KEY (supplier_id)
                REFERENCES suppliers(id),

            FOREIGN KEY (inventory_id)
                REFERENCES inventory(id)
        )
    """)

    # -----------------------------
    # Purchase orders table
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            inventory_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            status TEXT NOT NULL,

            FOREIGN KEY (inventory_id)
                REFERENCES inventory(id),

            FOREIGN KEY (supplier_id)
                REFERENCES suppliers(id)
        )
    """)

    # -----------------------------
    # Decision log table
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)

    connection.commit()

    seed_demo_data(connection)

    connection.close()


def seed_demo_data(connection):
    cursor = connection.cursor()

    # Prevent duplicate demo data
    product_count = cursor.execute(
        "SELECT COUNT(*) FROM inventory"
    ).fetchone()[0]

    if product_count > 0:
        return

    # -----------------------------
    # Demo inventory item
    # -----------------------------
    cursor.execute("""
        INSERT INTO inventory (
            sku,
            name,
            current_stock,
            daily_usage,
            safety_stock,
            reorder_threshold_days
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "BRG-001",
        "Industrial Bearings",
        400,
        60,
        50,
        3
    ))

    product_id = cursor.lastrowid

    # -----------------------------
    # Demo suppliers
    # -----------------------------
    suppliers = [
        ("AccuParts Corp", 96),
        ("PrecisionSource", 94),
        ("QuickMachine", 88)
    ]

    supplier_ids = {}

    for name, reliability in suppliers:
        cursor.execute("""
            INSERT INTO suppliers (
                name,
                reliability
            )
            VALUES (?, ?)
        """, (
            name,
            reliability
        ))

        supplier_ids[name] = cursor.lastrowid

    # -----------------------------
    # Supplier offers
    # -----------------------------
    offers = [
        (
            supplier_ids["AccuParts Corp"],
            product_id,
            247,
            48
        ),
        (
            supplier_ids["PrecisionSource"],
            product_id,
            289,
            24
        ),
        (
            supplier_ids["QuickMachine"],
            product_id,
            231,
            72
        )
    ]

    cursor.executemany("""
        INSERT INTO supplier_products (
            supplier_id,
            inventory_id,
            unit_price,
            delivery_hours
        )
        VALUES (?, ?, ?, ?)
    """, offers)

    connection.commit()


def show_demo_data():
    connection = get_connection()

    print("\n--- INVENTORY ---")

    inventory = connection.execute("""
        SELECT *
        FROM inventory
    """).fetchall()

    for item in inventory:
        print(
            f"{item['name']} | "
            f"Stock: {item['current_stock']} | "
            f"Usage: {item['daily_usage']}/day"
        )

    print("\n--- SUPPLIERS ---")

    suppliers = connection.execute("""
        SELECT
            suppliers.name,
            suppliers.reliability,
            supplier_products.unit_price,
            supplier_products.delivery_hours
        FROM supplier_products
        JOIN suppliers
            ON suppliers.id = supplier_products.supplier_id
    """).fetchall()

    for supplier in suppliers:
        print(
            f"{supplier['name']} | "
            f"EUR {supplier['unit_price']} | "
            f"{supplier['delivery_hours']}h | "
            f"Reliability: {supplier['reliability']}%"
        )

    connection.close()


if __name__ == "__main__":
    initialize_database()
    show_demo_data()
