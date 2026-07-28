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
    ocrResultId: string;
  }>;
};

export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to verify OCR results.", 401);
  }

  const { ocrResultId } = await context.params;
  const body = await request.json().catch(() => null);

  if (!body || typeof body.corrected_data !== "object" || Array.isArray(body.corrected_data)) {
    return errorResponse("Corrected data must be an object.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/ocr/verify/${ocrResultId}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        corrected_data: body.corrected_data
      })
    });
  } catch {
    return errorResponse("OCR verification service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not verify OCR result."),
      backendResponse.status
    );
  }

  return NextResponse.json({ ocr_result: payload });
}

