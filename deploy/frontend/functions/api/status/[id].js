export async function onRequestGet(context) {
  const jobId = context.params.id;
  const modalUrl = context.env.MODAL_STATUS_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_STATUS_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const resp = await fetch(`${modalUrl}?job_id=${jobId}`, {
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
