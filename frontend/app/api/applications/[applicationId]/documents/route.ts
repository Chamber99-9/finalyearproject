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
    return errorResponse("You must be logged in to view documents.", 401);
  }

  const { applicationId } = await context.params;
  if (!applicationId) {
    return errorResponse("Application id is required.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/applications/${applicationId}/documents`,
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );
  } catch {
    return errorResponse("Document service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load documents."),
      backendResponse.status
    );
  }

  return NextResponse.json({ documents: payload });
}

export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to upload documents.", 401);
  }

  const { applicationId } = await context.params;
  if (!applicationId) {
    return errorResponse("Application id is required.", 400);
  }

  const formData = await request.formData().catch(() => null);
  if (!formData) {
    return errorResponse("Invalid upload request.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${API_BASE_URL}/applications/${applicationId}/documents`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: formData
      }
    );
  } catch {
    return errorResponse("Document upload service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not upload document."),
      backendResponse.status
    );
  }

  return NextResponse.json({ document: payload }, { status: 201 });
}
