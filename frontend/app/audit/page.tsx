"use client";
import { useEffect, useState } from "react";
import { API, api, authHeaders, token } from "../../lib/api";

export default function Audit() {
  const [rows, setRows] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    api("/api/audit?limit=200", { headers: authHeaders() }).then(setRows).catch(e => setMsg(`閲覧不可（管理職のみ）: ${e.message}`));
  }, []);
  async function exp() {
    const r = await fetch(`${API}/api/audit/export`, { headers: { Authorization: `Bearer ${token()}` } });
    if (!r.ok) { setMsg("出力失敗"); return; }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await r.blob()); a.download = "audit.csv"; a.click();
  }
  return (
    <main>
      <h2>監査ログ</h2>
      <p className="muted">{msg || "操作・AI利用・出力の記録（管理職のみ閲覧可）"}</p>
      <p className="noprint"><button className="btn" onClick={exp}>CSV出力</button></p>
      <table className="grid"><thead><tr><th>ID</th><th>日時</th><th>ユーザ</th><th>操作</th><th>対象</th><th>詳細</th></tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td>{r.id}</td><td>{new Date(r.at * 1000).toLocaleString("ja-JP")}</td>
          <td>{r.username}</td><td>{r.action}</td><td>{r.target}</td><td>{r.detail}</td>
        </tr>)}</tbody></table>
    </main>
  );
}
