export const PII = new Set([
  "child_name", "child_furigana", "birth_date", "address", "address2",
  "guardian_furigana", "guardian_name", "tel", "emergency", "guardian_name_confirm",
]);

export const FIELDS = [
  ["child_code", "管理番号（匿名）"], ["grade", "学年"], ["class_type", "在籍形態"],
  ["profile_strengths", "好き・得意"], ["profile_needs", "苦手・配慮点"],
  ["child_wish", "本人の願い"], ["guardian_wish", "保護者の願い"],
  ["support_history", "これまでの支援"], ["related_agencies", "関係機関"],
  ["support_long_goal", "支援・長期目標（3年）"], ["guidance_long_goal", "指導・長期目標（1年）"],
  ["short_goal_1", "短期目標1"], ["short_goal_2", "短期目標2"],
  ["supports", "具体的支援・手立て"], ["eval_method", "評価方法・時期"],
  ["conference_memo", "会議・面談記録"],
  ["written_date", "記入日（新潟）"], ["writer", "記入者（新潟）"],
  ["child_furigana", "児童生徒ふりがな"], ["gender", "性別"], ["birth_date", "生年月日"],
  ["child_name", "児童生徒氏名"], ["address", "住所"], ["address2", "住所（続き）"],
  ["guardian_furigana", "保護者ふりがな"], ["guardian_name", "保護者氏名"],
  ["tel", "電話番号"], ["emergency", "緊急連絡先"],
  ["grade_year", "学年（年）"], ["history", "生育歴・療育教育歴"], ["life", "生活の様子"],
  ["wish", "願い・希望（新潟）"], ["school_support", "学校における支援"],
  ["eval_handover", "評価・引継ぎ事項"],
  ["family_support", "家庭の支援"], ["community_support", "地域の支援"],
  ["welfare_support", "福祉の支援"], ["medical_support", "医療の支援"],
  ["consent_date", "了承日"], ["guardian_name_confirm", "了承者氏名"],
  ["strengths", "得意・興味関心"], ["weaknesses", "苦手・配慮点（新潟）"],
] as const;

export const HANDOVER_FIELDS = [
  ["handover_to", "引継ぎ先"], ["handover_consent", "引継ぎ先への情報提供の同意"],
  ["handover_consent_date", "引継ぎ同意日"], ["start_ease", "糊しろ（4月のおさらい・得意な課題）"],
  ["effective_supports", "有効だった工夫と条件"], ["episode", "対応エピソード"],
] as const;

export const TABLE_FIELDS = (n: number) => [
  [`fact_${n}`, `実態${n}`], [`goal_${n}`, `目標${n}`],
  [`method_${n}`, `指導支援方法${n}`], [`eval_${n}`, `評価${n}`],
] as const;
