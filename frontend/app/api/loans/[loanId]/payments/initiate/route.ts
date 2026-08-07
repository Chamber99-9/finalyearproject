import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../../auth/_utils";

type RouteContext = { params: Promise<{ loanId: string }> };

/** Create a pending payment intent for one EMI. */
export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to pay.", 401);
  const { loanId } = await context.params;
  const chosen = request.nextUrl.searchParams.get("method");
  const query = chosen ? `?method=${encodeURIComponent(chosen)}` : "";
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/loans/${encodeURIComponent(loanId)}/payments/initiate${query}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Payment service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not start payment."), r.status);
  return NextResponse.json({ payment: payload });
}
