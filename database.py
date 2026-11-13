import sqlite3
from datetime import datetime


DB_NAME = "betsy.db"


def get_connection():
    connection = sqlite3.connect(DB_NAME)

    # Allows access like row["name"] instead of row[0]
    connection.row_factory = sqlite3.Row

    return connection


# --------------------------------------------------
# Database initialization
# --------------------------------------------------

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

    # -----------------------------
    # AI recommendation table
    # -----------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            model_name TEXT NOT NULL,
            product TEXT NOT NULL,
            supplier TEXT NOT NULL,
            confidence REAL NOT NULL,
            risk_level TEXT NOT NULL,
            reasoning TEXT NOT NULL,
            validation_status TEXT NOT NULL
        )
    """)

    connection.commit()

    seed_demo_data(connection)

    connection.close()


# --------------------------------------------------
# Demo seed data
# --------------------------------------------------

def seed_demo_data(connection):
    cursor = connection.cursor()

    product_count = cursor.execute(
        "SELECT COUNT(*) FROM inventory"
    ).fetchone()[0]

    # Prevent duplicate demo data
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


# --------------------------------------------------
# Debug/demo output
# --------------------------------------------------

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


# --------------------------------------------------
# Inventory
# --------------------------------------------------

def get_inventory():
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM inventory
        ORDER BY id
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def update_stock(product_id, new_stock):
    connection = get_connection()

    connection.execute("""
        UPDATE inventory
        SET current_stock = ?
        WHERE id = ?
    """, (
        new_stock,
        product_id
    ))

    connection.commit()
    connection.close()


# --------------------------------------------------
# Purchase orders
# --------------------------------------------------

def get_purchase_orders():
    connection = get_connection()

    rows = connection.execute("""
        SELECT
            po.id,
            po.created_at,
            i.name AS product,
            s.name AS supplier,
            po.quantity,
            po.unit_price,
            po.total_price,
            po.status

        FROM purchase_orders po

        JOIN inventory i
            ON i.id = po.inventory_id

        JOIN suppliers s
            ON s.id = po.supplier_id

        ORDER BY po.id DESC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def update_po_status(po_id, status):
    connection = get_connection()

    connection.execute("""
        UPDATE purchase_orders
        SET status = ?
        WHERE id = ?
    """, (
        status,
        po_id
    ))

    connection.commit()
    connection.close()


# --------------------------------------------------
# Decision log
# --------------------------------------------------

def get_decisions():
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM decisions
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


# --------------------------------------------------
# AI recommendations
# --------------------------------------------------

def save_ai_recommendation(
    model_name,
    product,
    supplier,
    confidence,
    risk_level,
    reasoning,
    validation_status
):
    connection = get_connection()

    connection.execute("""
        INSERT INTO ai_recommendations (
            created_at,
            model_name,
            product,
            supplier,
            confidence,
            risk_level,
            reasoning,
            validation_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(
            timespec="seconds"
        ),
        model_name,
        product,
        supplier,
        confidence,
        risk_level,
        reasoning,
        validation_status
    ))

    connection.commit()
    connection.close()


def get_latest_ai_recommendation():
    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM ai_recommendations
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


# --------------------------------------------------
# Demo reset
# --------------------------------------------------

def reset_demo():
    connection = get_connection()

    # Remove purchase orders
    connection.execute("""
        DELETE FROM purchase_orders
    """)

    # Remove decision logs
    connection.execute("""
        DELETE FROM decisions
    """)

    # Remove AI recommendations
    connection.execute("""
        DELETE FROM ai_recommendations
    """)

    # Restore inventory
    connection.execute("""
        UPDATE inventory
        SET current_stock = 400
        WHERE sku = 'BRG-001'
    """)

    # Reset IDs for demo consistency
    connection.execute("""
        DELETE FROM sqlite_sequence
        WHERE name IN (
            'purchase_orders',
            'decisions',
            'ai_recommendations'
        )
    """)

    connection.commit()
    connection.close()


# --------------------------------------------------
# Run database directly
# --------------------------------------------------

if __name__ == "__main__":
    initialize_database()
    show_demo_data()