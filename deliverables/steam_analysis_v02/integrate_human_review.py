"""Validate and integrate the user's versioned review file without changing AI labels."""
from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
HUMAN = ROOT / 'human_review'
SOURCE = HUMAN / 'uploaded_review_check_all_34.csv'
ORIGINAL = ROOT / 'results/review_check_all_34.csv'
KEYS = ['game', '目標主題', 'review_id', '抽查階段']
FIELDS = ['人工確認結果', '人工確認主題態度', '人工複核備註']


def integrate():
    old = pd.read_csv(ORIGINAL, dtype=str, keep_default_na=False)
    new = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    assert set(old.columns) == set(new.columns), 'Review columns changed'
    assert len(old) == len(new) == 34
    assert not new.duplicated(KEYS).any()
    assert set(map(tuple, old[KEYS].values)) == set(map(tuple, new[KEYS].values))
    a = old.set_index(KEYS)
    b = new.set_index(KEYS).reindex(a.index)
    protected = [c for c in a.columns if c not in FIELDS + ['review']]
    assert a[protected].equals(b[protected]), 'Non-review fields changed'
    normalized = lambda s: s.str.replace('\r\n', '\n', regex=False).str.replace('\r', '\n', regex=False)
    assert normalized(a.review).eq(normalized(b.review)).all(), 'Review text changed beyond line endings'
    assert b[FIELDS].apply(lambda s: s.str.strip().ne('')).all().all(), 'Incomplete human fields'
    # This snapshot records the user's explicit acceptance of all 34 original labels.
    assert b['人工確認結果'].eq('支持').all()
    assert b['人工確認主題態度'].eq(a['AI_主題態度']).all()
    for index, row in b.iterrows():
        assert index[1] + '：批評' in row['人工確認主題態度'].split('；')
    merged = a.copy()
    for c in FIELDS:
        merged[c] = b[c].str.strip()
    merged['複核者類型'] = 'AI 助理初查；使用者人工確認'
    merged['人工確認版本'] = 'human_v01'
    merged['人工確認來源'] = '使用者上傳 CSV'
    merged = merged.reset_index()
    # Keep the exact original review text; retain the exact uploaded bytes separately.
    merged.to_csv(HUMAN / 'review_check_all_34_human_v01.csv', index=False, encoding='utf-8-sig')
    summary = {
        'version': 'human_v01',
        'uploaded_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'original_template_sha256': hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
        'records': len(merged), 'unique_review_ids': merged.review_id.nunique(),
        'phases': merged['抽查階段'].value_counts().to_dict(),
        'human_result_counts': merged['人工確認結果'].value_counts().to_dict(),
        'human_labels_different_from_AI': int(b['人工確認主題態度'].ne(a['AI_主題態度']).sum()),
        'line_ending_only_differences': int(a.review.ne(b.review).sum()),
        'game_counts': merged.game.value_counts().to_dict(),
        'scope': '34 個目標主題抽查紀錄；不推論全部 1,600 則或每一個非目標標籤的品質。',
        'statistics_action': '人工標籤與原 AI 相同，未修改研究標籤或統計；既有筆數與占比保持不變。',
        'provenance': '原始 1,600 則資料、空白人工抽查模板與原 AI 助理觀察保留。原始人工驗證狀態是歷史值。',
    }
    (HUMAN / 'validation_human_v01.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    integrate()
