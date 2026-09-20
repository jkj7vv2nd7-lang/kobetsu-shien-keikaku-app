"use client";
import { useEffect, useState } from "react";
import { api, authHeaders } from "../../lib/api";

export default function Plans() {
  const [plans, setPlans] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ child_code: "S-2026-001", grade: "小4", class_type: "特別支援学級", school: "" });
  async function load() {
    try { setPlans(await api("/api/plans", { headers: authHeaders() })); setMsg(""); }
    catch (e: any) { setMsg(`読込失敗（要ログイン）: ${e.message}`); }
  }
  useEffect(() => { load(); }, []);
  async function duplicate(id: string) {
    try {
      const j = await api(`/api/plans/${id}/duplicate`, { method: "POST", headers: authHeaders() });
      setMsg(`複製しました（年度更新用）: ${j.id}`);
      load();
    } catch (e: any) { setMsg(`複製失敗: ${e.message}`); }
  }
  async function create() {
    try {
      const j = await api("/api/plans", { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ ...form, data: { profile_strengths: "見通しがあると集中", profile_needs: "急な変更に不安" } }) });
      setMsg(`作成 ${j.id}`);
      load();
    } catch (e: any) { setMsg(`作成失敗: ${e.message}`); }
  }
  return (
    <main>
      <h2>計画一覧</h2>
      <p className="muted">{msg}</p>
      <div className="card">
        <h3>新規作成（管理番号制・実名は計画内の氏名欄へ）</h3>
        {(["child_code", "grade", "class_type", "school"] as const).map(k => (
          <input key={k} value={(form as any)[k]} onChange={e => setForm({ ...form, [k]: e.target.value })}
            placeholder={k} style={{ marginRight: 8, width: 130 }} />
        ))}
        <button className="btn primary" onClick={create}>新規作成</button>
      </div>
      <div className="card">
        <table className="grid"><thead><tr><th>管理番号</th><th>学年</th><th>状態</th><th></th></tr></thead>
          <tbody>{plans.map(p => <tr key={p.id}>
            <td>{p.child_code}</td><td>{p.grade}</td>
            <td><span className={`badge ${p.status}`}>{p.status}</span></td>
            <td><a href={`/plans/${p.id}`}>開く</a> <button className="btn" onClick={() => duplicate(p.id)} style={{ marginLeft: 8 }}>複製（年度更新）</button></td>
          </tr>)}</tbody></table>
      </div>
    </main>
  );
}
