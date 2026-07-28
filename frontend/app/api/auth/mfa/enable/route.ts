import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../_utils";

export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/auth/mfa/enable`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not enable MFA."), r.status);
  return NextResponse.json({ mfa: payload });
}
