import { NextResponse } from "next/server";

export const AUTH_COOKIE_NAME = "sajilo_auth_token";
export const API_BASE_URL =
  process.env.SAJILO_API_BASE_URL ?? "http://127.0.0.1:8000";

export type BackendError = {
  detail?: string | Array<{ msg?: string; loc?: Array<string | number> }>;
};

export async function readBackendJson(response: Response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

export function errorResponse(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

export function setAuthCookie(response: NextResponse, token: string) {
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60
  });
}

export function backendErrorMessage(payload: BackendError, fallback: string) {
  if (typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail;
  }

  if (Array.isArray(payload.detail) && payload.detail.length > 0) {
    return payload.detail
      .map((item) => {
        const field = item.loc?.filter((part) => part !== "body").join(".");
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .filter(Boolean)
      .join(" ");
  }

  return fallback;
}
