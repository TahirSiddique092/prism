import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

/**
 * POST /api/documents/upload (Next route handler)
 *
 * Proxies PDF file upload to Flask with JWT authentication.
 * Form payload contains:
 *  - file: PDF file (max 20MB)
 *  - topics: comma-separated string or array
 */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: "Unauthorized — missing session token" },
      { status: 401 }
    );
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "Invalid form data in request" },
      { status: 400 }
    );
  }

  const file = formData.get("file");
  if (!file || typeof file === "string") {
    return NextResponse.json(
      { error: "No file part in the request" },
      { status: 400 }
    );
  }

  if (file.name === "") {
    return NextResponse.json(
      { error: "No selected file" },
      { status: 400 }
    );
  }

  if (!file.name.toLowerCase().endsWith(".pdf")) {
    return NextResponse.json(
      { error: "Only .pdf files are accepted" },
      { status: 400 }
    );
  }

  if (file.size > MAX_FILE_SIZE) {
    return NextResponse.json(
      { error: "File size limit exceeded (20MB max)" },
      { status: 413 }
    );
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}/api/documents/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { error: "Unable to reach documents upload service" },
      { status: 502 }
    );
  }
}
