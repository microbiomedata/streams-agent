export async function onRequestGet(context) {
  const clientId = context.env.ORCID_CLIENT_ID;
  const redirectUri = context.env.ORCID_REDIRECT_URI;

  if (!clientId || !redirectUri) {
    return new Response(JSON.stringify({ error: "ORCID not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const orcidAuthUrl = "https://orcid.org/oauth/authorize"
    + `?client_id=${clientId}`
    + `&response_type=code`
    + `&scope=/authenticate`
    + `&redirect_uri=${encodeURIComponent(redirectUri)}`;

  return Response.redirect(orcidAuthUrl, 302);
}
