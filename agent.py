from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from database import get_connection

from procurement import (
    detect_stockout,
    evaluate_suppliers,
    create_purchase_order,
    write_decision
)


class BetsyState(TypedDict, total=False):
    product: dict | None
    suppliers: list
    selected_supplier: dict | None

    purchase_order_id: int
    quantity: int
    total_price: float

    status: str
    message: str


# --------------------------------------------------
# Detect
# --------------------------------------------------

def check_inventory(state: BetsyState):
    product = detect_stockout()

    if product is None:
        return {
            "product": None,
            "status": "NO_ACTION",
            "message": (
                "No new procurement action required. "
                "Inventory is safe or an active order already exists."
            )
        }

    return {
        "product": product,
        "status": "STOCKOUT_RISK"
    }


def route_after_inventory_check(state: BetsyState):

    if state.get("product") is None:
        return "finish"

    return "evaluate_suppliers"


# --------------------------------------------------
# Analyse + Decide
# --------------------------------------------------

def supplier_evaluation(state: BetsyState):
    product = state["product"]

    selected_supplier, suppliers = evaluate_suppliers(
        product
    )

    if selected_supplier is None:

        message = (
            f"URGENT: {product['name']} is predicted "
            f"to run out in "
            f"{product['days_remaining']:.2f} days, "
            f"but no supplier can deliver in time."
        )

        write_decision(message)

        return {
            "suppliers": suppliers,
            "selected_supplier": None,
            "status": "ESCALATION_REQUIRED",
            "message": message
        }

    return {
        "suppliers": suppliers,
        "selected_supplier": selected_supplier,
        "status": "SUPPLIER_SELECTED"
    }


def route_after_supplier_evaluation(state: BetsyState):

    if state.get("selected_supplier") is None:
        return "finish"

    return "create_purchase_order"


# --------------------------------------------------
# Act
# --------------------------------------------------

def create_order(state: BetsyState):
    product = state["product"]
    supplier = state["selected_supplier"]

    purchase_order_id, quantity, total_price = (
        create_purchase_order(
            product,
            supplier
        )
    )

    return {
        "purchase_order_id": purchase_order_id,
        "quantity": quantity,
        "total_price": total_price,
        "status": "PO_CREATED"
    }


# --------------------------------------------------
# Verify
# --------------------------------------------------

def verify_order(state: BetsyState):
    purchase_order_id = state["purchase_order_id"]

    connection = get_connection()

    order = connection.execute("""
        SELECT
            po.id,
            po.status,
            po.quantity,
            po.total_price,
            i.name AS product,
            s.name AS supplier
        FROM purchase_orders po

        JOIN inventory i
            ON i.id = po.inventory_id

        JOIN suppliers s
            ON s.id = po.supplier_id

        WHERE po.id = ?
    """, (
        purchase_order_id,
    )).fetchone()

    connection.close()

    if order is None:

        message = (
            f"ERROR: PO-{purchase_order_id:04d} "
            f"could not be verified in the database."
        )

        write_decision(message)

        return {
            "status": "VERIFICATION_FAILED",
            "message": message
        }

    message = (
        f"PO-{purchase_order_id:04d} created and verified. "
        f"Product: {order['product']}. "
        f"Supplier: {order['supplier']}. "
        f"Quantity: {order['quantity']}. "
        f"Total value: EUR {order['total_price']:.2f}. "
        f"Status: {order['status']}."
    )

    write_decision(message)

    return {
        "status": "PENDING_APPROVAL",
        "message": message
    }


# --------------------------------------------------
# Build LangGraph
# --------------------------------------------------

def build_betsy_graph():

    builder = StateGraph(BetsyState)

    builder.add_node(
        "check_inventory",
        check_inventory
    )

    builder.add_node(
        "evaluate_suppliers",
        supplier_evaluation
    )

    builder.add_node(
        "create_purchase_order",
        create_order
    )

    builder.add_node(
        "verify_order",
        verify_order
    )

    builder.add_edge(
        START,
        "check_inventory"
    )

    builder.add_conditional_edges(
        "check_inventory",
        route_after_inventory_check,
        {
            "evaluate_suppliers": "evaluate_suppliers",
            "finish": END
        }
    )

    builder.add_conditional_edges(
        "evaluate_suppliers",
        route_after_supplier_evaluation,
        {
            "create_purchase_order": "create_purchase_order",
            "finish": END
        }
    )

    builder.add_edge(
        "create_purchase_order",
        "verify_order"
    )

    builder.add_edge(
        "verify_order",
        END
    )

    return builder.compile()


betsy_graph = build_betsy_graph()


def run_betsy():
    return betsy_graph.invoke({})


if __name__ == "__main__":
    result = run_betsy()

    print("\n--- BETSY LANGGRAPH RESULT ---")

    print(
        f"Status: {result.get('status')}"
    )

    print(
        f"Message: {result.get('message')}"
    )




