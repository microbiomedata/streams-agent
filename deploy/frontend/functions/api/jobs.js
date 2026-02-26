export async function onRequestGet(context) {
  // Mock auth check
  const auth = context.request.headers.get("Authorization");
  if (auth !== "Bearer test-token") {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const modalUrl = context.env.MODAL_JOBS_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_JOBS_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const resp = await fetch(modalUrl, {
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
