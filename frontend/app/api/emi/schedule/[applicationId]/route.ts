import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../../auth/_utils";

type RouteContext = {
  params: Promise<{
    applicationId: string;
  }>;
};

/**
 * Proxy for GET /emi/schedule/{application_id} on the FastAPI backend.
 * Returns the full amortization schedule for a stored application.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to view the schedule.", 401);
  }

  const { applicationId } = await context.params;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/emi/schedule/${encodeURIComponent(applicationId)}`,
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );
  } catch {
    return errorResponse("EMI service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load amortization schedule."),
      backendResponse.status
    );
  }

  return NextResponse.json({ schedule: payload });
}
