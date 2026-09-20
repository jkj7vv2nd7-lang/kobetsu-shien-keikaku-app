"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API, api, authHeaders } from "../../../lib/api";
import { FIELDS, PII, TABLE_FIELDS, HANDOVER_FIELDS } from "../../../lib/fields";

export default function PlanDetail() {
  const { id } = useParams() as { id: string };
  const [plan, setPlan] = useState<any>(null);
  const [data, setData] = useState<Record<string, any>>({});
  const [issues, setIssues] = useState<any[]>([]);
  const [ai, setAi] = useState("");
  const [draftKind, setDraftKind] = useState("guidance_long_goal");
  const [draftTarget, setDraftTarget] = useState("guidance_long_goal");
  const [polish, setPolish] = useState<Record<string, any>>({});
  const [nori, setNori] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  async function load() {
    const p = await api(`/api/plans/${id}`, { headers: authHeaders() });
    setPlan(p); setData(p.data || {});
  }
  useEffect(() => { load().catch(e => setMsg(e.message)); }, [id]);

  async function save() {
    const j = await api(`/api/plans/${id}`, { method: "PUT", headers: authHeaders(),
      body: JSON.stringify({ child_code: data.child_code || plan.child_code, grade: data.grade || plan.grade,
        class_type: data.class_type || plan.class_type, school: plan.school, data }) });
    setIssues(j.issues || []); setMsg(`保存。blocked=${j.blocked}`);
  }
  async function status(s: string) {
    try {
      const j = await api(`/api/plans/${id}/status`, { method: "POST", headers: authHeaders(), body: JSON.stringify({ status: s }) });
      setIssues(j.issues || []); setMsg(`状態→${j.status}`); load();
    } catch (e: any) { setMsg(`遷移失敗: ${e.message}`); }
  }
  async function draft() {
    const j = await api(`/api/ai/draft`, { method: "POST", headers: authHeaders(),
      body: JSON.stringify({ kind: draftKind, plan_id: id }) });
    setAi(j.text || JSON.stringify(j));
  }
  function applyDraft() {
    if (!ai) return;
    setData({ ...data, [draftTarget]: ai });
    setMsg(`下書きを「${draftTarget}」に反映（要確認・修正）`);
  }
  async function polishField(k: string) {
    const j = await api(`/api/ai/check`, { method: "POST", headers: authHeaders(),
      body: JSON.stringify({ facts: data[k] || "", plan_id: "" }) });
    setPolish({ ...polish, [k]: j.proposal });
    setIssues(j.issues || []);
  }
  function applyPolish(k: string) {
    const p = polish[k];
    if (!p) return;
    setData({ ...data, [k]: p.rewritten });
    setMsg(`修正案を「${k}」に反映（要確認）`);
  }
  async function norishiro() {
    const j = await api(`/api/ai/norishiro`, { method: "POST", headers: authHeaders(),
      body: JSON.stringify({ plan_id: id }) });
    setNori(j.proposals || []);
  }
  function applyNori(p: any) {
    setData({ ...data, start_ease: ((data.start_ease || "") + "\n" + p.body).trim() });
    setMsg("糊しろ案を反映（要確認・修正）");
  }
  async function handover(fmt: string) {
    const t = localStorage.getItem("token") || "";
    const r = await fetch(`${API}/api/plans/${id}/handover?format=${fmt}`, { headers: { Authorization: `Bearer ${t}` } });
    if (!r.ok) { setMsg(`引継ぎ出力失敗: ${(await r.text()).slice(0, 200)}`); return; }
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `handover.${fmt}`; a.click();
    setMsg(`引継ぎ${fmt}を取得（要・保護者同意）`);
  }
  async function check() {
    const j = await api(`/api/ai/check`, { method: "POST", headers: authHeaders(),
      body: JSON.stringify({ plan_id: id }) });
    setIssues(j.issues || []); setMsg(`表現・やさしい日本語チェック ${j.issues?.length}件`);
  }
  if (!plan) return <p>{msg || "読込中"}</p>;
  const field = (k: string, label: string) => (
    <div key={k} style={{ marginBottom: 8 }}>
      <label style={{ display: "block", fontSize: 13, color: "#444" }}>
        {label}：{k}{PII.has(k) && <span style={{ color: "#a00" }}>［個人情報・AI送信外］</span>}
      </label>
      <textarea value={data[k] || ""} onChange={e => setData({ ...data, [k]: e.target.value })}
        rows={k.includes("goal") || k.includes("supports") ? 3 : 2} style={{ width: "100%" }} />
      <div className="noprint">
        <button className="btn" onClick={() => polishField(k)}>AI推敲</button>
        {polish[k]?.rewritten && polish[k].rewritten !== (data[k] || "") && (
          <span> <button className="btn primary" onClick={() => applyPolish(k)}>修正案を反映</button>
          <span className="muted">（{polish[k].applied?.length || 0}件置換）</span></span>
        )}
      </div>
      {polish[k]?.rewritten && polish[k].rewritten !== (data[k] || "") && (
        <pre className="ai">{polish[k].rewritten}</pre>
      )}
    </div>
  );
  return (
    <main>
      <h2>計画 {plan.child_code}（{plan.status}）</h2>
      <p>{msg}</p>
      <p style={{ fontSize: 13, color: "#555" }}>［個人情報］印の項目は印刷時のみ使用し、AIには送信されません。文章は短い文・ですます調で（保存時に自動チェック）。</p>
      <h3>基本・文科省項目</h3>
      {FIELDS.slice(0, 17).map(([k, label]) => field(k, label))}
      <h3>新潟様式項目</h3>
      {FIELDS.slice(17).map(([k, label]) => field(k, label))}
      <h3>指導表（実態・目標・方法・評価×9行）</h3>
      {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => (
        <div key={n} style={{ borderTop: "1px solid #ddd", paddingTop: 8 }}>
          <b>行{n}</b>
          {TABLE_FIELDS(n).map(([k, label]) => field(k, label))}
        </div>
      ))}
      <h3>引継ぎ・同意（進学・進級時）</h3>
      <p style={{ fontSize: 13, color: "#555" }}>引継ぎ先への情報提供は保護者の同意が前提です（ハンドブックp21）。</p>
      {HANDOVER_FIELDS.map(([k, label]) => field(k, label))}
      <label><input type="checkbox" checked={!!data.guardian_confirmed}
        onChange={e => setData({ ...data, guardian_confirmed: e.target.checked })} /> 保護者確認済み</label>
      <div style={{ marginTop: 12 }} className="noprint">
        <button className="btn primary" onClick={save}>保存・検証</button>
        <button className="btn" onClick={() => status("review")} style={{ marginLeft: 8 }}>提出(review)</button>
        <button className="btn" onClick={() => status("approved")} style={{ marginLeft: 8 }}>承認(approved)</button>
        <button className="btn" onClick={() => window.print()} style={{ marginLeft: 8 }}>印刷</button>
      </div>
      <div className="card noprint" style={{ marginTop: 12 }}>
        <h3>AI支援（匿名化後のみ送信・要確認）</h3>
        <div>
          <select value={draftKind} onChange={e => setDraftKind(e.target.value)}>
            <option value="guidance_long_goal">長期目標の下書き</option>
            <option value="short_goal">短期目標の下書き</option>
            <option value="summary">引継ぎ要約</option>
          </select>
          <select value={draftTarget} onChange={e => setDraftTarget(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="guidance_long_goal">反映先：指導・長期目標</option>
            <option value="short_goal_1">反映先：短期目標1</option>
            <option value="short_goal_2">反映先：短期目標2</option>
            <option value="supports">反映先：具体的支援</option>
            <option value="eval_handover">反映先：評価・引継ぎ</option>
            <option value="start_ease">反映先：糊しろ</option>
          </select>
          <button className="btn" onClick={draft} style={{ marginLeft: 8 }}>下書き生成</button>
          {ai && <button className="btn primary" onClick={applyDraft} style={{ marginLeft: 8 }}>文案を反映</button>}
          <button className="btn" onClick={check} style={{ marginLeft: 8 }}>全体チェック</button>
          <button className="btn" onClick={norishiro} style={{ marginLeft: 8 }}>糊しろ提案</button>
          <button className="btn" onClick={() => handover("csv")} style={{ marginLeft: 8 }}>引継ぎCSV</button>
          <button className="btn" onClick={() => handover("json")} style={{ marginLeft: 8 }}>引継ぎJSON</button>
        </div>
        {ai && <pre className="ai">{ai}</pre>}
        {nori.length > 0 && (
          <div style={{ marginTop: 8 }}>{nori.map((p: any, i: number) => (
            <div key={i} className="card" style={{ marginBottom: 8 }}>
              <b>{p.title}</b>
              <pre className="ai">{p.body}</pre>
              <span className="muted">{p.reason}</span><br />
              <button className="btn primary" onClick={() => applyNori(p)} style={{ marginTop: 6 }}>糊しろ欄に反映</button>
            </div>))}</div>
        )}
      </div>
      <ul>{issues.map((i, n) => <li key={n}>[{i.level}/{i.rule}] {i.msg || i.hit}</li>)}</ul>
      <Comments id={id} />
    </main>
  );
}

function Comments({ id }: { id: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [body, setBody] = useState("");
  async function load() {
    try { setRows(await api(`/api/plans/${id}/comments`, { headers: authHeaders() })); } catch {}
  }
  useEffect(() => { load(); }, [id]);
  async function post() {
    await api(`/api/plans/${id}/comments`, { method: "POST", headers: authHeaders(), body: JSON.stringify({ body }) });
    setBody(""); load();
  }
  return (
    <div className="card noprint" style={{ marginTop: 12 }}>
      <h3>支援会議メモ（関係者共有用）</h3>
      <ul>{rows.map(r => <li key={r.id}><b>{r.author}</b>（{new Date(r.created_at * 1000).toLocaleString("ja-JP")}）：{r.body}</li>)}</ul>
      <textarea value={body} onChange={e => setBody(e.target.value)} rows={2} style={{ width: "100%" }} placeholder="申送り・相談内容（個人情報の書込み注意）" />
      <div style={{ marginTop: 6 }}><button className="btn primary" onClick={post}>投稿</button></div>
    </div>
  );
}
