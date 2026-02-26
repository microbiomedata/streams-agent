export async function onRequestGet(context) {
  const modalUrl = context.env.MODAL_JOBS_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_JOBS_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Pass user_id filter if logged in
  const session = parseSession(context.request);
  const clientIp = context.request.headers.get("CF-Connecting-IP") || "unknown";
  const userId = session ? session.orcid : `anon:${clientIp}`;

  const resp = await fetch(`${modalUrl}?user_id=${encodeURIComponent(userId)}`, {
    headers: {
      "x-api-secret": context.env.API_SECRET || "dev-secret",
    },
  });

  const result = await resp.json();
  return new Response(JSON.stringify(result), {
    status: resp.status,
    headers: { "Content-Type": "application/json" },
  });
}

function parseSession(request) {
  const cookie = request.headers.get("Cookie") || "";
  const match = cookie.match(/streams_session=([^;]+)/);
  if (!match) return null;
  try {
    const session = JSON.parse(atob(match[1]));
    if (session.exp && session.exp < Math.floor(Date.now() / 1000)) return null;
    return session;
  } catch {
    return null;
  }
}
