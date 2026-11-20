export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const code = url.searchParams.get("code");

  if (!code) {
    return new Response("Missing authorization code", { status: 400 });
  }

  const clientId = context.env.ORCID_CLIENT_ID;
  const clientSecret = context.env.ORCID_CLIENT_SECRET;
  const redirectUri = context.env.ORCID_REDIRECT_URI;

  // Exchange code for token
  const tokenResp = await fetch("https://orcid.org/oauth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json" },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: "authorization_code",
      code: code,
      redirect_uri: redirectUri,
    }),
  });

  if (!tokenResp.ok) {
    const err = await tokenResp.text();
    return new Response("ORCID token exchange failed: " + err, { status: 500 });
  }

  const tokenData = await tokenResp.json();
  // tokenData contains: orcid, name, access_token, token_type, etc.
  const orcidId = tokenData.orcid;
  const name = tokenData.name;

  if (!orcidId) {
    return new Response("No ORCID iD in response", { status: 500 });
  }

  // Create a simple session token: base64(JSON({orcid, name, exp}))
  // Not cryptographically secure — good enough for prototype
  const session = {
    orcid: orcidId,
    name: name || "",
    exp: Math.floor(Date.now() / 1000) + 86400, // 24 hours
  };
  const sessionToken = btoa(JSON.stringify(session));

  // Set cookie and redirect to home
  return new Response(null, {
    status: 302,
    headers: {
      "Location": "/",
      "Set-Cookie": `streams_session=${sessionToken}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=86400`,
    },
  });
}
