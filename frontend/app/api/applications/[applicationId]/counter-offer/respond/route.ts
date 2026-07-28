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

export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to respond to this offer.", 401);
  }

  const { applicationId } = await context.params;
  const body = await request.json().catch(() => null);
  if (!body || typeof body.accepted !== "boolean") {
    return errorResponse("Invalid counter offer response.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/applications/${applicationId}/counter-offer/respond`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ accepted: body.accepted })
      }
    );
  } catch {
    return errorResponse("Counter offer response service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not respond to counter offer."),
      backendResponse.status
    );
  }

  return NextResponse.json({ application: payload });
}
