import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

type RouteContext = { params: Promise<{ paymentId: string }> };

/** Fetch one of the customer's own payments (checkout + receipt). */
export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const { paymentId } = await context.params;
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/payments/${encodeURIComponent(paymentId)}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Payment service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not load payment."), r.status);
  return NextResponse.json({ payment: payload });
}
