export async function onRequestPost(context) {
  // Mock auth check
  const auth = context.request.headers.get("Authorization");
  if (auth !== "Bearer test-token") {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Forward to Modal
  const modalUrl = context.env.MODAL_SUBMIT_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_SUBMIT_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const body = await context.request.json();
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
    status: resp.status,
    headers: { "Content-Type": "application/json" },
  });
}
