"use client";
import { useEffect, useState } from "react";
import { API, api, authHeaders } from "../../lib/api";

export default function Plans() {
  const [plans, setPlans] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [filter, setFilter] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState({ child_code: "S-2026-001", grade: "小4", class_type: "特別支援学級", school: "" });
  async function load(query?: string) {
    try { setPlans(await api(`/api/plans${query ? `?q=${encodeURIComponent(query)}` : ""}`, { headers: authHeaders() })); setMsg(""); }
    catch (e: any) { setMsg(`読込失敗（要ログイン）: ${e.message}`); }
  }
  useEffect(() => { load(); }, []);
  async function bulkPdf() {
    const ids = Object.keys(sel).filter(k => sel[k]);
    if (ids.length === 0) { setMsg("選択がありません"); return; }
    try {
      const r = await fetch(`${API}/api/templates/bulk-pdf`, { method: "POST",
        headers: { ...authHeaders() }, body: JSON.stringify({ plan_ids: ids }) });
      if (!r.ok) { setMsg(`一括PDF失敗: ${(await r.text()).slice(0, 200)}`); return; }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await r.blob()); a.download = "bulk.pdf"; a.click();
      setMsg(`${ids.length}件を一括PDF化しました`);
    } catch (e: any) { setMsg(`一括PDF失敗: ${e.message}`); }
  }
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
        <h3>名簿一括取込（年度当初・管理職用 CSV: 管理番号,学年,在籍,学校）</h3>
        <input type="file" accept=".csv" onChange={async e => {
          const f = e.target.files?.[0];
          if (!f) return;
          const text = await f.text();
          const rows = text.split(/\r?\n/).slice(1).map(l => l.split(",").map(s => s.trim())).filter(c => c[0])
            .map(c => ({ child_code: c[0], grade: c[1] || "", class_type: c[2] || "", school: c[3] || "" }));
          try {
            const j = await api("/api/admin/roster", { method: "POST", headers: authHeaders(), body: JSON.stringify({ rows }) });
            setMsg(`取込：作成${j.created.length}件・スキップ${j.skipped.length}件`);
            load();
          } catch (err: any) { setMsg(`取込失敗: ${err.message}`); }
        }} />
      </div>
      <div className="card">
        検索：<input value={q} onChange={e => setQ(e.target.value)} placeholder="管理番号・学年" style={{ width: 180 }} />
        <button className="btn" onClick={() => load(q)} style={{ marginLeft: 8 }}>検索</button>
        <button className="btn primary" onClick={bulkPdf} style={{ marginLeft: 8 }}>選択を一括PDF</button>
        絞り込み：
        <select value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="">すべて</option>
          <option value="draft">下書き</option>
          <option value="review">提出中</option>
          <option value="approved">承認済</option>
        </select>
        <table className="grid" style={{ marginTop: 8 }}><thead><tr><th></th><th>管理番号</th><th>学年</th><th>状態</th><th></th></tr></thead>
          <tbody>{plans.filter(p => !filter || p.status === filter).map(p => <tr key={p.id}>
            <td><input type="checkbox" checked={!!sel[p.id]} onChange={e => setSel({ ...sel, [p.id]: e.target.checked })} /></td>
            <td>{p.child_code}</td><td>{p.grade}</td>
            <td><span className={`badge ${p.status}`}>{p.status}</span></td>
            <td><a href={`/plans/${p.id}`}>開く</a> <button className="btn" onClick={() => duplicate(p.id)} style={{ marginLeft: 8 }}>複製（年度更新）</button></td>
          </tr>)}</tbody></table>
      </div>
    </main>
  );
}
