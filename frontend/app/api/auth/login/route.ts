import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  backendErrorMessage,
  errorResponse,
  readBackendJson,
  setAuthCookie
} from "../_utils";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);

  if (!body?.email || !body?.password) {
    return errorResponse("Email and password are required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: String(body.email).trim().toLowerCase(),
        password: String(body.password)
      })
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Login failed. Please check your details."),
      backendResponse.status
    );
  }

  if (!payload.access_token || !payload.user) {
    return errorResponse("Login response was missing authentication data.", 502);
  }

  const response = NextResponse.json({ user: payload.user });
  setAuthCookie(response, payload.access_token);
  return response;
}
