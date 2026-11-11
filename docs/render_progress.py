"""Render the project status diagram; run from any working directory."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent
FONT = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
if not FONT.exists():
    raise FileNotFoundError('Install Noto CJK fonts to render this Chinese status chart.')
font_manager.fontManager.addfont(str(FONT))
plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams['svg.fonttype'] = 'path'
fig = plt.figure(figsize=(14, 11), facecolor='#f5f7fa')
ax = fig.add_axes([0, 0, 1, 1])
ax.set(xlim=(0, 14), ylim=(0, 11))
ax.axis('off')
ax.text(.65,10.35,'Steam-Project｜專案進度',fontsize=26,weight='bold',color='#172b40')
ax.text(.65,9.91,'截至 2026/11/11（台灣時間）｜依 GitHub 已提交成果核對',fontsize=12,color='#5a6a7a')
ax.add_patch(FancyBboxPatch((.65,8.88),12.7,.72,boxstyle='round,pad=.02,rounding_size=.12',facecolor='#172b40',edgecolor='none'))
ax.text(.93,9.24,'目前位置：34 筆人工確認完成 → 記錄分類規則 → 定稿作品集摘要',fontsize=16,color='white',va='center')

def panel(x,y,w,h,title,items,color):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.02,rounding_size=.13',facecolor='white',edgecolor='#dce3eb'))
    ax.add_patch(FancyBboxPatch((x+.2,y+h-.58),w-.4,.40,boxstyle='round,pad=.01,rounding_size=.06',facecolor=color,edgecolor='none'))
    ax.text(x+.35,y+h-.38,title,color='white',fontsize=15,weight='bold',va='center')
    cursor=y+h-.96
    for heading,body in items:
        ax.text(x+.25,cursor,heading,fontsize=13,weight='bold',color='#23374b',va='top')
        ax.text(x+.25,cursor-.31,body,fontsize=11,color='#586b7e',va='top',linespacing=1.5)
        cursor-=.98

panel(.65,4.70,4.0,3.9,'已完成・可核對',[
 ('研究範圍','四款遊戲／三個月／繁簡中文'),
 ('樣本與基本驗證','1,600 則；配額、ID、日期通過'),
 ('人工確認完成','34／34 筆支持；另存使用者版本')], '#237b67')
panel(5.0,4.70,4.0,3.9,'已有初稿・待確認',[
 ('AI 語意分類','情緒、主題、主題態度已提供'),
 ('可重跑統計與圖表','Notebook 10 格已執行；統計不變'),
 ('報告與調查建議','每款一項；正式結論未定稿')], '#a66d22')
panel(9.35,4.70,4.0,3.9,'接著完成',[
 ('記錄分類規則','說明重疊主題的判讀依據'),
 ('整理原文與建議','每款一項，保留不同判讀'),
 ('定稿作品集','無標籤變更，本次無須重算')], '#526f9e')

ax.add_patch(FancyBboxPatch((.65,3.43),12.7,.94,boxstyle='round,pad=.02,rounding_size=.1',facecolor='#fff1df',edgecolor='#efca91'))
ax.text(.92,4.06,'本次人工確認：34 筆均支持，標籤與統計維持原值',fontsize=15,weight='bold',color='#855714',va='center')
ax.text(.92,3.70,'使用者支持既有分類；助理先前的主題邊界疑點另存，後續將判讀規則寫明。',fontsize=12,color='#855714',va='center')

ax.text(.7,2.98,'後續路徑',fontsize=14,weight='bold',color='#23374b')
ax.text(.7,2.56,'人工結果已收錄 → 寫明分類邊界與限制 → 整理每款調查建議 → 定稿 README 與報告',fontsize=12,color='#38546c')
ax.text(.7,2.03,'本版暫緩',fontsize=13,weight='bold',color='#23374b')
ax.text(2.15,2.03,'遊玩時數分組、重新抽樣、機器學習',fontsize=12,color='#586b7e')
ax.text(.7,1.62,'原規劃未交付',fontsize=13,weight='bold',color='#23374b')
ax.text(2.58,1.62,'SQL、Power BI；未列入本次工作包必要交付',fontsize=12,color='#586b7e')
ax.text(.7,1.03,'證據待補：最終樣本已提供；原始收集、完整性驗收、清理與正式抽樣流程尚未完整提交。',fontsize=11,color='#586b7e')
ax.text(.7,.57,'34 筆支持不代表全體分類準確率。鳴潮 71 則完整複核尚未執行，可作後續擴充檢查。',fontsize=10,color='#6d7e8f')
for ext in ['png','pdf']:
    fig.savefig(ROOT/f'project_progress.{ext}',dpi=180,bbox_inches='tight',facecolor=fig.get_facecolor())
plt.close(fig)
