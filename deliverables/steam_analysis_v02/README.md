# Steam 玩家體驗分析工作包 v0.2

先讀 `results/analysis_report.md`；GitHub 摘要為 `results/README_summary.md`。

## Colab

1. 將 `Steam_Experience_Analysis_v02.ipynb` 上傳 Google Colab。
2. 執行全部。若 CSV 不在工作目錄，依提示上傳附帶的 `steam_chinese_1600_semantic_v02.csv`。
3. 本版會核對輸入檔 SHA-256，避免對不同資料沿用抽查註記。套件需 Python 3.11 以上，建議 Python 3.12。
4. 表格與圖輸出到 `results/`，最後產生結果 ZIP。下載 Notebook 時請保留輸出。

Notebook 已在雲端 Python kernel 完整執行；尚未在 Google Colab 服務內實測。無須 Google Drive、Steam 憑證或重新收集資料。

## 一般 Python

在此工作包目錄執行：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python analysis.py
```

可改用 `python analysis.py /path/to/input.csv /path/to/output`。抽查註記僅適用本版資料，輸入不同時需重新核對，不應直接沿用。

`build_notebook.py` 將分析函式與本版註記內嵌成獨立 Notebook。重新建立後需要重新執行 Notebook 才有輸出。

## 計數與複核

- 原始 CSV 不修改；全部 1,600 筆保留，分母為每款全部樣本。
- 主題以評論×主題去重；批評、肯定、混合分開計。
- `review_check_24.csv` 是 24 筆主抽查，`review_check_supplement_10.csv` 是鳴潮內容面向的十筆補查。
- 抽查結果是 AI 助理再讀原文，不代表人工驗證。人工欄留白，請另欄記錄你的確認與修正理由。
- 明顯標籤問題已揭露，未擅自改標、扣數或估計分類準確率。圖與比例均屬原 AI 初判。
- 新手受辱、掉線、材料解鎖等細項尚未完整標記，不能用面向總數代替其筆數或比例。

完整包包含使用者提供的評論資料、原文抽查與分析成果。
