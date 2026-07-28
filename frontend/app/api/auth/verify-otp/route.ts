import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  backendErrorMessage,
  errorResponse,
  readBackendJson,
  setAuthCookie
} from "../_utils";

/** Complete two-factor login: verify the emailed OTP and set the auth cookie. */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.otp) {
    return errorResponse("Email and code are required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/auth/verify-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: String(body.email).trim().toLowerCase(),
        otp: String(body.otp).trim()
      })
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Invalid or expired code."),
      backendResponse.status
    );
  }
  if (!payload.access_token || !payload.user) {
    return errorResponse("Verification response was missing authentication data.", 502);
  }

  const response = NextResponse.json({ user: payload.user });
  setAuthCookie(response, payload.access_token);
  return response;
}
