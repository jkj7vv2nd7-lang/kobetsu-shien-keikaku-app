"use client";
import { API, token } from "../lib/api";

export default function LogoutButton() {
  async function logout() {
    const t = token();
    if (t) {
      try { await fetch(`${API}/api/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${t}` } }); } catch {}
      localStorage.removeItem("token");
    }
    window.location.href = "/login";
  }
  return (
    <button className="btn" style={{ marginLeft: 12, padding: "2px 10px", fontSize: 12 }} onClick={logout}>
      ログアウト
    </button>
  );
}
