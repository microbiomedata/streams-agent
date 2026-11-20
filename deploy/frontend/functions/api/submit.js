export async function onRequestPost(context) {
  const base = context.env.MODAL_BASE_URL; // e.g. https://cmungall--streams-agent-prototype
  const modalUrl = base ? `${base}-submit.modal.run` : context.env.MODAL_SUBMIT_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_BASE_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Determine user identity: ORCID session or anonymous (IP-based)
  const session = parseSession(context.request);
  const clientIp = context.request.headers.get("CF-Connecting-IP") || "unknown";
  const userId = session ? session.orcid : `anon:${clientIp}`;

  const body = await context.request.json();
  body.user_id = userId;

  const resp = await fetch(modalUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-secret": context.env.API_SECRET || "dev-secret",
    },
    body: JSON.stringify(body),
  });

  const result = await resp.json();
  return new Response(JSON.stringify(result), {
    status: result.error ? 429 : resp.status,
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
