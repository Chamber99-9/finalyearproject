"""Real payment-rail integration (Khalti KPG-2).

Khalti's ePayment flow:
  1. initiate  -> POST /epayment/initiate/  returns { pidx, payment_url }.
     We redirect the customer to `payment_url`.
  2. Khalti redirects back to our `return_url?pidx=...&status=...` after payment.
  3. lookup   -> POST /epayment/lookup/  { pidx }  returns the authoritative
     status ("Completed" etc.). We NEVER trust the redirect params — we always
     confirm server-side via lookup before settling.

All amounts are in paisa (NPR * 100). Requires KHALTI_SECRET_KEY.
"""

from typing import Any

import httpx

from app.config import get_settings


class GatewayError(Exception):
    pass


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.khalti_secret_key:
        raise GatewayError("KHALTI_SECRET_KEY is not configured.")
    return {"Authorization": f"Key {settings.khalti_secret_key}"}


async def khalti_initiate(
    *,
    amount_paisa: int,
    purchase_order_id: str,
    purchase_order_name: str,
    return_url: str,
    website_url: str,
    customer: dict[str, Any],
) -> dict[str, str]:
    """Create a Khalti payment and return its checkout URL + pidx."""
    settings = get_settings()
    payload = {
        "return_url": return_url,
        "website_url": website_url,
        "amount": int(amount_paisa),
        "purchase_order_id": purchase_order_id,
        "purchase_order_name": purchase_order_name,
        "customer_info": {
            "name": customer.get("name") or "Customer",
            "email": customer.get("email") or "",
            "phone": customer.get("phone") or "",
        },
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{settings.khalti_base_url}/epayment/initiate/",
            json=payload,
            headers=_auth_headers(),
        )
    if response.status_code != 200:
        raise GatewayError(f"Khalti initiate failed: {response.text}")
    data = response.json()
    return {"checkout_url": data["payment_url"], "provider_ref": data["pidx"]}


def _map_status(khalti_status: str) -> str:
    if khalti_status == "Completed":
        return "success"
    if khalti_status == "Pending":
        return "pending"
    return "failed"


async def khalti_lookup(pidx: str) -> dict[str, Any]:
    """Server-side confirmation of a Khalti payment (authoritative)."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{settings.khalti_base_url}/epayment/lookup/",
            json={"pidx": pidx},
            headers=_auth_headers(),
        )
    if response.status_code != 200:
        raise GatewayError(f"Khalti lookup failed: {response.text}")
    data = response.json()
    return {
        "status": _map_status(str(data.get("status", ""))),
        "transaction_id": data.get("transaction_id"),
        "total_amount": data.get("total_amount"),
        "raw": data,
    }
