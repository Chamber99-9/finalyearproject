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
    loanId: string;
  }>;
};

/** POST — pay one EMI on a loan (reduces the outstanding balance). */
export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) return errorResponse("You must be logged in to pay an EMI.", 401);

  const { loanId } = await context.params;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/loans/${encodeURIComponent(loanId)}/pay`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    return errorResponse("Loan service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);
  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not record the payment."),
      backendResponse.status
    );
  }
  return NextResponse.json({ payment: payload });
}
