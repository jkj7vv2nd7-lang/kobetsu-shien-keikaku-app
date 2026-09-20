"""新潟様式PDF生成 v0.6（fpdf2＋IPAexゴシック）。

フォント解決順：japanize-matplotlib同梱 → Windowsフォント → エラー。
印刷レイアウトはExcel原本の代替（A4縦・2ページ）。
"""
from __future__ import annotations
import os
from pathlib import Path


def font_path() -> str:
    try:
        import japanize_matplotlib
        p = Path(japanize_matplotlib.__file__).parent / "fonts" / "ipaexg.ttf"
        if p.exists():
            return str(p)
    except ImportError:
        pass
    for c in ("C:\\Windows\\Fonts\\msgothic.ttc", "C:\\Windows\\Fonts\\meiryo.ttc",
              "/usr/share/fonts/ipaexg.ttf", "/usr/share/fonts/opentype/ipaexg.ttf"):
        if os.path.exists(c):
            return c
    raise RuntimeError("日本語フォントが見つかりません（japanize-matplotlibを要インストール）")


def _pdf() -> tuple:
    from fpdf import FPDF
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_font("ipaex", "", font_path())
    pdf.add_font("ipaex", "B", font_path())
    return pdf, 10, 5.2


def _h(pdf, text: str, size: int = 14):
    pdf.set_font("ipaex", "B", size)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")


def _kv(pdf, label: str, value: str, size=10, lh=5.2):
    pdf.set_font("ipaex", "B", size)
    pdf.write(lh, label + " ")
    pdf.set_font("ipaex", "", size)
    pdf.write(lh, (value or "") + "\n")


def build_niigata_pdf(data: dict) -> bytes:
    pdf, size, lh = _pdf()
    g = lambda k: "" if data.get(k) is None else str(data.get(k))
    bool_s = lambda v: "確認済" if v is True else ("未確認" if v is False else g(v))

    # --- 1ページ：個別の教育支援計画 ---
    pdf.add_page()
    _h(pdf, "個別の教育支援計画")
    _kv(pdf, "記入日：", g("written_date"))
    _kv(pdf, "記入者：", g("writer"))
    _kv(pdf, "児童生徒氏名：", f"{g('child_name')}（{g('child_furigana')}）  性別：{g('gender')}  生年月日：{g('birth_date')}")
    _kv(pdf, "住所：", g("address") + " " + g("address2"))
    _kv(pdf, "保護者氏名：", f"{g('guardian_name')}（{g('guardian_furigana')}）")
    _kv(pdf, "電話：", f"{g('tel')}  緊急連絡先：{g('emergency')}")
    _h(pdf, "これまでの生育歴（療育・教育歴）", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("history"))
    _h(pdf, "生活の様子", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("life"))
    _h(pdf, "願い・希望", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("wish"))
    _h(pdf, "長期目標", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("support_long_goal"))
    _h(pdf, "学校における支援", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("school_support"))
    _h(pdf, "評価・引継ぎ事項", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("eval_handover"))
    _h(pdf, "関係者による支援", 11)
    for label, key in (("家庭", "family_support"), ("地域", "community_support"),
                       ("福祉", "welfare_support"), ("医療", "medical_support")):
        _kv(pdf, f"[{label}]", g(key))
    pdf.ln(2)
    _kv(pdf, "上記の内容について了承します。", "")
    _kv(pdf, "日付：", f"{g('consent_date')}  保護者氏名：{g('guardian_name_confirm')}（印）")

    # --- 2ページ：個別の指導計画 ---
    pdf.add_page()
    _h(pdf, "個別の指導計画")
    _kv(pdf, "記入日：", g("written_date"))
    _kv(pdf, "記入者：", g("writer"))
    _kv(pdf, "学年：", f"{g('grade_year')}  氏名：{g('child_name')}（{g('child_furigana')}）  性別：{g('gender')}  生年月日：{g('birth_date')}")
    _h(pdf, "得意なこと、興味・関心", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("strengths"))
    _h(pdf, "苦手なこと・配慮すること", 11)
    pdf.set_font("ipaex", "", size); pdf.multi_cell(0, lh, g("weaknesses"))
    _h(pdf, "指導表", 11)
    cols = (("実態", 45), ("目標", 45), ("指導・支援方法", 55), ("評価", 45))
    pdf.set_font("ipaex", "B", 9)
    for title, w in cols:
        pdf.cell(w, 6, title, border=1)
    pdf.ln()
    pdf.set_font("ipaex", "", 9)
    for n in range(1, 10):
        vals = [g(f"fact_{n}"), g(f"goal_{n}"), g(f"method_{n}"), g(f"eval_{n}")]
        if not any(vals):
            continue
        h = max(8, max(len(v) for v in vals) // 18 * 5 + 8)
        x0 = pdf.get_x()
        y0 = pdf.get_y()
        if y0 + h > 280:
            pdf.add_page()
            y0 = pdf.get_y()
        for (title, w), v in zip(cols, vals):
            pdf.set_xy(x0, y0)
            pdf.multi_cell(w, 5, v, border=1)
            x0 += w
        pdf.set_xy(10, y0 + h)
    pdf.ln(2)
    _kv(pdf, "上記の内容について了承します。", "")
    _kv(pdf, "日付：", f"{g('consent_date')}  保護者氏名：{g('guardian_name_confirm')}（印）")

    out = pdf.output()
    return bytes(out)
