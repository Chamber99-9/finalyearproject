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
    return errorResponse("You must be logged in as an officer.", 401);
  }

  const { applicationId } = await context.params;
  if (!applicationId) {
    return errorResponse("Application id is required.", 400);
  }

  const body = await request.json().catch(() => null);
  if (!body) {
    return errorResponse("Invalid document request.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/officer/applications/${applicationId}/request-document`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
      }
    );
  } catch {
    return errorResponse("Officer document request service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not request additional documents."),
      backendResponse.status
    );
  }

  return NextResponse.json({ document_request: payload }, { status: 201 });
}
