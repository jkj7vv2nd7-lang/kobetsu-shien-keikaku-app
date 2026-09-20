"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API, api, authHeaders } from "../../../lib/api";
import { FIELDS, PII, TABLE_FIELDS, HANDOVER_FIELDS, REVIEW_FIELDS } from "../../../lib/fields";

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
  const [snips, setSnips] = useState<any[]>([]);
  const [snipId, setSnipId] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    const p = await api(`/api/plans/${id}`, { headers: authHeaders() });
    setPlan(p); setData(p.data || {});
  }
  useEffect(() => { load().catch(e => setMsg(e.message)); }, [id]);

  async function save() {
    try {
      const j = await api(`/api/plans/${id}`, { method: "PUT", headers: authHeaders(),
        body: JSON.stringify({ child_code: data.child_code || plan.child_code, grade: data.grade || plan.grade,
          class_type: data.class_type || plan.class_type, school: plan.school, data }) });
      setIssues(j.issues || []); setMsg(`保存。blocked=${j.blocked}`);
    } catch (e: any) { setMsg(`保存失敗: ${e.message}`); }
  }
  async function status(s: string) {
    try {
      const j = await api(`/api/plans/${id}/status`, { method: "POST", headers: authHeaders(), body: JSON.stringify({ status: s }) });
      setIssues(j.issues || []); setMsg(`状態→${j.status}`); load();
    } catch (e: any) { setMsg(`遷移失敗: ${e.message}`); }
  }
  async function draft() {
    try {
      const j = await api(`/api/ai/draft`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ kind: draftKind, plan_id: id }) });
      setAi(j.blocked ? `利用不可: ${JSON.stringify(j.issues || j).slice(0, 200)}` : (j.text || JSON.stringify(j)));
    } catch (e: any) { setMsg(`下書き失敗: ${e.message}`); }
  }
  function applyDraft() {
    if (!ai) return;
    setData({ ...data, [draftTarget]: ai });
    setMsg(`下書きを「${draftTarget}」に反映（要確認・修正）`);
  }
  async function polishField(k: string) {
    try {
      const j = await api(`/api/ai/check`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ facts: data[k] || "", plan_id: "" }) });
      setPolish({ ...polish, [k]: j.proposal });
      setIssues(j.issues || []);
    } catch (e: any) { setMsg(`推敲失敗: ${e.message}`); }
  }
  function applyPolish(k: string) {
    const p = polish[k];
    if (!p) return;
    setData({ ...data, [k]: p.rewritten });
    setMsg(`修正案を「${k}」に反映（要確認）`);
  }
  async function norishiro() {
    try {
      const j = await api(`/api/ai/norishiro`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ plan_id: id }) });
      setNori(j.proposals || []);
    } catch (e: any) { setMsg(`提案失敗: ${e.message}`); }
  }
  async function loadSnips() {
    try { setSnips(await api(`/api/plans/snippets/all`, { headers: authHeaders() })); } catch {}
  }
  function applySnip() {
    const s = snips.find(x => x.id === snipId);
    if (!s) return;
    setData({ ...data, [draftTarget]: ((data[draftTarget] || "") + "\n" + s.body).trim() });
    setMsg(`定型文「${s.title}」を追加（要確認・修正）`);
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
    try {
      const j = await api(`/api/ai/check`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ plan_id: id }) });
      setIssues(j.issues || []); setMsg(`表現・やさしい日本語チェック ${j.issues?.length}件`);
    } catch (e: any) { setMsg(`チェック失敗: ${e.message}`); }
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
      <h2>計画 {plan.child_code} <span className={`badge ${plan.status}`}>{plan.status}</span></h2>
      <p>{msg}</p>
      <div className="card">
        <h3>基本情報</h3>
        {[["child_code", "管理番号"], ["grade", "学年"], ["class_type", "在籍形態"]].map(([k, label]) => (
          <span key={k} style={{ marginRight: 12 }}>{label}：
            <input value={data[k] ?? plan[k] ?? ""} onChange={e => setData({ ...data, [k]: e.target.value })} style={{ width: 140 }} />
          </span>
        ))}
        {[["class_name", "組"], ["student_no", "出席番号"]].map(([k, label]) => (
          <span key={k} style={{ marginRight: 12 }}>{label}：
            <input value={data[k] || ""} onChange={e => setData({ ...data, [k]: e.target.value })} style={{ width: 80 }} />
          </span>
        ))}
      </div>
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
      <h3>見直し予定</h3>
      {REVIEW_FIELDS.map(([k, label]) => field(k, label))}
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
        <div style={{ marginTop: 8 }}>
          定型文：
          <select value={snipId} onChange={e => { setSnipId(e.target.value); if (snips.length === 0) loadSnips(); }} onFocus={loadSnips} style={{ maxWidth: 320 }}>
            <option value="">（選択）</option>
            {snips.map(s => <option key={s.id} value={s.id}>[{s.category || "共通"}] {s.title}</option>)}
          </select>
          <button className="btn" onClick={applySnip} style={{ marginLeft: 8 }}>反映先の欄に追加</button>
        </div>
        <details style={{ marginTop: 6 }}>
          <summary className="muted">定型文を新規登録</summary>
          <SnippetForm onDone={loadSnips} />
        </details>
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
      <Shares id={id} />
      <Consents id={id} />
      <Versions id={id} data={data} setData={setData} />
      <Comments id={id} />
      <Records id={id} />
    </main>
  );
}

function SnippetForm({ onDone }: { onDone: () => void }) {
  const [cat, setCat] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  async function save() {
    await api(`/api/plans/snippets/all`, { method: "POST", headers: authHeaders(),
      body: JSON.stringify({ category: cat, title, body }) });
    setCat(""); setTitle(""); setBody(""); onDone();
  }
  return (
    <div style={{ marginTop: 6 }}>
      <input value={cat} onChange={e => setCat(e.target.value)} placeholder="分類" style={{ width: 100 }} />
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="タイトル" style={{ marginLeft: 6, width: 200 }} />
      <input value={body} onChange={e => setBody(e.target.value)} placeholder="本文" style={{ marginLeft: 6, width: 300 }} />
      <button className="btn" onClick={save} style={{ marginLeft: 6 }}>登録</button>
    </div>
  );
}

function Shares({ id }: { id: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [days, setDays] = useState("7");
  const [msg, setMsg] = useState("");
  async function load() {
    try { setRows(await api(`/api/plans/${id}/shares`, { headers: authHeaders() })); } catch {}
  }
  useEffect(() => { load(); }, [id]);
  async function create() {
    try {
      const j = await api(`/api/plans/${id}/shares`, { method: "POST", headers: authHeaders(), body: JSON.stringify({ days: Number(days) || 7 }) });
      setMsg(`発行：${window.location.origin}/share/${j.token}（${j.days}日間）`);
      load();
    } catch (e: any) { setMsg(`発行失敗: ${e.message}`); }
  }
  async function revoke(sid: string) {
    await api(`/api/plans/${id}/shares/${sid}`, { method: "DELETE", headers: authHeaders() });
    load();
  }
  return (
    <div className="card noprint" style={{ marginTop: 12 }}>
      <h3>保護者共有リンク（提出以降・期限付き）</h3>
      <p className="muted">閲覧は記録されます。不要になったら取消してください。</p>
      <input value={days} onChange={e => setDays(e.target.value)} style={{ width: 60 }} /> 日間
      <button className="btn primary" onClick={create} style={{ marginLeft: 8 }}>発行</button>
      <p className="muted">{msg}</p>
      <ul>{rows.map(r => <li key={r.id}>
        {r.revoked ? "取消済" : `期限 ${new Date(r.expires_at * 1000).toLocaleDateString("ja-JP")}`}
        {!r.revoked && <button className="btn" onClick={() => revoke(r.id)} style={{ marginLeft: 8 }}>取消</button>}
      </li>)}</ul>
    </div>
  );
}

function Consents({ id }: { id: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [method, setMethod] = useState("対面");
  const [msg, setMsg] = useState("");
  async function load() {
    try { setRows(await api(`/api/plans/${id}/consents`, { headers: authHeaders() })); } catch {}
  }
  useEffect(() => { load(); }, [id]);
  async function add() {
    try {
      const j = await api(`/api/plans/${id}/consents`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ consenter: name, method }) });
      setMsg(`記録しました（内容ハッシュ ${j.plan_hash?.slice(0, 8)}…）。保護者確認も自動で付与されます`);
      setName(""); load();
    } catch (e: any) { setMsg(`記録失敗: ${e.message}`); }
  }
  return (
    <div className="card noprint" style={{ marginTop: 12 }}>
      <h3>合意の記録（電子確認・内容ハッシュ付き）</h3>
      <p className="muted">合意時点の内容をハッシュで特定します（法的電子署名ではありません）。</p>
      <ul>{rows.map(r => <li key={r.id}>{r.consenter}・{r.method}・{new Date(r.agreed_at * 1000).toLocaleString("ja-JP")}・ハッシュ{r.plan_hash?.slice(0, 8)}</li>)}</ul>
      <input value={name} onChange={e => setName(e.target.value)} placeholder="合意者氏名" />
      <select value={method} onChange={e => setMethod(e.target.value)} style={{ marginLeft: 8 }}>
        <option>対面</option><option>共有リンク</option><option>書面</option>
      </select>
      <button className="btn primary" onClick={add} style={{ marginLeft: 8 }}>記録</button>
      <p className="muted">{msg}</p>
    </div>
  );
}

function Versions({ id, data, setData }: { id: string; data: any; setData: any }) {
  const [rows, setRows] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  async function load() {
    try { setRows(await api(`/api/plans/${id}/versions`, { headers: authHeaders() })); } catch {}
  }
  useEffect(() => { load(); }, [id]);
  async function restore(v: number) {
    if (!confirm(`版${v}に復元しますか？（現在の内容は履歴に残ります）`)) return;
    try {
      await api(`/api/plans/${id}/restore/${v}`, { method: "POST", headers: authHeaders() });
      const p = await api(`/api/plans/${id}`, { headers: authHeaders() });
      setData(p.data || {}); setMsg(`版${v}に復元しました。内容を確認して保存してください`);
      load();
    } catch (e: any) { setMsg(`復元失敗: ${e.message}`); }
  }
  if (rows.length === 0) return null;
  return (
    <div className="card noprint" style={{ marginTop: 12 }}>
      <h3>変更履歴（直近{rows.length}件）</h3>
      <ul>{rows.map(r => <li key={r.version_no}>版{r.version_no}・{r.created_by}・{new Date(r.created_at * 1000).toLocaleString("ja-JP")}
        {r.changed_keys?.length > 0 && `（変更：${r.changed_keys.slice(0, 8).join("、")}）`}
        <button className="btn" onClick={() => restore(r.version_no)} style={{ marginLeft: 8 }}>復元</button></li>)}</ul>
      <p className="muted">{msg}</p>
    </div>
  );
}

function Comments({ id }: { id: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [body, setBody] = useState("");
  const [emsg, setEmsg] = useState("");
  async function load() {
    try { setRows(await api(`/api/plans/${id}/comments`, { headers: authHeaders() })); } catch {}
  }
  useEffect(() => { load(); }, [id]);
  async function post() {
    try {
      await api(`/api/plans/${id}/comments`, { method: "POST", headers: authHeaders(), body: JSON.stringify({ body }) });
      setBody(""); setEmsg(""); load();
    } catch (e: any) { setEmsg(`投稿失敗: ${e.message}`); }
  }
  return (
    <div className="card noprint" style={{ marginTop: 12 }}>
      <h3>支援会議メモ（関係者共有用）</h3>
      <ul>{rows.map(r => <li key={r.id}><b>{r.author}</b>（{new Date(r.created_at * 1000).toLocaleString("ja-JP")}）：{r.body}</li>)}</ul>
      <textarea value={body} onChange={e => setBody(e.target.value)} rows={2} style={{ width: "100%" }} placeholder="申送り・相談内容（個人情報の書込み注意）" />
      <div style={{ marginTop: 6 }}><button className="btn primary" onClick={post}>投稿</button> <span className="muted">{emsg}</span></div>
    </div>
  );
}

function Records({ id }: { id: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [date, setDate] = useState("");
  const [goal, setGoal] = useState("");
  const [body, setBody] = useState("");
  const [emsg, setEmsg] = useState("");
  async function load() {
    try { setRows(await api(`/api/plans/${id}/records`, { headers: authHeaders() })); } catch {}
  }
  useEffect(() => { load(); }, [id]);
  async function post() {
    try {
      await api(`/api/plans/${id}/records`, { method: "POST", headers: authHeaders(),
        body: JSON.stringify({ date, goal_ref: goal, body }) });
      setDate(""); setGoal(""); setBody(""); setEmsg(""); load();
    } catch (e: any) { setEmsg(`記録失敗: ${e.message}`); }
  }
  return (
    <div className="card noprint" style={{ marginTop: 12 }}>
      <h3>日々の指導記録（目標と紐付け・評価の積み重ね）</h3>
      <ul>{rows.map(r => <li key={r.id}>{r.date}［{r.goal_ref || "目標共通"}］{r.body}（{r.author}）</li>)}</ul>
      <input value={date} onChange={e => setDate(e.target.value)} placeholder="日付 YYYY-MM-DD" style={{ width: 160 }} />
      <input value={goal} onChange={e => setGoal(e.target.value)} placeholder="関連目標（例：短期目標1）" style={{ marginLeft: 8, width: 220 }} />
      <textarea value={body} onChange={e => setBody(e.target.value)} rows={2} style={{ width: "100%", marginTop: 6 }} placeholder="できたこと・兆し・工夫（個人内評価の視点で）" />
      <div style={{ marginTop: 6 }}><button className="btn primary" onClick={post}>記録</button> <span className="muted">{emsg}</span></div>
    </div>
  );
}
