import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../../auth/_utils";

type RouteContext = { params: Promise<{ userId: string }> };

/** Admin: a customer's loan accounts (for restructuring controls). */
export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const { userId } = await context.params;

  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/admin/users/${encodeURIComponent(userId)}/loans`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store"
    });
  } catch {
    return errorResponse("Service unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) {
    return errorResponse(backendErrorMessage(payload, "Could not load loans."), r.status);
  }
  return NextResponse.json({ loans: payload });
}
