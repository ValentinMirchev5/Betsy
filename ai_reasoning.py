from typing import Literal

from ollama import chat
from pydantic import BaseModel


MODEL_NAME = "qwen3.5:4b"


class SupplierRecommendation(BaseModel):
    supplier_name: str

    reasoning: str

    risk_level: Literal[
        "low",
        "medium",
        "high"
    ]

    confidence: float


def recommend_supplier(
    product,
    suppliers
):
    """
    Uses an LLM to analyse the safe supplier options.

    Important:
    The LLM does NOT decide which suppliers are allowed.
    Python business rules determine supplier eligibility first.
    """

    eligible_suppliers = [
        supplier
        for supplier in suppliers
        if supplier.get("eligible") is True
    ]

    if not eligible_suppliers:
        return None

    supplier_text = ""

    for supplier in eligible_suppliers:
        supplier_text += (
            f"\nSupplier: {supplier['name']}\n"
            f"Unit price: EUR {supplier['unit_price']}\n"
            f"Delivery time: {supplier['delivery_hours']} hours\n"
            f"Reliability: {supplier['reliability']}%\n"
        )

    prompt = f"""
You are Betsy, an AI procurement agent for a manufacturing company.

Your task is to recommend ONE supplier from the eligible suppliers provided.

PRODUCT INFORMATION

Product:
{product['name']}

Current stock:
{product['current_stock']}

Daily usage:
{product['daily_usage']}

Estimated days remaining:
{product['days_remaining']:.2f}

Estimated hours remaining:
{product['hours_remaining']:.2f}

ELIGIBLE SUPPLIERS
{supplier_text}

Evaluate the trade-off between:

- purchase price
- delivery speed
- supplier reliability
- urgency of the predicted stockout

You MUST choose a supplier from the eligible supplier list.

Do not invent suppliers, prices, delivery times or reliability values.

Explain why the recommended supplier is appropriate.

Return the answer as structured JSON.
"""

    response = chat(
        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a cautious enterprise procurement "
                    "decision-support AI. Never invent business data."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        format=SupplierRecommendation.model_json_schema(),

        options={
            "temperature": 0
        }
    )

    recommendation = (
        SupplierRecommendation.model_validate_json(
            response.message.content
        )
    )

    return recommendation
