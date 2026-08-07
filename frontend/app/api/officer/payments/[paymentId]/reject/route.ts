import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../../auth/_utils";

type RouteContext = { params: Promise<{ paymentId: string }> };

/** Officer rejects a receipt that doesn't match the bank statement. */
export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const { paymentId } = await context.params;
  const body = await request.json().catch(() => ({}));
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/officer/payments/${encodeURIComponent(paymentId)}/reject`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Service unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not reject payment."), r.status);
  return NextResponse.json({ payment: payload });
}
