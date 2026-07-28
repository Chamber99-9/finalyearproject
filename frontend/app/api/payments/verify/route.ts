import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/** Confirm a real-rail payment after the gateway redirects back. */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const body = await request.json().catch(() => null);
  if (!body?.provider_ref) return errorResponse("Missing payment reference.", 400);

  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/payments/verify`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ provider_ref: String(body.provider_ref) })
    });
  } catch {
    return errorResponse("Payment service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not verify payment."), r.status);
  return NextResponse.json({ payment: payload });
}
