import { NextResponse } from "next/server";

import { clearAuthCookie } from "../_utils";

/** Clear the auth cookie to log the user out. */
export async function POST() {
  const response = NextResponse.json({ ok: true });
  clearAuthCookie(response);
  return response;
}
