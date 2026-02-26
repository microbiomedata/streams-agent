export async function onRequestPost(context) {
  const modalUrl = context.env.MODAL_EXTRACT_TITLE_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_EXTRACT_TITLE_URL not configured" }), {
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

  const text = await resp.text();
  if (!resp.ok) {
    return new Response(JSON.stringify({ title: "", slug: "", error: "extraction failed" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  return new Response(text, {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
