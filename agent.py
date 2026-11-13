from typing_extensions import TypedDict

from langgraph.graph import (
    StateGraph,
    START,
    END
)

from database import (
    get_connection,
    save_ai_recommendation
)

from procurement import (
    detect_stockout,
    evaluate_suppliers,
    create_purchase_order,
    write_decision
)

from ai_reasoning import (
    recommend_supplier,
    MODEL_NAME
)


# --------------------------------------------------
# LangGraph state
# --------------------------------------------------

class BetsyState(TypedDict, total=False):

    # Procurement information
    product: dict | None
    suppliers: list

    # Deterministic fallback supplier
    fallback_supplier: dict | None

    # Final supplier chosen after AI validation
    selected_supplier: dict | None

    # AI reasoning information
    ai_supplier: str
    ai_reasoning: str
    ai_confidence: float
    ai_risk_level: str
    ai_validation_status: str

    # Purchase order information
    purchase_order_id: int
    quantity: int
    total_price: float

    # Workflow information
    status: str
    message: str


# --------------------------------------------------
# DETECT
# --------------------------------------------------

def check_inventory(
    state: BetsyState
):
    """
    Detect whether inventory is approaching
    a stockout threshold.
    """

    product = detect_stockout()

    if product is None:

        return {
            "product": None,

            "status": "NO_ACTION",

            "message": (
                "No new procurement action required. "
                "Inventory is safe or an active "
                "purchase order already exists."
            )
        }

    return {
        "product": product,
        "status": "STOCKOUT_RISK"
    }


def route_after_inventory_check(
    state: BetsyState
):
    """
    Decide whether Betsy should continue
    into supplier analysis.
    """

    if state.get("product") is None:
        return "finish"

    return "evaluate_suppliers"


# --------------------------------------------------
# ANALYSE
# Deterministic supplier filtering
# --------------------------------------------------

def supplier_evaluation(
    state: BetsyState
):
    """
    Apply Betsy's deterministic supplier rules.

    Python determines which suppliers are safe.

    The highest-scoring deterministic supplier is
    kept as a fallback if the LLM fails.
    """

    product = state["product"]

    fallback_supplier, suppliers = (
        evaluate_suppliers(
            product
        )
    )

    # No supplier passed the hard rules.
    if fallback_supplier is None:

        message = (
            f"URGENT: {product['name']} is "
            f"predicted to run out in "
            f"{product['days_remaining']:.2f} days, "
            f"but no supplier can deliver in time."
        )

        write_decision(
            message
        )

        return {
            "suppliers": suppliers,

            "fallback_supplier": None,

            "selected_supplier": None,

            "status": "ESCALATION_REQUIRED",

            "message": message
        }

    return {
        "suppliers": suppliers,

        "fallback_supplier":
            fallback_supplier,

        "status":
            "SUPPLIERS_FILTERED",

        "message": (
            "Eligible suppliers passed "
            "deterministic safety filtering."
        )
    }


def route_after_supplier_evaluation(
    state: BetsyState
):
    """
    Only send safe supplier options
    to the AI reasoning node.
    """

    if state.get(
        "fallback_supplier"
    ) is None:

        return "finish"

    return "ai_supplier_reasoning"


# --------------------------------------------------
# AI REASONING
# Ollama
# --------------------------------------------------

def ai_supplier_reasoning(
    state: BetsyState
):
    """
    Uses Ollama to reason about eligible suppliers.

    The LLM recommendation is always checked against
    the deterministic eligible supplier list before
    Betsy is allowed to use it.
    """

    product = state["product"]

    suppliers = state["suppliers"]

    fallback_supplier = (
        state["fallback_supplier"]
    )

    # Only suppliers already approved by
    # deterministic business rules.
    eligible_suppliers = {
        supplier["name"]: supplier
        for supplier in suppliers
        if supplier.get("eligible") is True
    }

    try:

        # ------------------------------------------
        # Ask Ollama for a recommendation
        # ------------------------------------------

        recommendation = (
            recommend_supplier(
                product,
                suppliers
            )
        )

        if recommendation is None:
            raise ValueError(
                "Ollama returned no recommendation."
            )

        # ------------------------------------------
        # Validate the LLM recommendation
        # ------------------------------------------

        recommended_supplier = (
            eligible_suppliers.get(
                recommendation.supplier_name
            )
        )

        # AI recommended something that Python
        # did not mark as eligible.
        if recommended_supplier is None:

            selected_supplier = (
                fallback_supplier
            )

            validation_status = (
                "Fallback used - "
                "AI recommendation failed "
                "deterministic policy validation"
            )

            reasoning = (
                "The AI recommendation did not match "
                "a supplier that passed Betsy's "
                "deterministic safety rules. "
                "Betsy therefore used the deterministic "
                f"fallback supplier "
                f"{fallback_supplier['name']}."
            )

            confidence = 0.0
            risk_level = "high"

        else:

            # AI recommendation is safe.
            selected_supplier = (
                recommended_supplier
            )

            validation_status = (
                "Validated by deterministic policy"
            )

            reasoning = (
                recommendation.reasoning
            )

            confidence = (
                recommendation.confidence
            )

            risk_level = (
                recommendation.risk_level
            )

    except Exception as error:

        # ------------------------------------------
        # Safe deterministic fallback
        # ------------------------------------------

        selected_supplier = (
            fallback_supplier
        )

        validation_status = (
            "Deterministic fallback - "
            "AI unavailable"
        )

        reasoning = (
            "The local Ollama model was unavailable "
            "or returned invalid output. "
            "Betsy continued safely using the "
            "deterministic supplier scoring system. "
            f"Fallback supplier: "
            f"{fallback_supplier['name']}."
        )

        confidence = 0.0
        risk_level = "high"

        print(
            f"\nOLLAMA AI ERROR: {error}"
        )

    # ----------------------------------------------
    # Save AI evidence
    # ----------------------------------------------

    save_ai_recommendation(
        model_name=MODEL_NAME,

        product=product["name"],

        supplier=(
            selected_supplier["name"]
        ),

        confidence=confidence,

        risk_level=risk_level,

        reasoning=reasoning,

        validation_status=(
            validation_status
        )
    )

    # ----------------------------------------------
    # Save AI reasoning in general decision log
    # ----------------------------------------------

    ai_log_message = (
        f"Ollama model {MODEL_NAME} recommended "
        f"{selected_supplier['name']}. "
        f"Confidence: {confidence:.2f}. "
        f"Risk level: {risk_level}. "
        f"Validation: {validation_status}. "
        f"Reasoning: {reasoning}"
    )

    write_decision(
        ai_log_message,
        "AI Recommendation"
    )

    return {
        "selected_supplier":
            selected_supplier,

        "ai_supplier":
            selected_supplier["name"],

        "ai_reasoning":
            reasoning,

        "ai_confidence":
            confidence,

        "ai_risk_level":
            risk_level,

        "ai_validation_status":
            validation_status,

        "status":
            "AI_RECOMMENDATION_VALIDATED",

        "message": (
            f"AI recommended "
            f"{selected_supplier['name']} "
            f"and the recommendation passed "
            f"Betsy's validation process."
        )
    }


# --------------------------------------------------
# ACT
# --------------------------------------------------

def create_order(
    state: BetsyState
):
    """
    Create a purchase order using the supplier
    chosen by the AI + deterministic validation layer.
    """

    product = state["product"]

    supplier = state[
        "selected_supplier"
    ]

    purchase_order_id, quantity, total_price = (
        create_purchase_order(
            product,
            supplier
        )
    )

    return {
        "purchase_order_id":
            purchase_order_id,

        "quantity":
            quantity,

        "total_price":
            total_price,

        "status":
            "PO_CREATED",

        "message": (
            f"PO-{purchase_order_id:04d} created "
            f"for {supplier['name']}."
        )
    }


# --------------------------------------------------
# VERIFY
# --------------------------------------------------

def verify_order(
    state: BetsyState
):
    """
    Verify that the purchase order really exists
    in SQLite after Betsy creates it.
    """

    purchase_order_id = state[
        "purchase_order_id"
    ]

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

    # Verification failed
    if order is None:

        message = (
            f"ERROR: PO-{purchase_order_id:04d} "
            f"could not be verified in the database."
        )

        write_decision(
            message
        )

        return {
            "status":
                "VERIFICATION_FAILED",

            "message":
                message
        }

    # Verification succeeded
    message = (
        f"PO-{purchase_order_id:04d} "
        f"created and verified. "
        f"Product: {order['product']}. "
        f"Supplier: {order['supplier']}. "
        f"Quantity: {order['quantity']}. "
        f"Total value: EUR "
        f"{order['total_price']:.2f}. "
        f"Status: {order['status']}."
    )

    write_decision(
        message
    )

    return {
        "status":
            "PENDING_APPROVAL",

        "message":
            message
    }


# --------------------------------------------------
# BUILD LANGGRAPH
# --------------------------------------------------

def build_betsy_graph():

    builder = StateGraph(
        BetsyState
    )

    # ----------------------------------------------
    # Nodes
    # ----------------------------------------------

    builder.add_node(
        "check_inventory",
        check_inventory
    )

    builder.add_node(
        "evaluate_suppliers",
        supplier_evaluation
    )

    builder.add_node(
        "ai_supplier_reasoning",
        ai_supplier_reasoning
    )

    builder.add_node(
        "create_purchase_order",
        create_order
    )

    builder.add_node(
        "verify_order",
        verify_order
    )

    # ----------------------------------------------
    # Start
    # ----------------------------------------------

    builder.add_edge(
        START,
        "check_inventory"
    )

    # ----------------------------------------------
    # Inventory routing
    # ----------------------------------------------

    builder.add_conditional_edges(
        "check_inventory",

        route_after_inventory_check,

        {
            "evaluate_suppliers":
                "evaluate_suppliers",

            "finish":
                END
        }
    )

    # ----------------------------------------------
    # Supplier routing
    # ----------------------------------------------

    builder.add_conditional_edges(
        "evaluate_suppliers",

        route_after_supplier_evaluation,

        {
            "ai_supplier_reasoning":
                "ai_supplier_reasoning",

            "finish":
                END
        }
    )

    # ----------------------------------------------
    # AI -> Create PO
    # ----------------------------------------------

    builder.add_edge(
        "ai_supplier_reasoning",
        "create_purchase_order"
    )

    # ----------------------------------------------
    # Create PO -> Verify
    # ----------------------------------------------

    builder.add_edge(
        "create_purchase_order",
        "verify_order"
    )

    # ----------------------------------------------
    # Verify -> Finish
    # ----------------------------------------------

    builder.add_edge(
        "verify_order",
        END
    )

    return builder.compile()


# --------------------------------------------------
# Compile Betsy
# --------------------------------------------------

betsy_graph = build_betsy_graph()


# --------------------------------------------------
# Public function used by app.py and runner.py
# --------------------------------------------------

def run_betsy():
    """
    Run one complete Betsy LangGraph workflow.
    """

    return betsy_graph.invoke({})


# --------------------------------------------------
# Direct test execution
# --------------------------------------------------

if __name__ == "__main__":

    result = run_betsy()

    print(
        "\n--- BETSY LANGGRAPH RESULT ---"
    )

    print(
        f"Status: "
        f"{result.get('status')}"
    )

    print(
        f"Message: "
        f"{result.get('message')}"
    )

    if result.get(
        "ai_supplier"
    ):

        print(
            "\n--- AI REASONING ---"
        )

        print(
            f"Model: "
            f"{MODEL_NAME}"
        )

        print(
            f"Recommended supplier: "
            f"{result.get('ai_supplier')}"
        )

        print(
            f"Confidence: "
            f"{result.get('ai_confidence', 0):.2f}"
        )

        print(
            f"Risk level: "
            f"{result.get('ai_risk_level')}"
        )

        print(
            f"Validation: "
            f"{result.get('ai_validation_status')}"
        )

        print(
            "\nReasoning:"
        )

        print(
            result.get(
                "ai_reasoning"
            )
        )