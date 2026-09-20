"use client";
import { useState } from "react";
import { API } from "../../lib/api";

export default function Login() {
  const [u, setU] = useState("teacher");
  const [p, setP] = useState("teacher123");
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [warn, setWarn] = useState("");
  const [needMfa, setNeedMfa] = useState(false);
  async function login() {
    const r = await fetch(`${API}/api/auth/login`, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: p }) });
    const j = await r.json();
    if (j.mfa_required) { setNeedMfa(true); setMsg("確認コードを入力してください"); }
    else if (j.token) {
      localStorage.setItem("token", j.token);
      if (j.must_change_pw) { setWarn("初期パスワードのままです。下の欄で必ず変更してください。"); }
      else window.location.href = "/";
    }
    else setMsg(`失敗: ${JSON.stringify(j)}`);
  }
  async function mfa() {
    const r = await fetch(`${API}/api/auth/mfa/login`, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: p, code }) });
    const j = await r.json();
    if (j.token) { localStorage.setItem("token", j.token); window.location.href = "/"; }
    else setMsg(`失敗: ${JSON.stringify(j)}`);
  }
  return (
    <main>
      <h2>ログイン</h2>
      <p>試作ID: admin/admin123, manager/manager123, teacher/teacher123, viewer/viewer123</p>
      <input value={u} onChange={e => setU(e.target.value)} placeholder="ユーザ" />
      <input value={p} onChange={e => setP(e.target.value)} type="password" placeholder="パスワード" style={{ marginLeft: 8 }} />
      <button onClick={login} style={{ marginLeft: 8 }}>ログイン</button>
      {needMfa && (<div style={{ marginTop: 8 }}>
        <input value={code} onChange={e => setCode(e.target.value)} placeholder="確認コード（6桁）" />
        <button onClick={mfa} style={{ marginLeft: 8 }}>確認</button>
      </div>)}
      <p>{msg}</p>
      {warn && <p className="issue-err">{warn}</p>}
      <MfaSetup />
      <PwChange />
      <p style={{ fontSize: 13 }}>MFA設定はログイン後に「確認コード発行」から（認証アプリに手動登録）。管理職は有効化を推奨。</p>
    </main>
  );
}

function PwChange() {
  const [o, setO] = useState("");
  const [n, setN] = useState("");
  const [msg, setMsg] = useState("");
  async function change() {
    const t = localStorage.getItem("token") || "";
    const r = await fetch(`${API}/api/auth/password`, { method: "POST",
      headers: { Authorization: `Bearer ${t}`, "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: o, new_password: n }) });
    const j = await r.json();
    setMsg(j.ok ? "変更しました" : `失敗: ${JSON.stringify(j).slice(0, 200)}`);
  }
  return (
    <div style={{ marginTop: 16, borderTop: "1px solid #ddd", paddingTop: 8 }}>
      <h3>パスワード変更（8文字以上）</h3>
      <input value={o} onChange={e => setO(e.target.value)} type="password" placeholder="現在のパスワード" />
      <input value={n} onChange={e => setN(e.target.value)} type="password" placeholder="新しいパスワード" style={{ marginLeft: 8 }} />
      <button onClick={change} style={{ marginLeft: 8 }}>変更</button>
      <p style={{ fontSize: 13 }}>{msg}</p>
    </div>
  );
}
function MfaSetup() {
  const [info, setInfo] = useState("");
  const [vcode, setVcode] = useState("");
  async function setup() {
    const t = localStorage.getItem("token") || "";
    const r = await fetch(`${API}/api/auth/mfa/setup`, { method: "POST", headers: { Authorization: `Bearer ${t}` } });
    const j = await r.json();
    setInfo(j.secret ? `秘密鍵: ${j.secret} ／ 登録URL: ${j.otpauth_url}` : JSON.stringify(j));
  }
  async function verify() {
    const t = localStorage.getItem("token") || "";
    const r = await fetch(`${API}/api/auth/mfa/verify`, { method: "POST",
      headers: { Authorization: `Bearer ${t}`, "Content-Type": "application/json" }, body: JSON.stringify({ code: vcode }) });
    const j = await r.json();
    setInfo(`検証: ${j.ok ? "成功" : "失敗"}`);
  }
  return (
    <div style={{ marginTop: 16, borderTop: "1px solid #ddd", paddingTop: 8 }}>
      <h3>MFA（2段階認証）設定</h3>
      <button onClick={setup}>確認コード発行</button>
      <input value={vcode} onChange={e => setVcode(e.target.value)} placeholder="確認コード" style={{ marginLeft: 8 }} />
      <button onClick={verify} style={{ marginLeft: 8 }}>有効化の確認</button>
      <p style={{ fontSize: 13, wordBreak: "break-all" }}>{info}</p>
    </div>
  );
}
