import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../auth/_utils";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/officer/payments/pending`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Service unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not load payments."), r.status);
  return NextResponse.json({ payments: payload });
}
