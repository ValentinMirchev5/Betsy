import math
from datetime import datetime

from database import get_connection


TARGET_STOCK_DAYS = 4


# --------------------------------------------------
# Stockout detection
# --------------------------------------------------

def detect_stockout():
    """
    Checks inventory and returns the first product
    that is inside its reorder threshold.

    Products with an already active purchase order
    are ignored to prevent duplicate orders.
    """

    connection = get_connection()

    products = connection.execute("""
        SELECT *
        FROM inventory
    """).fetchall()

    for row in products:
        product = dict(row)

        current_stock = product["current_stock"]
        daily_usage = product["daily_usage"]

        # Prevent division by zero or invalid usage values
        if daily_usage <= 0:
            continue

        days_remaining = (
            current_stock / daily_usage
        )

        # Check whether Betsy is already handling this product
        active_order = connection.execute("""
            SELECT id
            FROM purchase_orders
            WHERE inventory_id = ?
            AND status IN (
                'Pending Approval',
                'Approved'
            )
        """, (
            product["id"],
        )).fetchone()

        if active_order:
            continue

        if (
            days_remaining
            <= product["reorder_threshold_days"]
        ):
            product["days_remaining"] = (
                days_remaining
            )

            product["hours_remaining"] = (
                days_remaining * 24
            )

            connection.close()

            return product

    connection.close()

    return None


# --------------------------------------------------
# Supplier retrieval
# --------------------------------------------------

def get_supplier_options(product_id):
    """
    Retrieves all supplier offers for one product.
    """

    connection = get_connection()

    rows = connection.execute("""
        SELECT
            s.id AS supplier_id,
            s.name,
            s.reliability,
            sp.unit_price,
            sp.delivery_hours,
            sp.available

        FROM supplier_products sp

        JOIN suppliers s
            ON s.id = sp.supplier_id

        WHERE sp.inventory_id = ?
    """, (
        product_id,
    )).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# --------------------------------------------------
# Deterministic supplier filtering and scoring
# --------------------------------------------------

def evaluate_suppliers(product):
    """
    Applies hard safety rules first.

    Suppliers are rejected when:
    - they are unavailable
    - they cannot deliver before the predicted stockout

    Remaining suppliers are scored using:
    - 40% price
    - 35% delivery speed
    - 25% reliability

    This deterministic selection is also used as
    Betsy's safe fallback if the LLM is unavailable
    or produces an invalid recommendation.
    """

    suppliers = get_supplier_options(
        product["id"]
    )

    eligible_suppliers = []

    for supplier in suppliers:
        supplier["eligible"] = True
        supplier["rejection_reason"] = None

        # Hard rule: unavailable suppliers cannot be used
        if supplier["available"] == 0:
            supplier["eligible"] = False

            supplier["rejection_reason"] = (
                "Supplier is unavailable"
            )

            continue

        # Hard rule: supplier must arrive before stockout
        if (
            supplier["delivery_hours"]
            > product["hours_remaining"]
        ):
            supplier["eligible"] = False

            supplier["rejection_reason"] = (
                "Cannot deliver before "
                "predicted stockout"
            )

            continue

        eligible_suppliers.append(
            supplier
        )

    # No supplier passed the safety rules
    if not eligible_suppliers:
        return None, suppliers

    cheapest_price = min(
        supplier["unit_price"]
        for supplier in eligible_suppliers
    )

    fastest_delivery = min(
        supplier["delivery_hours"]
        for supplier in eligible_suppliers
    )

    for supplier in eligible_suppliers:

        price_score = (
            cheapest_price
            / supplier["unit_price"]
        )

        delivery_score = (
            fastest_delivery
            / supplier["delivery_hours"]
        )

        reliability_score = (
            supplier["reliability"]
            / 100
        )

        supplier["score"] = (
            price_score * 0.40
            + delivery_score * 0.35
            + reliability_score * 0.25
        )

    selected_supplier = max(
        eligible_suppliers,
        key=lambda supplier: supplier["score"]
    )

    return (
        selected_supplier,
        suppliers
    )


# --------------------------------------------------
# Order quantity calculation
# --------------------------------------------------

def calculate_order_quantity(product):
    """
    Calculates enough stock to cover the target
    stock period plus the safety stock.
    """

    target_stock = (
        product["daily_usage"]
        * TARGET_STOCK_DAYS
        + product["safety_stock"]
    )

    quantity_needed = (
        target_stock
        - product["current_stock"]
    )

    return max(
        1,
        math.ceil(quantity_needed)
    )


# --------------------------------------------------
# Purchase order creation
# --------------------------------------------------

def create_purchase_order(
    product,
    supplier
):
    """
    Creates a purchase order in SQLite.

    New purchase orders start as Pending Approval.
    """

    quantity = (
        calculate_order_quantity(
            product
        )
    )

    unit_price = supplier[
        "unit_price"
    ]

    total_price = (
        quantity
        * unit_price
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO purchase_orders (
            created_at,
            inventory_id,
            supplier_id,
            quantity,
            unit_price,
            total_price,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(
            timespec="seconds"
        ),
        product["id"],
        supplier["supplier_id"],
        quantity,
        unit_price,
        total_price,
        "Pending Approval"
    ))

    purchase_order_id = (
        cursor.lastrowid
    )

    connection.commit()
    connection.close()

    return (
        purchase_order_id,
        quantity,
        total_price
    )


# --------------------------------------------------
# Decision logging
# --------------------------------------------------

def write_decision(
    message,
    decision_type="Procurement Decision"
):
    """
    Saves an important Betsy decision to the
    audit/decision log.

    decision_type defaults to Procurement Decision,
    so existing code continues to work.

    The AI layer can use:
    write_decision(message, "AI Recommendation")
    """

    connection = get_connection()

    connection.execute("""
        INSERT INTO decisions (
            created_at,
            decision_type,
            message
        )
        VALUES (?, ?, ?)
    """, (
        datetime.now().isoformat(
            timespec="seconds"
        ),
        decision_type,
        message
    ))

    connection.commit()
    connection.close()


# --------------------------------------------------
# Legacy/manual procurement test
# --------------------------------------------------

def run_procurement_check():
    """
    Manual procurement test.

    The real autonomous application now uses
    LangGraph through agent.py and runner.py,
    but this function remains useful for testing.
    """

    product = detect_stockout()

    if product is None:
        message = (
            "No new procurement action is required. "
            "Inventory is safe or an active purchase "
            "order already exists."
        )

        print(
            f"\n{message}"
        )

        return message

    print(
        "\n--- STOCKOUT RISK DETECTED ---"
    )

    print(
        f"Product: {product['name']}"
    )

    print(
        f"Current stock: "
        f"{product['current_stock']}"
    )

    print(
        f"Daily usage: "
        f"{product['daily_usage']}"
    )

    print(
        f"Estimated stock remaining: "
        f"{product['days_remaining']:.2f} days"
    )

    print(
        f"Approximately "
        f"{product['hours_remaining']:.1f} hours"
    )

    selected_supplier, suppliers = (
        evaluate_suppliers(
            product
        )
    )

    print(
        "\n--- SUPPLIER EVALUATION ---"
    )

    for supplier in suppliers:

        print(
            f"\n{supplier['name']}"
        )

        print(
            f"Price: EUR "
            f"{supplier['unit_price']}"
        )

        print(
            f"Delivery: "
            f"{supplier['delivery_hours']} hours"
        )

        print(
            f"Reliability: "
            f"{supplier['reliability']}%"
        )

        if supplier["eligible"]:

            print(
                "Status: ELIGIBLE"
            )

            print(
                f"Score: "
                f"{supplier['score']:.3f}"
            )

        else:

            print(
                "Status: REJECTED"
            )

            print(
                f"Reason: "
                f"{supplier['rejection_reason']}"
            )

    if selected_supplier is None:
        message = (
            f"URGENT: {product['name']} is "
            f"predicted to run out in "
            f"{product['days_remaining']:.2f} days, "
            f"but no supplier can deliver in time."
        )

        print(
            f"\n{message}"
        )

        write_decision(
            message
        )

        return message

    purchase_order_id, quantity, total_price = (
        create_purchase_order(
            product,
            selected_supplier
        )
    )

    message = (
        f"PO-{purchase_order_id:04d} created for "
        f"{product['name']}. "
        f"Selected supplier: "
        f"{selected_supplier['name']}. "
        f"Predicted stockout in "
        f"{product['days_remaining']:.2f} days. "
        f"Quantity: {quantity}. "
        f"Total value: EUR {total_price:.2f}. "
        f"Status: Pending Approval."
    )

    write_decision(
        message
    )

    print(
        "\n--- BETSY DECISION ---"
    )

    print(
        f"Selected supplier: "
        f"{selected_supplier['name']}"
    )

    print(
        f"Order quantity: "
        f"{quantity}"
    )

    print(
        f"Unit price: EUR "
        f"{selected_supplier['unit_price']}"
    )

    print(
        f"Total order value: "
        f"EUR {total_price:.2f}"
    )

    print(
        f"Purchase order: "
        f"PO-{purchase_order_id:04d}"
    )

    print(
        "Status: Pending Approval"
    )

    print(
        "\nDecision saved to "
        "Betsy's decision log."
    )

    return message


# --------------------------------------------------
# Direct test execution
# --------------------------------------------------

if __name__ == "__main__":
    run_procurement_check()