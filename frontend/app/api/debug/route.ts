export async function GET() {
  const backendUrl = process.env.BACKEND_URL ?? "(not set)";
  let backendReachable = false;
  let backendError = "";
  try {
    const res = await fetch(`${backendUrl}/`, { signal: AbortSignal.timeout(5000) });
    backendReachable = res.ok;
  } catch (e) {
    backendError = String(e);
  }
  return Response.json({ backendUrl, backendReachable, backendError });
}
