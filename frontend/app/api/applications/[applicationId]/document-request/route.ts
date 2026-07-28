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

export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to view document requests.", 401);
  }

  const { applicationId } = await context.params;
  if (!applicationId) {
    return errorResponse("Application id is required.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/applications/${applicationId}/document-request`,
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );
  } catch {
    return errorResponse("Document request service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load document request."),
      backendResponse.status
    );
  }

  return NextResponse.json(payload);
}
