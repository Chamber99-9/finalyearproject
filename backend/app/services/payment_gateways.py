"""Real payment-rail integrations (eSewa ePay v2 and Khalti KPG-2).

eSewa ePay v2 flow (the project's default rail):
  1. initiate -> we build a signed form (HMAC-SHA256 over
     "total_amount,transaction_uuid,product_code") that the customer's browser
     POSTs to eSewa's hosted payment page.
  2. eSewa redirects back to our success_url with a base64 `data` payload.
  3. status  -> GET the transaction status API and settle only on "COMPLETE".
     We NEVER trust the redirect payload alone — the status API is authoritative.

Khalti's ePayment flow:
  1. initiate -> POST /epayment/initiate/ returns { pidx, payment_url }.
  2. Khalti redirects back to our return_url?pidx=...&status=...
  3. lookup   -> POST /epayment/lookup/ { pidx } returns the authoritative status.

Khalti amounts are in paisa (NPR * 100); eSewa amounts are in rupees.
"""

import base64
import hashlib
import hmac
from typing import Any

import httpx

from app.config import get_settings


class GatewayError(Exception):
    pass


# --- eSewa ePay v2 ----------------------------------------------------------

def _esewa_signature(message: str) -> str:
    """HMAC-SHA256(base64) over the eSewa signed field string."""
    secret = get_settings().esewa_secret_key
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def esewa_build_form(
    *,
    amount: float,
    transaction_uuid: str,
    success_url: str,
    failure_url: str,
) -> dict[str, Any]:
    """Return the auto-submit form (action URL + fields) for eSewa checkout.

    eSewa signs exactly these three fields in this order:
    total_amount, transaction_uuid, product_code.
    """
    settings = get_settings()
    total_amount = f"{amount:.2f}"
    product_code = settings.esewa_merchant_code
    signed_field_names = "total_amount,transaction_uuid,product_code"
    message = (
        f"total_amount={total_amount},"
        f"transaction_uuid={transaction_uuid},"
        f"product_code={product_code}"
    )
    signature = _esewa_signature(message)
    fields = {
        "amount": total_amount,
        "tax_amount": "0",
        "total_amount": total_amount,
        "transaction_uuid": transaction_uuid,
        "product_code": product_code,
        "product_service_charge": "0",
        "product_delivery_charge": "0",
        "success_url": success_url,
        "failure_url": failure_url,
        "signed_field_names": signed_field_names,
        "signature": signature,
    }
    return {"action": settings.esewa_form_url, "fields": fields}


def _map_esewa_status(esewa_status: str) -> str:
    status = (esewa_status or "").upper()
    if status == "COMPLETE":
        return "success"
    if status in {"PENDING", "AMBIGUOUS"}:
        return "pending"
    return "failed"


async def esewa_status_check(*, transaction_uuid: str, total_amount: float) -> dict[str, Any]:
    """Authoritative server-side status check for an eSewa transaction."""
    settings = get_settings()
    params = {
        "product_code": settings.esewa_merchant_code,
        "total_amount": f"{total_amount:.2f}",
        "transaction_uuid": transaction_uuid,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(settings.esewa_status_url, params=params)
    if response.status_code != 200:
        raise GatewayError(f"eSewa status check failed: {response.text}")
    data = response.json()
    return {
        "status": _map_esewa_status(str(data.get("status", ""))),
        "transaction_id": data.get("ref_id"),
        "total_amount": data.get("total_amount"),
        "raw": data,
    }


# --- Khalti KPG-2 -----------------------------------------------------------


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
