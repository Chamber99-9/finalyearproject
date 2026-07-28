import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

/**
 * Proxy for POST /emi/preview — customer-facing EMI preview that uses the
 * bank-defined rate (customer sends only loan amount + tenure).
 */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to preview an EMI.", 401);

  const body = await request.json().catch(() => null);
  if (!body) return errorResponse("Invalid EMI preview request.", 400);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/emi/preview`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("EMI service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not preview EMI."),
      backendResponse.status
    );
  }
  return NextResponse.json({ emi: payload });
}
