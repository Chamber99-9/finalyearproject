import { NextRequest } from "next/server";

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

export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in to view OCR results.", 401);
  }

  const { ocrResultId } = await context.params;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/ocr/results/${ocrResultId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  } catch {
    return errorResponse("OCR service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load OCR result."),
      backendResponse.status
    );
  }

  return Response.json({ ocr_result: payload });
}

