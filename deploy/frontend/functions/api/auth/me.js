export async function onRequestGet(context) {
  const adminOrcids = (context.env.ADMIN_ORCIDS || "").split(",").map(s => s.trim()).filter(Boolean);
  const session = parseSession(context.request);
  if (session) {
    const isAdmin = adminOrcids.includes(session.orcid);
    return new Response(JSON.stringify({ logged_in: true, orcid: session.orcid, name: session.name, is_admin: isAdmin }), {
      headers: { "Content-Type": "application/json" },
    });
  }
  return new Response(JSON.stringify({ logged_in: false, is_admin: false }), {
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
