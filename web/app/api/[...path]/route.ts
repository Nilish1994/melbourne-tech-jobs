import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
// Only these read-only resources are reachable from the browser.
const ALLOWED = /^(analytics(\/[a-z/]*)?|jobs)$/;

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path.join("/");
  if (!ALLOWED.test(path)) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  const upstream = await fetch(`${API_URL}/${path}${request.nextUrl.search}`, { next: { revalidate: 300 } });
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
