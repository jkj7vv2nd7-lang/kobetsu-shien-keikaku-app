import "./globals.css";
import LogoutButton from "./logout-button";

export const viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body style={{ fontFamily: "sans-serif", margin: 0, background: "#f6f7f9" }}>
        <nav style={{ background: "var(--navy)", color: "#fff", padding: "10px 16px" }}>
          <a href="/" style={{ color: "#fff", marginRight: 16, textDecoration: "none", fontWeight: "bold" }}>計画支援 v0.6</a>
          <a href="/plans" style={{ color: "#cfe0f5", marginRight: 12 }}>計画</a>
          <a href="/templates" style={{ color: "#cfe0f5", marginRight: 12 }}>様式・差し込み</a>
          <a href="/audit" style={{ color: "#cfe0f5", marginRight: 12 }}>監査</a>
          <a href="/settings" style={{ color: "#cfe0f5", marginRight: 12 }}>設定</a>
          <a href="/login" style={{ color: "#cfe0f5" }}>ログイン</a>
          <LogoutButton />
        </nav>
        <div style={{ maxWidth: 960, margin: "0 auto", padding: 16 }}>{children}</div>
      </body>
    </html>
  );
}
