"use client";
import { useEffect, useState } from "react";
import { api, authHeaders } from "../lib/api";

const SCHEDULE = [
  ["3〜4月", "相談・引継ぎ：前任者・他機関から引継ぎ、保護者の願いを聞き取る"],
  ["4月", "実態把握：行動観察・聞き取りで強みと課題、手立てを検討"],
  ["4月", "信頼関係・合意形成：面談で共通理解"],
  ["4〜5月末", "作成：3年後を見通した長期目標、校内委員会で検討"],
  ["5月末まで", "保護者への説明・合意形成"],
  ["随時", "支援の実施：ズレがあれば柔軟に修正"],
  ["年度末・学期末", "評価と次年度確認：支援会議で評価、次年度へ引継ぎ"],
] as const;

export default function Home() {
  const [s, setS] = useState<any>(null);
  useEffect(() => { api("/api/stats/summary", { headers: authHeaders() }).then(setS).catch(() => {}); }, []);
  return (
    <main>
      <h1>個別支援・指導計画</h1>
      <p className="muted">文科省参考様式＋新潟県様式対応。実名は管理番号で扱い、AIには匿名化後のみ送信します。</p>
      {s ? (
        <div className="card">
          <h3>進捗（全{s.total}件・要修正{s.blocked}件）</h3>
          <p>
            <span className="badge draft">下書き {s.by_status?.draft || 0}</span>{" "}
            <span className="badge review">提出中 {s.by_status?.review || 0}</span>{" "}
            <span className="badge approved">承認済 {s.by_status?.approved || 0}</span>
          </p>
          <ul>{(s.recent || []).map((p: any) => (
            <li key={p.id}><a href={`/plans/${p.id}`}>{p.child_code} / {p.grade}</a> <span className={`badge ${p.status}`}>{p.status}</span></li>
          ))}</ul>
        </div>
      ) : (
        <div className="card"><a href="/login">ログイン</a>すると進捗が表示されます（teacher/teacher123 等）。</div>
      )}
      <div className="card">
        <h3>手順</h3>
        <ol>
          <li><a href="/login">ログイン</a>（初回はパスワード変更・MFA設定を推奨）</li>
          <li><a href="/plans">計画の作成・編集・承認</a>（AI下書き→検討・反映→表現チェック）</li>
          <li><a href="/templates">様式の取込・プレビュー・Excel出力</a>（新潟様式は登録済み）</li>
        </ol>
      </div>
      <div className="card">
        <h3>年間の目安（新潟ハンドブックp3-4）</h3>
        <table className="grid"><tbody>
          {SCHEDULE.map(([t, c]) => <tr key={t}><th>{t}</th><td>{c}</td></tr>)}
        </tbody></table>
      </div>
    </main>
  );
}
