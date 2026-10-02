import streamlit as st

from database import (
    initialize_database,
    get_inventory,
    update_stock,
    get_purchase_orders,
    update_po_status,
    get_decisions,
    reset_demo
)

from procurement import (
    run_procurement_check,
    write_decision
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
st.subheader("Autonomous Procurement Agent")

st.success("Agent Status: ACTIVE")


# Show messages after actions / reruns.
if "flash_message" in st.session_state:
    st.info(st.session_state.pop("flash_message"))


# --------------------------------------------------
# Load current data
# --------------------------------------------------

inventory = get_inventory()
purchase_orders = get_purchase_orders()

pending_orders = [
    po
    for po in purchase_orders
    if po["status"] == "Pending Approval"
]


# --------------------------------------------------
# Dashboard metrics
# --------------------------------------------------

st.divider()

st.header("Overview")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Inventory Items",
    len(inventory)
)

col2.metric(
    "Purchase Orders",
    len(purchase_orders)
)

col3.metric(
    "Pending Approvals",
    len(pending_orders)
)


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

    st.subheader(item["name"])

    col1, col2, col3, col4 = st.columns(4)

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
        f"{item['reorder_threshold_days']:.0f} days"
    )

    if days_remaining <= item["reorder_threshold_days"]:
        st.warning(
            "Stockout risk detected: "
            "this item is inside its reorder threshold."
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

        st.session_state["flash_message"] = (
            f"{item['name']} inventory updated "
            f"to {new_stock} units."
        )

        st.rerun()


# --------------------------------------------------
# Betsy controls
# --------------------------------------------------

st.divider()

st.header("Betsy Agent")

st.write(
    "Run one procurement monitoring cycle. "
    "Betsy will check inventory, detect stockout risk, "
    "evaluate suppliers and create a purchase order "
    "when necessary."
)

if st.button(
    "Run Betsy Procurement Cycle",
    type="primary"
):
    result = run_procurement_check()

    st.session_state["flash_message"] = result

    st.rerun()


# --------------------------------------------------
# Purchase orders
# --------------------------------------------------

st.divider()

st.header("Purchase Orders")

purchase_orders = get_purchase_orders()


if not purchase_orders:

    st.info(
        "No purchase orders have been created yet."
    )

else:

    for po in purchase_orders:

        st.subheader(
            f"PO-{po['id']:04d}"
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.write(
            f"**Product**\n\n{po['product']}"
        )

        col2.write(
            f"**Supplier**\n\n{po['supplier']}"
        )

        col3.write(
            f"**Quantity**\n\n{po['quantity']}"
        )

        col4.write(
            f"**Total**\n\nâ‚¬{po['total_price']:,.2f}"
        )

        st.write(
            f"**Status:** {po['status']}"
        )

        st.write(
            f"Created: {po['created_at']}"
        )

        if po["status"] == "Pending Approval":

            approve_col, reject_col = st.columns(2)

            with approve_col:

                if st.button(
                    "Approve Purchase Order",
                    key=f"approve_{po['id']}"
                ):

                    update_po_status(
                        po["id"],
                        "Approved"
                    )

                    write_decision(
                        f"PO-{po['id']:04d} was approved "
                        f"by the human operator."
                    )

                    st.session_state["flash_message"] = (
                        f"PO-{po['id']:04d} approved."
                    )

                    st.rerun()

            with reject_col:

                if st.button(
                    "Reject Purchase Order",
                    key=f"reject_{po['id']}"
                ):

                    update_po_status(
                        po["id"],
                        "Rejected"
                    )

                    write_decision(
                        f"PO-{po['id']:04d} was rejected "
                        f"by the human operator."
                    )

                    st.session_state["flash_message"] = (
                        f"PO-{po['id']:04d} rejected."
                    )

                    st.rerun()

        st.divider()


# --------------------------------------------------
# Decision log
# --------------------------------------------------

st.header("Decision Log")

decisions = get_decisions()


if not decisions:

    st.info(
        "Betsy has not recorded any decisions yet."
    )

else:

    for decision in decisions:

        with st.expander(
            f"{decision['created_at']} - "
            f"{decision['decision_type']}"
        ):

            st.write(
                decision["message"]
            )


# --------------------------------------------------
# Demo controls
# --------------------------------------------------

st.divider()

st.header("Demo Controls")

st.warning(
    "Reset Demo deletes purchase orders and decision "
    "logs and restores Industrial Bearings to 400 units."
)

if st.button("Reset Demo"):

    reset_demo()

    st.session_state["flash_message"] = (
        "Demo reset successfully."
    )

    st.rerun()
