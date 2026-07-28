import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/** GET the loan-type menu with this-month indicative rates. */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to view loan types.", 401);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/loan-rates/types`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Loan rate service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load loan types."),
      backendResponse.status
    );
  }
  return NextResponse.json({ loan_types: payload });
}
