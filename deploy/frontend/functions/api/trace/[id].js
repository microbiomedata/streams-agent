export async function onRequestGet(context) {
  const jobId = context.params.id;
  const base = context.env.MODAL_BASE_URL;
  const modalUrl = base ? `${base}-trace.modal.run` : context.env.MODAL_TRACE_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_BASE_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const resp = await fetch(`${modalUrl}?job_id=${jobId}`, {
    headers: {
      "x-api-secret": context.env.API_SECRET || "dev-secret",
    },
  });

  const result = await resp.text();
  return new Response(result, {
    status: resp.status,
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": `attachment; filename="trace-${jobId}.json"`,
    },
  });
}
