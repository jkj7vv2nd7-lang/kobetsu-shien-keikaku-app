"use client";
import { useEffect, useState } from "react";
import { API, api, authHeaders, token } from "../../lib/api";
import { FIELDS } from "../../lib/fields";

const ALL_IDS = new Set([...FIELDS.map(f => f[0])]);

export default function Templates() {
  const [list, setList] = useState<any[]>([]);
  const [slots, setSlots] = useState<any[]>([]);
  const [tid, setTid] = useState("");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [planId, setPlanId] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [msg, setMsg] = useState("");

  async function load() {
    try { setList(await api("/api/templates", { headers: authHeaders() })); } catch (e: any) { setMsg(e.message); }
  }
  useEffect(() => { load(); }, []);

  async function upload(e: any) {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const r = await fetch(`${API}/api/templates/upload`, { method: "POST",
      headers: { Authorization: `Bearer ${token()}` }, body: fd });
    const j = await r.json();
    if (j.template_id) { setTid(j.template_id); setSlots(j.slots || []); setMapping({}); setPreview(null); setMsg(`${j.template_id}: ${j.slots?.length} slot`); load(); }
    else setMsg(JSON.stringify(j).slice(0, 300));
  }
  async function open(tid: string) {
    setTid(tid);
    const j = await api(`/api/templates/${tid}/slots`, { headers: authHeaders() });
    setSlots(j.slots || []); setMapping(j.mapping || {}); setPreview(null);
  }
  function autoMap() {
    const m = { ...mapping };
    let n = 0;
    for (const s of slots) {
      if (!m[s.slot_id] && s.field_hint && ALL_IDS.has(s.field_hint)) { m[s.slot_id] = s.field_hint; n++; }
    }
    setMapping(m); setMsg(`候補を${n}件自動割当（要確認）`);
  }
  async function saveMapping() {
    await api(`/api/templates/${tid}/mapping`, { method: "POST", headers: authHeaders(), body: JSON.stringify({ mapping }) });
    setMsg("マッピング保存");
  }
  async function doPreview() {
    try {
      const j = await api(`/api/templates/${tid}/preview`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ plan_id: planId || undefined, data: planId ? {} : {}, mapping }) });
      setPreview(j); setMsg(`プレビュー：空欄${j.slots.filter((s: any) => s.empty).length}件・未割当${j.unmapped.length}件`);
    } catch (e: any) { setMsg(`プレビュー失敗: ${e.message}`); }
  }
  async function pdf() {
    try {
      const r = await fetch(`${API}/api/templates/${tid}/pdf`, { method: "POST",
        headers: { ...authHeaders() }, body: JSON.stringify({ plan_id: planId || undefined, data: planId ? {} : {}, mapping }) });
      if (!r.ok) { setMsg(`PDF失敗: ${(await r.text()).slice(0, 200)}`); return; }
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = `${tid}.pdf`; a.click();
      setMsg("PDFを取得しました");
    } catch (e: any) { setMsg(`PDF失敗: ${e.message}`); }
  }
  async function merge() {
    try {
      const j = await api(`/api/templates/${tid}/merge`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ plan_id: planId || undefined, data: planId ? {} : {}, mapping }) });
      setMsg(`出力: ${j.output}`);
      setPreview({ ...preview, download: `${API}${j.download}`, output: j.output });
    } catch (e: any) { setMsg(`差し込み失敗: ${e.message}`); }
  }
  return (
    <main>
      <h2>様式・差し込み</h2>
      <p className="muted">{msg}</p>
      <div className="card">
        <h3>自治体様式の取込（txt/docx/xlsx）</h3>
        <input type="file" accept=".txt,.docx,.xlsx" onChange={upload} />
      </div>
      <div className="card">
        <h3>登録済み</h3>
        <ul>{list.map(t => <li key={t.id}>
          <button className="btn" onClick={() => open(t.id)}>{t.id}</button> {t.label || t.filename}
        </li>)}</ul>
      </div>
      {tid && (<>
        <div className="card">
          <h3>マッピング：{tid}（{slots.length} slot）</h3>
          <input value={planId} onChange={e => setPlanId(e.target.value)} placeholder="plan_id（計画から差し込み）" style={{ width: 260 }} />
          <div style={{ marginTop: 8 }}>
            <button className="btn" onClick={autoMap}>候補を自動割当</button>
            <button className="btn primary" onClick={saveMapping} style={{ marginLeft: 8 }}>保存</button>
            <button className="btn" onClick={doPreview} style={{ marginLeft: 8 }}>プレビュー</button>
            <button className="btn primary" onClick={merge} style={{ marginLeft: 8 }}>Excel出力</button>
            <button className="btn" onClick={pdf} style={{ marginLeft: 8 }}>PDF出力（新潟様式）</button>
          </div>
        </div>
        {preview?.slots && (
          <div className="card">
            <h3>プレビュー {preview.blocked ? "（検証エラーあり・出力不可）" : ""}</h3>
            {preview.download && <p><a href={preview.download}>出力ファイルを取得（{preview.output}）</a> → Excelで開いて印刷→PDF</p>}
            {(preview.unmapped?.length > 0) && <p className="issue-warn">未割当slot：{preview.unmapped.slice(0, 10).join(", ")}{preview.unmapped.length > 10 ? "…" : ""}</p>}
            <table className="grid"><thead><tr><th>セル</th><th>項目</th><th>値</th><th>状態</th></tr></thead>
              <tbody>{preview.slots.slice(0, 120).map((s: any, i: number) => (
                <tr key={i}><td><code>{s.sheet ? `${s.sheet}!${s.cell}` : s.slot_id}</code><br /><span className="muted">{s.label}</span></td>
                  <td>{s.field}</td><td>{String(s.value || "").slice(0, 60)}</td>
                  <td>{s.empty ? <span className="issue-warn">空欄</span> : "○"}</td></tr>
              ))}</tbody></table>
            {preview.issues?.length > 0 && (<ul>{preview.issues.map((x: any, n: number) => (
              <li key={n} className={x.level === "error" ? "issue-err" : x.level === "warn" ? "issue-warn" : "issue-info"}>[{x.level}/{x.rule}] {x.msg || x.hit}</li>))}</ul>)}
          </div>
        )}
        <div className="card">
          <h3>割当の編集</h3>
          {slots.slice(0, 100).map((s, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <code>{s.slot_id}</code> {s.label}
              <select value={typeof mapping[s.slot_id] === "string" ? mapping[s.slot_id] : ""} onChange={e => setMapping({ ...mapping, [s.slot_id]: e.target.value })} style={{ marginLeft: 8 }}>
                <option value="">（未割当）</option>
                {FIELDS.map(([k, label]) => <option key={k} value={k}>{k}：{label}</option>)}
              </select>
            </div>
          ))}
        </div>
      </>)}
    </main>
  );
}
