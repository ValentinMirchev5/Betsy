import math

from database import get_connection


TARGET_STOCK_DAYS = 4


def detect_stockout():
    """
    Checks inventory and returns the first product
    that is inside its reorder threshold.
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

        if daily_usage <= 0:
            continue

        days_remaining = current_stock / daily_usage

        if days_remaining <= product["reorder_threshold_days"]:
            product["days_remaining"] = days_remaining
            product["hours_remaining"] = days_remaining * 24

            connection.close()

            return product

    connection.close()

    return None


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
    """, (product_id,)).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def evaluate_suppliers(product):
    """
    First removes suppliers that cannot safely fulfil
    the order.

    Then scores the remaining suppliers using:
    - 40% price
    - 35% delivery speed
    - 25% reliability
    """

    suppliers = get_supplier_options(product["id"])

    eligible_suppliers = []

    for supplier in suppliers:
        supplier["eligible"] = True
        supplier["rejection_reason"] = None

        if supplier["available"] == 0:
            supplier["eligible"] = False
            supplier["rejection_reason"] = "Supplier is unavailable"
            continue

        if supplier["delivery_hours"] > product["hours_remaining"]:
            supplier["eligible"] = False
            supplier["rejection_reason"] = (
                "Cannot deliver before predicted stockout"
            )
            continue

        eligible_suppliers.append(supplier)

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
            cheapest_price / supplier["unit_price"]
        )

        delivery_score = (
            fastest_delivery / supplier["delivery_hours"]
        )

        reliability_score = (
            supplier["reliability"] / 100
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

    return selected_supplier, suppliers


def calculate_order_quantity(product):
    """
    Calculates enough stock to cover the target period
    plus the safety stock.
    """

    target_stock = (
        product["daily_usage"] * TARGET_STOCK_DAYS
        + product["safety_stock"]
    )

    quantity_needed = (
        target_stock - product["current_stock"]
    )

    return max(
        1,
        math.ceil(quantity_needed)
    )


def run_procurement_check():
    """
    Temporary test function for Sprint 1.
    """

    product = detect_stockout()

    if product is None:
        print("\nNo stockout risk detected.")
        print("No procurement action is required.")
        return

    print("\n--- STOCKOUT RISK DETECTED ---")

    print(f"Product: {product['name']}")
    print(f"Current stock: {product['current_stock']}")
    print(f"Daily usage: {product['daily_usage']}")

    print(
        f"Estimated stock remaining: "
        f"{product['days_remaining']:.2f} days"
    )

    print(
        f"Approximately "
        f"{product['hours_remaining']:.1f} hours"
    )

    selected_supplier, suppliers = evaluate_suppliers(
        product
    )

    print("\n--- SUPPLIER EVALUATION ---")

    for supplier in suppliers:

        print(
            f"\n{supplier['name']}"
        )

        print(
            f"Price: EUR {supplier['unit_price']}"
        )

        print(
            f"Delivery: {supplier['delivery_hours']} hours"
        )

        print(
            f"Reliability: {supplier['reliability']}%"
        )

        if supplier["eligible"]:

            print("Status: ELIGIBLE")

            print(
                f"Score: {supplier['score']:.3f}"
            )

        else:

            print("Status: REJECTED")

            print(
                f"Reason: "
                f"{supplier['rejection_reason']}"
            )

    if selected_supplier is None:

        print(
            "\nURGENT: No supplier can deliver "
            "before the predicted stockout."
        )

        return

    quantity = calculate_order_quantity(product)

    total_price = (
        quantity * selected_supplier["unit_price"]
    )

    print("\n--- BETSY DECISION ---")

    print(
        f"Selected supplier: "
        f"{selected_supplier['name']}"
    )

    print(
        f"Order quantity: {quantity}"
    )

    print(
        f"Unit price: "
        f"EUR {selected_supplier['unit_price']}"
    )

    print(
        f"Total order value: "
        f"EUR {total_price:.2f}"
    )


if __name__ == "__main__":
    run_procurement_check()
