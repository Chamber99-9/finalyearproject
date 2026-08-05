import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../_utils";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);

  if (!body?.full_name || !body?.email || !body?.phone || !body?.password) {
    return errorResponse("Full name, email, phone, and password are required.");
  }

  const email = String(body.email).trim().toLowerCase();
  const password = String(body.password);

  let registerResponse: Response;
  try {
    registerResponse = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: String(body.full_name).trim(),
        email,
        phone: String(body.phone).trim(),
        password
      })
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }

  const registerPayload = await readBackendJson(registerResponse);

  if (!registerResponse.ok) {
    return errorResponse(
      backendErrorMessage(registerPayload, "Registration failed. Please try again."),
      registerResponse.status
    );
  }

  // Registration no longer auto-logs-in: the account is inactive until the
  // emailed OTP is verified. Hand the verification challenge back to the client.
  return NextResponse.json(
    { verification_required: true, email: registerPayload.email ?? email },
    { status: 201 }
  );
}
