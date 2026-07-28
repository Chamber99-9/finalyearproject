import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to submit KYC.", 401);
  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid KYC request.", 400);
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/kyc/submit`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("KYC service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not submit KYC."), r.status);
  return NextResponse.json({ kyc: payload });
}
