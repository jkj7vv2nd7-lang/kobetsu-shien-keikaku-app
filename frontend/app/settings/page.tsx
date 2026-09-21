"use client";
import { useEffect, useState } from "react";
import { api, authHeaders } from "../../lib/api";

export default function Settings() {
  const [rows, setRows] = useState<any[]>([]);
  const [uname, setUname] = useState("");
  const [label, setLabel] = useState("");
  const [msg, setMsg] = useState("");
  const [last, setLast] = useState("");
  async function load() {
    try { setRows(await api("/api/auth/keys", { headers: authHeaders() })); }
    catch (e: any) { setMsg(`閲覧不可（管理職のみ）: ${e.message}`); }
  }
  useEffect(() => { load(); }, []);
  async function issue() {
    try {
      const j = await api("/api/auth/keys", { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ username: uname, label }) });
      setLast(j.api_key); setMsg("発行しました。下のキーはこの画面でのみ表示されます");
      load();
    } catch (e: any) { setMsg(`発行失敗: ${e.message}`); }
  }
  async function revoke(id: string) {
    await api(`/api/auth/keys/${id}`, { method: "DELETE", headers: authHeaders() });
    load();
  }
  return (
    <main>
      <h2>設定（管理職）</h2>
      <div className="card">
        <h3>APIキー発行（使用者本人のキー）</h3>
        <input value={uname} onChange={e => setUname(e.target.value)} placeholder="ユーザ名" />
        <input value={label} onChange={e => setLabel(e.target.value)} placeholder="用途メモ" style={{ marginLeft: 8 }} />
        <button className="btn primary" onClick={issue} style={{ marginLeft: 8 }}>発行</button>
        {last && <p><code>{last}</code></p>}
        <p className="muted">{msg}</p>
        <table className="grid"><thead><tr><th>ユーザ</th><th>用途</th><th>状態</th><th></th></tr></thead>
          <tbody>{rows.map(r => <tr key={r.id}>
            <td>{r.username}</td><td>{r.label}</td><td>{r.revoked ? "取消済" : "有効"}</td>
            <td>{!r.revoked && <button className="btn" onClick={() => revoke(r.id)}>取消</button>}</td>
          </tr>)}</tbody></table>
      </div>
      <div className="card">
        <h3>簡易運用モード</h3>
        <p className="muted">バックエンドの <code>SIMPLE_MODE=1</code> で、初期PW警告なし・セッション30日・MFA要求なしになります。委員会許可など組織の承認がある場合に使用してください（既定OFF）。</p>
      </div>
    </main>
  );
}
