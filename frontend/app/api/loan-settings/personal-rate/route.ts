import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/** GET the current bank Personal Loan interest rate (any signed-in user). */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to view the interest rate.", 401);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/loan-settings/personal-rate`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Loan settings service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load the interest rate."),
      backendResponse.status
    );
  }
  return NextResponse.json({ setting: payload });
}

/** PUT to change the bank default rate (admin only, enforced by the backend). */
export async function PUT(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to change the interest rate.", 401);

  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid interest rate request.", 400);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/loan-settings/personal-rate`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Loan settings service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not update the interest rate."),
      backendResponse.status
    );
  }
  return NextResponse.json({ setting: payload });
}
