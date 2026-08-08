import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  clearAuthCookie,
  errorResponse,
  readBackendJson
} from "../_utils";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You are not logged in.", 401);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`
      },
      cache: "no-store"
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    // 401 means the token is no longer valid — expired, or the account was
    // blacklisted. Clear the cookie so the route guard signs them out.
    if (backendResponse.status === 401) {
      const response = NextResponse.json(
        { error: backendErrorMessage(payload, "Your session has ended.") },
        { status: 401 }
      );
      clearAuthCookie(response);
      return response;
    }
    return errorResponse(
      backendErrorMessage(payload, "Could not load current user."),
      backendResponse.status
    );
  }

  return Response.json({ user: payload });
}
