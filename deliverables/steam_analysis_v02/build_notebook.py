from pathlib import Path
import json
import nbformat as nbf

root=Path(__file__).resolve().parent
source=(root/'analysis.py').read_text(encoding='utf-8').split("\nif __name__=='__main__':")[0]
notes=json.loads((root/'review_notes.json').read_text(encoding='utf-8'))
cells=[]
md=lambda text: cells.append(nbf.v4.new_markdown_cell(text))
code=lambda text: cells.append(nbf.v4.new_code_cell(text))
md('''# Steam 中文玩家體驗分析｜v0.2

研究：2026/08/01–2026/10/31（台灣時間），Overwatch 500、Apex Legends 500、鳴潮 300、燕雲十六聲 300。

本 Notebook 保留分析程式、表格、圖與結果。所有主題／情緒數字皆源自既有 AI 初判；本次抽查也是 AI 助理閱讀，**不是人工驗證**。原始檔不覆寫，人工確認欄留白。鳴潮「內容與養成」有反覆誤分類，不能直接以原排名解釋內容痛點。

在 Colab 選「執行全部」，上傳指定 CSV；Notebook 不需要 Steam、Google Drive 憑證或線上收集。若要保存回 Google Drive，請自行另存 Notebook；此處不會同步或發布 GitHub。''')
md('## 1. 執行環境\n\n固定統計與繪圖套件版本。Colab 若無中文字型，圖表使用英文主題名稱，中文報告與資料不變。')
code('''import sys, subprocess, os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', str(Path.cwd() / '.matplotlib-cache'))
os.environ.setdefault('IPYTHONDIR', str(Path.cwd() / '.ipython-cache'))
subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                '--quiet', 'pandas==3.1.1', 'matplotlib==3.11.2'], check=True)
''')
md('## 2. 選擇資料檔\n\n預設讀取同目錄的 `steam_chinese_1600_semantic_v02.csv`。同內容但其他檔名可修改 INPUT_PATH；Colab 找不到檔案時會跳出上傳。以 SHA-256 防止將既有抽查註記套到另一份資料。')
code('''from pathlib import Path
import hashlib
INPUT_PATH = ""  # 可填相同內容 CSV 的路徑
candidate = Path(INPUT_PATH) if INPUT_PATH else Path('steam_chinese_1600_semantic_v02.csv')
if not candidate.is_file():
    try:
        from google.colab import files
    except ImportError:
        raise FileNotFoundError('請將 CSV 放在目前目錄，或填寫 INPUT_PATH。')
    uploaded = files.upload()
    csv_names = [name for name in uploaded if name.lower().endswith('.csv')]
    if len(csv_names) != 1:
        raise ValueError('請一次上傳一份 CSV。')
    candidate = Path(csv_names[0])
expected_sha = '05cfe2fda17b17fcabc18d71d686fba53058ac9906f94b1a9ade3a34e142e088'
assert hashlib.sha256(candidate.read_bytes()).hexdigest() == expected_sha, (
    '檔案內容與此版不同。請先核對資料版本並重新抽樣／檢視抽查註記，避免沿用舊結論。')
OUTPUT = Path('results')
OUTPUT.mkdir(exist_ok=True)
print('資料版本 SHA-256 核對通過；輸出：', OUTPUT.resolve())
''')
md('## 3. 分析函式與助理抽查註記\n\n以下完整內嵌程式與 34 筆註記，無須另外上傳 Python 或 JSON。註記是本版既有抽查觀察，不會在重跑時呼叫 AI；使用者應在匯出的人工欄位另行確認。')
code(source)
code('REVIEW_NOTES = '+repr(notes))
md('## 4. 驗證與展開評論×主題\n\n核對配額、App ID、必要欄位、唯一 ID、研究時間、月份與主題／態度一致性；相同評論同主題態度衝突即停止。保留不同 ID 的同文評論。研究期後更新不直接刪除。')
code('''from IPython.display import display, Markdown, Image
df, long, validation = validate_and_expand(candidate, OUTPUT)
display(pd.DataFrame([{'game': g, 'n': validation['game_counts'][g]} for g in GAMES]))
print(json.dumps(validation, ensure_ascii=False, indent=2))
''')
md('## 5. 主題統計、情緒與敏感度\n\n分母是每款全部樣本，不依分析適用性篩選；批評、肯定、混合分開。情緒另表，不能代替主題態度。排除期後更新的表格另用縮減後分母，不改主要分析。')
code('''stats, top5, positive, emotions, sensitivity = summarize(df, long, OUTPUT)
display(top5[['game','topic','批評','sample_n','批評_pct']])
display(positive[['game','topic','肯定','sample_n','肯定_pct']])
display(emotions)
display(sensitivity.sort_values(['game','批評','topic'], ascending=[True,False,True]).groupby('game').head(2))
''')
md('## 6. 主圖與同面向的兩種回饋\n\n依各款批評前五面向繪圖。所有面板使用相同百分比刻度；混合另列。中文圖於有 Noto CJK 字型的環境產生，缺字型則顯示英文標籤。')
code('''make_figures(stats, OUTPUT)
display(Image(filename=str(OUTPUT/'criticism.png')))
display(Image(filename=str(OUTPUT/'feedback.png')))
''')
md('## 7. 原文抽查\n\n主抽查共 24 個紀錄：各款前兩大批評面向，各三則；review_id 穩定排序，每組 random_state=42。鳴潮內容面向補抽十則，排除原三則後 random_state=43。補抽是分類品質抽查，不是重新抽研究樣本。不得據此計細項占比或分類準確率。')
code('''checks = export_review(df, long, stats, REVIEW_NOTES, OUTPUT)
display(checks[['抽查階段','game','目標主題','review_id','AI_主題態度','具體問題_助理摘要','助理抽查結果','原文證據','人工確認結果']])
print('主要抽查：', (checks['抽查階段']=='主要抽查').sum(), '補充：', (checks['抽查階段']=='補充抽查').sum())
print('人工欄留白；原始檔與 AI 標籤未修改。')
''')
md('## 8. 成果報告、摘要與證據\n\n目的選例與額外標籤疑點獨立保存，不混入隨機抽查。建議是下一步蒐證方向；整面向筆數不能充作具體問題筆數。')
code('''export_extra_evidence(df, OUTPUT)
summary = build_report(df, stats, top5, positive, emotions, sensitivity, validation, checks, OUTPUT)
display(summary)
display(Markdown((OUTPUT/'README_summary.md').read_text(encoding='utf-8')))
display(Markdown((OUTPUT/'analysis_report.md').read_text(encoding='utf-8')))
''')
md('## 9. 匯出成果\n\n執行後產生結果 ZIP；Colab 可取消註解下載。Notebook 本身請另外透過 Colab「檔案 → 下載 → .ipynb」保留程式與輸出。CSV 為 UTF-8 BOM，便於 Excel 開啟；沒有修改或覆蓋原始資料。')
code('''import shutil
archive = shutil.make_archive('steam_analysis_results_v02', 'zip', OUTPUT)
print('成果 ZIP：', archive)
print('輸出檔：')
for path in sorted(OUTPUT.iterdir()):
    print(path.name)
# Colab 下載：
# from google.colab import files
# files.download(archive)
''')
nb=nbf.v4.new_notebook(cells=cells)
nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
nb.metadata.language_info={'name':'python','version':'3.12'}
nb.metadata.colab={'name':'Steam_Experience_Analysis_v02.ipynb'}
nbf.write(nb,root/'Steam_Experience_Analysis_v02.ipynb')
print('Created standalone Colab notebook:', len(cells),'cells')
