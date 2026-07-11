// Supabase Edge Function trigger for nightly burnout scoring.
// Schedule this function from Supabase's dashboard/cron and point it at the
// deployed FastAPI backend, which owns Python feature extraction + joblib model
// inference.

Deno.serve(async () => {
  const backendUrl = Deno.env.get("BACKEND_INTERNAL_URL");
  const jobSecret = Deno.env.get("INTERNAL_JOB_SECRET");

  if (!backendUrl || !jobSecret) {
    return new Response(
      JSON.stringify({ error: "BACKEND_INTERNAL_URL and INTERNAL_JOB_SECRET are required" }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  const response = await fetch(`${backendUrl.replace(/\/$/, "")}/internal/jobs/burnout-nightly`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${jobSecret}`,
      "content-type": "application/json",
    },
  });

  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
});
