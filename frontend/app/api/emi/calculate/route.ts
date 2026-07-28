import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/**
 * Proxy for POST /emi/calculate on the FastAPI backend.
 * Mirrors the existing route-handler pattern (forwards the JWT cookie as a
 * bearer token and normalizes backend errors).
 */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to calculate an EMI.", 401);
  }

  const body = await request.json().catch(() => null);
  if (!body) {
    return errorResponse("Invalid EMI calculation request.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/emi/calculate`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("EMI service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not calculate EMI."),
      backendResponse.status
    );
  }

  return NextResponse.json({ emi: payload });
}
