import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../../auth/_utils";

type RouteContext = { params: Promise<{ loanId: string }> };

/** Admin/officer: restructure a loan (extend / defer / waive penalty). */
export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in.", 401);
  const { loanId } = await context.params;
  const body = await request.json().catch(() => ({}));

  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}/loans/${encodeURIComponent(loanId)}/restructure`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Service unavailable.", 503);
  }
  const payload = await readBackendJson(r);
  if (!r.ok) {
    return errorResponse(backendErrorMessage(payload, "Could not restructure the loan."), r.status);
  }
  return NextResponse.json({ loan: payload });
}
