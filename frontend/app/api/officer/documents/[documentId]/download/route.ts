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
    documentId: string;
  }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in as an officer.", 401);
  }

  const { documentId } = await context.params;
  if (!documentId) {
    return errorResponse("Document id is required.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/officer/documents/${documentId}/download`,
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );
  } catch {
    return errorResponse("Officer document service is unavailable.", 503);
  }

  if (!backendResponse.ok) {
    const payload = await readBackendJson(backendResponse);
    return errorResponse(
      backendErrorMessage(payload, "Could not load uploaded document."),
      backendResponse.status
    );
  }

  return new NextResponse(backendResponse.body, {
    headers: {
      "Content-Disposition":
        backendResponse.headers.get("Content-Disposition") ?? "inline",
      "Content-Type":
        backendResponse.headers.get("Content-Type") ?? "application/octet-stream"
    }
  });
}
