import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/** POST — validate a PAN number against the mock tax registry. */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to verify a PAN.", 401);

  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid PAN verification request.", 400);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/verification/pan`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Verification service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not verify PAN."),
      backendResponse.status
    );
  }
  return NextResponse.json({ pan: payload });
}
