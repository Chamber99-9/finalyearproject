import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/** GET the signed-in customer's loan accounts. */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to view loans.", 401);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/loans/my`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Loan service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load your loans."),
      backendResponse.status
    );
  }
  return NextResponse.json({ loans: payload });
}
