import streamlit as st

from database import (
    initialize_database,
    get_inventory,
    update_stock,
    get_purchase_orders,
    update_po_status,
    get_decisions,
    get_latest_ai_recommendation,
    reset_demo
)

from procurement import (
    write_decision
)

from agent import (
    run_betsy
)


# --------------------------------------------------
# Application setup
# --------------------------------------------------

initialize_database()

st.set_page_config(
    page_title="Betsy Procurement Agent",
    layout="wide"
)


# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("Betsy")

st.subheader(
    "Autonomous Procurement Agent"
)

st.success(
    "Agent Status: ACTIVE"
)


# --------------------------------------------------
# Flash messages
# --------------------------------------------------

if "flash_message" in st.session_state:

    st.info(
        st.session_state.pop(
            "flash_message"
        )
    )


# --------------------------------------------------
# Load current inventory
# --------------------------------------------------

inventory = get_inventory()


# --------------------------------------------------
# Live dashboard overview
# --------------------------------------------------

@st.fragment(run_every="5s")
def live_overview():

    inventory_data = get_inventory()

    purchase_orders = (
        get_purchase_orders()
    )

    pending_orders = [
        po
        for po in purchase_orders
        if po["status"]
        == "Pending Approval"
    ]

    st.divider()

    st.header("Overview")

    col1, col2, col3 = (
        st.columns(3)
    )

    col1.metric(
        "Inventory Items",
        len(inventory_data)
    )

    col2.metric(
        "Purchase Orders",
        len(purchase_orders)
    )

    col3.metric(
        "Pending Approvals",
        len(pending_orders)
    )


live_overview()


# --------------------------------------------------
# Inventory
# --------------------------------------------------

st.divider()

st.header("Inventory")


for item in inventory:

    if item["daily_usage"] > 0:

        days_remaining = (
            item["current_stock"]
            / item["daily_usage"]
        )

    else:

        days_remaining = 0


    st.subheader(
        item["name"]
    )


    col1, col2, col3, col4 = (
        st.columns(4)
    )


    col1.metric(
        "Current Stock",
        f"{item['current_stock']} units"
    )


    col2.metric(
        "Daily Usage",
        f"{item['daily_usage']:.0f} units"
    )


    col3.metric(
        "Days Remaining",
        f"{days_remaining:.2f}"
    )


    col4.metric(
        "Reorder Threshold",
        (
            f"{item['reorder_threshold_days']:.0f} "
            f"days"
        )
    )


    if (
        days_remaining
        <= item["reorder_threshold_days"]
    ):

        st.warning(
            "Stockout risk detected: "
            "this item is inside its "
            "reorder threshold."
        )

    else:

        st.success(
            "Inventory level is currently safe."
        )


    new_stock = st.number_input(
        "Simulate stock level",

        min_value=0,

        value=item["current_stock"],

        step=1,

        key=f"stock_{item['id']}"
    )


    if st.button(
        "Update Inventory",

        key=f"update_stock_{item['id']}"
    ):

        update_stock(
            item["id"],
            new_stock
        )

        st.session_state[
            "flash_message"
        ] = (
            f"{item['name']} inventory updated "
            f"to {new_stock} units."
        )

        st.rerun()


# --------------------------------------------------
# AI Reasoning
# --------------------------------------------------

@st.fragment(run_every="5s")
def live_ai_reasoning():

    st.divider()

    st.header("AI Reasoning")

    recommendation = (
        get_latest_ai_recommendation()
    )


    # ----------------------------------------------
    # No AI decision yet
    # ----------------------------------------------

    if recommendation is None:

        st.info(
            "No AI procurement recommendation "
            "has been generated yet."
        )

        st.caption(
            "When a procurement decision is required, "
            "Betsy uses a locally running Ollama LLM "
            "to analyse the eligible suppliers."
        )

        return


    # ----------------------------------------------
    # AI recommendation exists
    # ----------------------------------------------

    st.success(
        "Ollama AI recommendation generated"
    )


    col1, col2, col3, col4 = (
        st.columns(4)
    )


    col1.metric(
        "AI Model",
        recommendation[
            "model_name"
        ]
    )


    col2.metric(
        "Recommended Supplier",
        recommendation[
            "supplier"
        ]
    )


    col3.metric(
        "Confidence",
        (
            f"{recommendation['confidence'] * 100:.0f}%"
        )
    )


    col4.metric(
        "Risk Level",
        recommendation[
            "risk_level"
        ].title()
    )


    # ----------------------------------------------
    # AI explanation
    # ----------------------------------------------

    st.subheader(
        "AI Explanation"
    )

    st.write(
        recommendation[
            "reasoning"
        ]
    )


    # ----------------------------------------------
    # Safety validation
    # ----------------------------------------------

    st.subheader(
        "Safety Validation"
    )


    if (
        recommendation[
            "validation_status"
        ]
        ==
        "Validated by deterministic policy"
    ):

        st.success(
            "AI recommendation passed "
            "Betsy's deterministic safety rules."
        )

    else:

        st.warning(
            recommendation[
                "validation_status"
            ]
        )


    st.caption(
        f"Generated: "
        f"{recommendation['created_at']}"
    )


live_ai_reasoning()


# --------------------------------------------------
# Betsy controls
# --------------------------------------------------

st.divider()

st.header("Betsy Agent")


st.write(
    "Betsy automatically monitors inventory in the "
    "background. This button can also manually run "
    "one LangGraph procurement cycle for testing."
)


if st.button(
    "Run Betsy Procurement Cycle",
    type="primary"
):

    # IMPORTANT:
    # This now runs the real LangGraph workflow,
    # including Ollama AI reasoning.
    result = run_betsy()

    st.session_state[
        "flash_message"
    ] = result.get(
        "message",
        "Betsy procurement cycle completed."
    )

    st.rerun()


# --------------------------------------------------
# Live purchase orders
# --------------------------------------------------

@st.fragment(run_every="5s")
def live_purchase_orders():

    st.divider()

    st.header(
        "Purchase Orders"
    )

    purchase_orders = (
        get_purchase_orders()
    )


    if not purchase_orders:

        st.info(
            "No purchase orders have "
            "been created yet."
        )

        return


    for po in purchase_orders:

        st.subheader(
            f"PO-{po['id']:04d}"
        )


        col1, col2, col3, col4 = (
            st.columns(4)
        )


        col1.write(
            f"**Product**\n\n"
            f"{po['product']}"
        )


        col2.write(
            f"**Supplier**\n\n"
            f"{po['supplier']}"
        )


        col3.write(
            f"**Quantity**\n\n"
            f"{po['quantity']}"
        )


        col4.write(
            f"**Total**\n\n"
            f"EUR {po['total_price']:,.2f}"
        )


        st.write(
            f"**Status:** "
            f"{po['status']}"
        )


        st.write(
            f"Created: "
            f"{po['created_at']}"
        )


        # ------------------------------------------
        # Human approval
        # ------------------------------------------

        if (
            po["status"]
            == "Pending Approval"
        ):

            approve_col, reject_col = (
                st.columns(2)
            )


            with approve_col:

                if st.button(
                    "Approve Purchase Order",

                    key=(
                        f"approve_{po['id']}"
                    )
                ):

                    update_po_status(
                        po["id"],
                        "Approved"
                    )

                    write_decision(
                        (
                            f"PO-{po['id']:04d} "
                            f"was approved by "
                            f"the human operator."
                        )
                    )

                    st.session_state[
                        "flash_message"
                    ] = (
                        f"PO-{po['id']:04d} "
                        f"approved."
                    )

                    st.rerun()


            with reject_col:

                if st.button(
                    "Reject Purchase Order",

                    key=(
                        f"reject_{po['id']}"
                    )
                ):

                    update_po_status(
                        po["id"],
                        "Rejected"
                    )

                    write_decision(
                        (
                            f"PO-{po['id']:04d} "
                            f"was rejected by "
                            f"the human operator."
                        )
                    )

                    st.session_state[
                        "flash_message"
                    ] = (
                        f"PO-{po['id']:04d} "
                        f"rejected."
                    )

                    st.rerun()


        st.divider()


live_purchase_orders()


# --------------------------------------------------
# Live decision log
# --------------------------------------------------

@st.fragment(run_every="5s")
def live_decision_log():

    st.header(
        "Decision Log"
    )

    decisions = (
        get_decisions()
    )


    if not decisions:

        st.info(
            "Betsy has not recorded "
            "any decisions yet."
        )

        return


    for decision in decisions:

        with st.expander(
            (
                f"{decision['created_at']} - "
                f"{decision['decision_type']}"
            )
        ):

            st.write(
                decision[
                    "message"
                ]
            )


live_decision_log()


# --------------------------------------------------
# Demo controls
# --------------------------------------------------

st.divider()

st.header(
    "Demo Controls"
)


st.warning(
    "Reset Demo deletes purchase orders, "
    "decision logs and AI recommendations, "
    "and restores Industrial Bearings "
    "to 400 units."
)


if st.button(
    "Reset Demo"
):

    reset_demo()

    st.session_state[
        "flash_message"
    ] = (
        "Demo reset successfully."
    )

    st.rerun()