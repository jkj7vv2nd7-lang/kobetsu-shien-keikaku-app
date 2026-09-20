# 運用マニュアル（v0.9・学校現場向け）

## 日常の起動・停止
```powershell
cd "C:\Users\masan\開発中のアプリ\個別支援＿個別指導計画作成"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```
別ターミナルで `cd frontend; npm run dev`。ブラウザは `http://localhost:3000`。
校内公開時は `--host 0.0.0.0`＋ファイアウォールで校内網のみ許可すること。

## 定期バックアップ（週1推奨）
```powershell
python backend/backup.py backup
```
`backend/backups/backup_YYYYMMDD_HHMMSS.zip` に保存。外部媒体へ複写すること。
復元（現行dataは自動退避）：
```powershell
python backend/backup.py restore backend/backups/<file>.zip --force
```

## 年度更新（4月）
1. 旧年度計画を一覧から「複製（年度更新）」（状態draft、確認・同意リセット、メモ引継ぎ）
2. 新学年・新担任で内容を見直し、糊しろ提案で4月課題を設定
3. 5月末までに保護者合意→承認。旧年度は approved のまま保存

## トラブルシュート
- ログイン試行超過（429）：5分待つ。プロキシ経路の場合は送信元IP単位の制限に注意
- PDF文字化け：`/api/health` の `pdf_font` を確認（Falseなら pip install japanize-matplotlib）
- ディスク逼迫：`/api/health` の `disk_free_mb` を確認、backups と templates 出力物を整理
- 監査証跡：`/audit` 画面またはCSV出力で確認

## 初期設定チェックリスト
- [ ] 初期パスワードを全員変更（初回ログイン時に警告表示）
- [ ] 管理職はMFA有効化
- [ ] `backend/.env` にLLMキー・CORS・SSOを設定（リポジトリに含めない）
- [ ] 新潟様式 `python backend/seed_niigata.py`
- [ ] バックアップ先の確保
