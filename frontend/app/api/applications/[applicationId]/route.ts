import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

type RouteContext = {
  params: Promise<{
    applicationId: string;
  }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to view this application.", 401);
  }

  const { applicationId } = await context.params;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/applications/${applicationId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  } catch {
    return errorResponse("Application service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load application."),
      backendResponse.status
    );
  }

  return NextResponse.json({ application: payload });
}

export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to update this application.", 401);
  }

  const { applicationId } = await context.params;
  const body = await request.json().catch(() => null);

  if (!body) {
    return errorResponse("Invalid application update request.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/applications/${applicationId}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Application service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not update application."),
      backendResponse.status
    );
  }

  return NextResponse.json({ application: payload });
}
