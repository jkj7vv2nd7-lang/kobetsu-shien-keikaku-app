export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function token(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || "";
}
export function authHeaders(): Record<string, string> {
  const t = token();
  return t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
}
export async function api(path: string, init?: RequestInit) {
  const r = await fetch(`${API}${path}`, init);
  if (r.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`${r.status}: ${t.slice(0, 300)}`);
  }
  return r.json();
}
