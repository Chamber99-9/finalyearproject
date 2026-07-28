import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../auth/_utils";

type RouteContext = { params: Promise<{ paymentId: string }> };

/** Dev/demo: emulate the gateway confirming a payment (runs the real webhook path). */
export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const { paymentId } = await context.params;
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/payments/${encodeURIComponent(paymentId)}/simulate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Payment service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not confirm payment."), r.status);
  return NextResponse.json({ payment: payload });
}
