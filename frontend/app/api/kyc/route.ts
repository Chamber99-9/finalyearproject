import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../auth/_utils";

/** Pending KYC queue (officer/admin, enforced by the backend). */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/kyc`, { headers: { Authorization: `Bearer ${token}` } });
  } catch {
    return errorResponse("KYC service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not load KYC queue."), r.status);
  return NextResponse.json({ records: payload });
}
