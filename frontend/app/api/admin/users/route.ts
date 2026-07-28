import { NextRequest, NextResponse } from "next/server";

import {
  API_BASE_URL,
  AUTH_COOKIE_NAME,
  backendErrorMessage,
  errorResponse,
  readBackendJson
} from "../../auth/_utils";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in as an admin.", 401);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/admin/users`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  } catch {
    return errorResponse("Admin user service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not load users."),
      backendResponse.status
    );
  }

  return NextResponse.json({ users: payload });
}
