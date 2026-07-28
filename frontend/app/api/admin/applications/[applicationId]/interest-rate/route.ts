import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../../auth/_utils";

type RouteContext = {
  params: Promise<{
    applicationId: string;
  }>;
};

/** PUT — admin override of an application's interest rate (recalculates EMI). */
export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to change the interest rate.", 401);

  const { applicationId } = await context.params;
  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid interest rate request.", 400);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/admin/applications/${applicationId}/interest-rate`,
      {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }
    );
  } catch {
    return errorResponse("Admin service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not update the interest rate."),
      backendResponse.status
    );
  }
  return NextResponse.json({ application: payload });
}
