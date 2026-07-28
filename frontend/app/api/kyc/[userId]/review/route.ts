import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../auth/_utils";

type RouteContext = { params: Promise<{ userId: string }> };

/** Approve/reject a KYC submission (officer/admin). */
export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const { userId } = await context.params;
  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid review request.", 400);
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/kyc/${encodeURIComponent(userId)}/review`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("KYC service is unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not review KYC."), r.status);
  return NextResponse.json({ kyc: payload });
}
