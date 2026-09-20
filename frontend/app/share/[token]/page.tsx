"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API } from "../../../lib/api";

export default function ShareView() {
  const { token } = useParams() as { token: string };
  const [plan, setPlan] = useState<any>(null);
  const [msg, setMsg] = useState("読込中…");
  useEffect(() => {
    fetch(`${API}/api/share/${token}`).then(async r => {
      if (!r.ok) { setMsg(r.status === 410 ? "このリンクは期限切れ・取消済みです。担任にお尋ねください。" : "リンクが無効です。"); return; }
      setPlan(await r.json()); setMsg("");
    }).catch(() => setMsg("読込失敗"));
  }, [token]);
  if (!plan) return <main style={{ maxWidth: 720, margin: "24px auto", padding: 16 }}><p>{msg}</p></main>;
  const d = plan.data || {};
  const show = (label: string, v: any) => v ? <p><b>{label}：</b>{String(v)}</p> : null;
  return (
    <main style={{ maxWidth: 720, margin: "24px auto", padding: 16, fontFamily: "sans-serif" }}>
      <h1>個別の計画のご説明（{plan.child_code}）</h1>
      <p>担任からの共有です。ご不明点は学校へお尋ねください。</p>
      {show("学年", plan.grade)}
      {show("長期目標", d.guidance_long_goal || d.support_long_goal)}
      {show("短期目標", d.short_goal_1)}
      {show("具体的な支援", d.supports)}
      {show("評価の時期・方法", d.eval_method)}
      {show("願いへの対応", d.guardian_wish ? `保護者の願い「${d.guardian_wish}」を踏まえています` : "")}
      <button onClick={() => window.print()}>印刷</button>
    </main>
  );
}
