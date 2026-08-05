import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../../auth/_utils";

type RouteContext = { params: Promise<{ userId: string }> };

export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const { userId } = await context.params;
  const body = await request.json().catch(() => ({}));
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/officer/users/${encodeURIComponent(userId)}/blacklist`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ blacklisted: Boolean(body?.blacklisted) })
    });
  } catch {
    return errorResponse("Service unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) return errorResponse(backendErrorMessage(payload, "Could not update user."), r.status);
  return NextResponse.json({ user: payload });
}
