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
    userId: string;
  }>;
};

export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return errorResponse("You must be logged in as an admin.", 401);
  }

  const { userId } = await context.params;
  if (!userId) {
    return errorResponse("User id is required.", 400);
  }

  const body = await request.json().catch(() => null);
  if (!body) {
    return errorResponse("Invalid role update request.", 400);
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${API_BASE_URL}/admin/users/${userId}/role`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });
  } catch {
    return errorResponse("Admin role service is unavailable.", 503);
  }

  const payload = await readBackendJson(backendResponse);

  if (!backendResponse.ok) {
    return errorResponse(
      backendErrorMessage(payload, "Could not update user role."),
      backendResponse.status
    );
  }

  return NextResponse.json({ user: payload });
}
