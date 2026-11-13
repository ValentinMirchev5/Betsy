from typing import Literal

from ollama import chat

from pydantic import (
    BaseModel,
    Field
)


MODEL_NAME = "qwen3.5:4b"


# --------------------------------------------------
# Structured AI response
# --------------------------------------------------

class SupplierRecommendation(BaseModel):

    supplier_name: str

    reasoning: str

    risk_level: Literal[
        "low",
        "medium",
        "high"
    ]

    confidence: float = Field(
        ge=0,
        le=1
    )


# --------------------------------------------------
# Ollama supplier reasoning
# --------------------------------------------------

def recommend_supplier(
    product,
    suppliers
):
    """
    Uses Ollama to recommend one supplier.

    IMPORTANT:
    The LLM only receives suppliers that Python
    has already determined are eligible.

    The LLM is used for reasoning and trade-off
    analysis, not for bypassing safety rules.
    """

    # Only suppliers that passed deterministic
    # Python safety rules are sent to the LLM.
    eligible_suppliers = [
        supplier
        for supplier in suppliers
        if supplier.get("eligible") is True
    ]

    if not eligible_suppliers:
        return None


    # --------------------------------------------------
    # Build supplier context
    # --------------------------------------------------

    supplier_text = ""

    for supplier in eligible_suppliers:

        supplier_text += (
            f"\n"
            f"Supplier: {supplier['name']}\n"
            f"Unit price: EUR "
            f"{supplier['unit_price']}\n"
            f"Delivery time: "
            f"{supplier['delivery_hours']} hours\n"
            f"Reliability: "
            f"{supplier['reliability']}%\n"
        )


    # --------------------------------------------------
    # Prompt
    # --------------------------------------------------

    prompt = f"""
You are Betsy, an AI procurement agent working
for a manufacturing company.

A deterministic safety system has already removed
suppliers that are unavailable or cannot deliver
before the predicted stockout.

You must recommend ONE supplier from the eligible
supplier list below.


PRODUCT INFORMATION

Product:
{product['name']}

Current stock:
{product['current_stock']}

Daily usage:
{product['daily_usage']}

Days until predicted stockout:
{product['days_remaining']:.2f}

Hours until predicted stockout:
{product['hours_remaining']:.2f}


ELIGIBLE SUPPLIERS

{supplier_text}


Evaluate the suppliers using these factors:

1. Purchase price
2. Delivery speed
3. Historical reliability
4. Urgency of the stockout
5. Operational risk


IMPORTANT RULES

- Choose ONLY from the provided eligible suppliers.
- Do not invent suppliers.
- Do not invent prices.
- Do not invent reliability values.
- Do not invent delivery times.
- Do not modify any of the supplied business facts.
- Confidence must be between 0 and 1.
- Risk level must be low, medium, or high.


Explain the business reasoning behind your choice.

Return structured JSON matching the provided schema.
"""


    # --------------------------------------------------
    # Call Ollama
    # --------------------------------------------------

    print(
        f"\nCalling Ollama model "
        f"{MODEL_NAME} for supplier reasoning..."
    )

    response = chat(
        model=MODEL_NAME,

        messages=[
            {
                "role": "system",

                "content": (
                    "You are a cautious enterprise "
                    "procurement decision-support AI. "
                    "Use only the supplied business data. "
                    "Never invent financial, supplier, "
                    "inventory or delivery information."
                )
            },

            {
                "role": "user",
                "content": prompt
            }
        ],

        # Forces the LLM response into the
        # Pydantic JSON structure.
        format=(
            SupplierRecommendation
            .model_json_schema()
        ),

        # We do not need a long reasoning phase
        # for this structured procurement decision.
        think=False,

        options={
            # Deterministic / less random responses
            "temperature": 0,

            # Enough context for the procurement prompt
            "num_ctx": 4096,

            # Prevent unnecessarily long responses
            "num_predict": 250
        }
    )


    print(
        "Ollama supplier recommendation received."
    )


    # --------------------------------------------------
    # Validate structured response
    # --------------------------------------------------

    recommendation = (
        SupplierRecommendation
        .model_validate_json(
            response.message.content
        )
    )


    return recommendation