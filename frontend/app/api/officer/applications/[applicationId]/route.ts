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
    return errorResponse("You must be logged in as an officer.", 401);
  }

  const { applicationId } = await context.params;
  if (!applicationId) {
    return errorResponse("Application id is required.", 400);
  }

  let riskResponse: Response;
  try {
    riskResponse = await fetch(`${API_BASE_URL}/risk/calculate/${applicationId}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  } catch {
    return errorResponse("Credit risk scoring service is unavailable.", 503);
  }

  const riskPayload = await readBackendJson(riskResponse);

  if (!riskResponse.ok) {
    return errorResponse(
      backendErrorMessage(riskPayload, "Could not calculate credit risk score."),
      riskResponse.status
    );
  }

  let flagCheckResponse: Response;
  try {
    flagCheckResponse = await fetch(`${API_BASE_URL}/flags/check/${applicationId}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  } catch {
    return errorResponse("Suspicious flag service is unavailable.", 503);
  }

  const flagCheckPayload = await readBackendJson(flagCheckResponse);

  if (!flagCheckResponse.ok) {
    return errorResponse(
      backendErrorMessage(flagCheckPayload, "Could not check suspicious application flags."),
      flagCheckResponse.status
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/officer/applications/${applicationId}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  } catch {
    return errorResponse("Officer application service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load application review details."),
      backendResponse.status
    );
  }

  return NextResponse.json({ detail: payload });
}
