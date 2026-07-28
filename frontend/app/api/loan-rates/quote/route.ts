import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/** POST for the effective rate of a loan type + tenure. */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to get a rate quote.", 401);

  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid rate quote request.", 400);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/loan-rates/quote`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Loan rate service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not get a rate quote."),
      backendResponse.status
    );
  }
  return NextResponse.json({ quote: payload });
}
