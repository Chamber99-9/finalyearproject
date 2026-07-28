import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/** POST — salary-based cap + collateral requirement for a requested loan. */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to check eligibility.", 401);

  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid eligibility request.", 400);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/loan-eligibility/check`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Eligibility service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not check eligibility."),
      backendResponse.status
    );
  }
  return NextResponse.json({ eligibility: payload });
}
