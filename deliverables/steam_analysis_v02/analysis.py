from pathlib import Path
import hashlib
import json
import platform
import sys
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

GAMES = ['Overwatch', 'Apex Legends', '鳴潮', '燕雲十六聲']
EXPECTED = {'Overwatch': 500, 'Apex Legends': 500, '鳴潮': 300, '燕雲十六聲': 300}
APPIDS = {'Overwatch': '2357570', 'Apex Legends': '1172470', '鳴潮': '3513350', '燕雲十六聲': '3564740'}
ATTITUDES = ['批評', '肯定', '混合', '中性提及', '不確定']

def validate_and_expand(path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(path, dtype={'review_id': 'string', 'appid': 'string'})
    required = ['game','appid','review_id','review','language','requested_language',
                'timestamp_created','timestamp_updated','created_at_utc','month',
                '文字情緒_AI','主題_AI','各主題態度_AI','分析適用性_AI','研究期後更新',
                '人工驗證狀態','人工確認情緒','人工確認主題態度','人工複核備註']
    absent = sorted(set(required) - set(df.columns))
    if absent:
        raise ValueError(f'缺少必要欄位：{absent}')
    core = [c for c in required if not c.startswith('人工確認') and c != '人工複核備註']
    blank = {c: int((df[c].isna() | df[c].astype('string').str.strip().eq('')).sum()) for c in core}
    if any(blank.values()):
        raise ValueError(f'必要欄位缺漏：{blank}')
    counts = df.groupby('game').size().to_dict()
    assert counts == EXPECTED, f'樣本配額不符：{counts}'
    assert not df.duplicated(['appid','review_id']).any(), '遊戲＋評論 ID 重複'
    assert df.review_id.is_unique, '全檔評論 ID 重複'
    assert df.review_id.str.fullmatch(r'\d+').all()
    assert df.appid.eq(df.game.map(APPIDS)).all(), '遊戲 ID 不符'
    assert df.language.isin(['tchinese','schinese']).all()
    assert df.requested_language.isin(['tchinese','schinese']).all()
    created = pd.to_datetime(df.timestamp_created, unit='s', utc=True).dt.tz_convert('Asia/Taipei')
    updated = pd.to_datetime(df.timestamp_updated, unit='s', utc=True).dt.tz_convert('Asia/Taipei')
    start, end = pd.Timestamp('2026-08-01', tz='Asia/Taipei'), pd.Timestamp('2026-11-01', tz='Asia/Taipei')
    assert ((created >= start) & (created < end)).all(), '建立日期超出研究期間'
    assert (created.dt.strftime('%Y-%m') == df.month).all(), '月份欄與台灣時間不符'
    assert (pd.to_datetime(df.created_at_utc, utc=True) == created).all(), '日期欄不一致'
    assert (updated >= created).all(), '更新時間早於建立時間'
    after = updated >= end
    supplied_flag = df['研究期後更新'].astype(str).str.lower().map({'true':True,'false':False})
    assert supplied_flag.notna().all() and supplied_flag.eq(after).all(), '期後更新標記不一致'
    rows, duplicate_pairs = [], 0
    for _, r in df.iterrows():
        themes = {x.strip() for x in r['主題_AI'].split('；')} - {'無具體主題'}
        seen = {}
        for item in r['各主題態度_AI'].split('；'):
            item = item.strip()
            if item == '無具體主題':
                continue
            if '：' not in item:
                raise ValueError(f'態度格式錯誤：{r.review_id}: {item}')
            topic, attitude = [x.strip() for x in item.rsplit('：', 1)]
            assert attitude in ATTITUDES, f'未知態度：{attitude}'
            if topic in seen:
                assert seen[topic] == attitude, f'同評論同主題態度衝突：{r.review_id}'
                duplicate_pairs += 1
                continue
            seen[topic] = attitude
            rows.append({'game':r.game,'appid':r.appid,'review_id':r.review_id,
                         'topic':topic,'attitude_AI':attitude,'研究期後更新':bool(after.loc[r.name])})
        assert set(seen) == themes, f'主題及態度欄不一致：{r.review_id}'
    long = pd.DataFrame(rows)
    assert not long.duplicated(['appid','review_id','topic']).any()
    long.to_csv(output/'review_topic_long.csv', index=False, encoding='utf-8-sig')
    report = {
        'input_file': Path(path).name, 'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'rows':len(df),'columns':len(df.columns),'game_counts':counts,
        'duplicate_review_ids':int(df.review_id.duplicated().sum()),
        'duplicate_game_review_ids':int(df.duplicated(['appid','review_id']).sum()),
        'duplicate_game_text_rows':int(df.duplicated(['game','review']).sum()),
        'note_duplicate_text':'同文不同 ID 保留，不視為同一評論；未驗證來源真實性或帳號獨立性。',
        'required_missing':blank,'created_min_taipei':str(created.min()),'created_max_taipei':str(created.max()),
        'post_period_updated':int(after.sum()),'post_period_updated_by_game':df.assign(after=after).groupby('game').after.sum().to_dict(),
        'topic_pair_rows':len(long),'duplicate_topic_pairs_removed':duplicate_pairs,
        'AI_applicability':df['分析適用性_AI'].value_counts().to_dict(),
        'human_review_status':df['人工驗證狀態'].value_counts().to_dict(),
        'no_topic_reviews':int(df['主題_AI'].eq('無具體主題').sum()),
        'python_version':platform.python_version(),'pandas_version':pd.__version__,'matplotlib_version':matplotlib.__version__,
        'denominator':'各遊戲全部樣本；不依分析適用性或情緒篩選。批評只計態度=批評，混合另列。',
    }
    (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    df.groupby(['game','language','month']).size().rename('n').reset_index().to_csv(output/'sample_composition.csv',index=False,encoding='utf-8-sig')
    return df, long, report

def summarize(df, long, output):
    output = Path(output)
    stats = long.groupby(['game','topic','attitude_AI']).size().unstack(fill_value=0).reindex(columns=ATTITUDES,fill_value=0).reset_index()
    stats['sample_n'] = stats.game.map(EXPECTED)
    for a in ATTITUDES:
        stats[a+'_pct'] = stats[a] / stats.sample_n * 100
    stats.to_csv(output/'topic_statistics_AI.csv',index=False,encoding='utf-8-sig')
    ordered = stats.sort_values(['game','批評','topic'],ascending=[True,False,True])
    top5 = ordered.groupby('game',sort=False).head(5)
    top5.to_csv(output/'top5_criticism_AI.csv',index=False,encoding='utf-8-sig')
    positive = stats.sort_values(['game','肯定','topic'],ascending=[True,False,True]).groupby('game',sort=False).head(5)
    positive.to_csv(output/'top5_praise_AI.csv',index=False,encoding='utf-8-sig')
    emotions = df.groupby(['game','文字情緒_AI']).size().rename('n').reset_index()
    emotions['sample_n'] = emotions.game.map(EXPECTED)
    emotions['pct'] = emotions.n/emotions.sample_n*100
    emotions.to_csv(output/'emotion_statistics_AI.csv',index=False,encoding='utf-8-sig')
    sensitivity = long[~long['研究期後更新']].groupby(['game','topic','attitude_AI']).size().unstack(fill_value=0).reindex(columns=ATTITUDES,fill_value=0).reset_index()
    valid_n = df[~df['研究期後更新'].astype(str).str.lower().eq('true')].groupby('game').size()
    sensitivity['sample_n'] = sensitivity.game.map(valid_n)
    sensitivity['批評_pct'] = sensitivity['批評']/sensitivity.sample_n*100
    sensitivity.to_csv(output/'sensitivity_excluding_post_period_updates.csv',index=False,encoding='utf-8-sig')
    return stats, top5, positive, emotions, sensitivity

EN_TOPICS = {'連線':'Connection','當機與啟動':'Crashes / launch','客服與營運':'Service / operations',
 '帳號與平台':'Account / platform','效能':'Performance','配對與排位':'Matchmaking / ranked',
 '社群與合作體驗':'Community / cooperation','平衡':'Balance','內容與養成':'Content / progression',
 '付費與抽卡':'Payment / gacha','操作介面與可及性':'UI / accessibility','錯誤與異常':'Bugs / anomalies',
 '美術與音樂':'Art / music','操作與戰鬥':'Controls / combat','教學與引導':'Tutorial',
 '外掛與公平性':'Cheating / fairness','下載更新與容量':'Download / updates','語言與在地化':'Localization'}
EN_GAMES = {'Overwatch':'Overwatch','Apex Legends':'Apex Legends','鳴潮':'Wuthering Waves','燕雲十六聲':'Where Winds Meet'}

def make_figures(stats, output):
    output=Path(output)
    chinese_font=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    cjk=chinese_font.exists()
    if cjk:
        font_manager.fontManager.addfont(str(chinese_font))
        plt.rcParams['font.family']=font_manager.FontProperties(fname=str(chinese_font)).get_name()
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'font.size':11,'svg.fonttype':'path'})
    for mode in ['criticism','feedback']:
        fig,axes=plt.subplots(2,2,figsize=(15,10))
        for ax,game in zip(axes.flat,GAMES):
            g=stats[stats.game.eq(game)].sort_values(['批評','topic'],ascending=[False,True]).head(5).iloc[::-1]
            labels=g.topic.tolist() if cjk else [EN_TOPICS[t] for t in g.topic]
            if mode=='criticism':
                ax.barh(labels,g['批評_pct'],color='#b34d3a',height=.62)
                for y,(_,r) in enumerate(g.iterrows()):
                    ax.text(r['批評_pct']+.5,y,f"{int(r['批評'])} ({r['批評_pct']:.1f}%)",va='center',fontsize=10)
            else:
                for offset,col,color in [(-.22,'批評','#b34d3a'),(0,'肯定','#258579'),(.22,'混合','#b29452')]:
                    ys=[y+offset for y in range(len(g))]
                    ax.barh(ys,g[col+'_pct'],height=.21,color=color,label=col if cjk else {'批評':'Criticism','肯定':'Praise','混合':'Mixed'}[col])
                    for y,(_,r) in zip(ys,g.iterrows()):
                        ax.text(r[col+'_pct']+.4,y,f"{int(r[col])} ({r[col+'_pct']:.1f}%)",va='center',fontsize=8)
                ax.set_yticks(range(len(g)),labels)
            ax.set_xlim(0,40)
            ax.set_title(f"{game if cjk else EN_GAMES[game]}  |  n={EXPECTED[game]}",loc='left',fontweight='bold')
            ax.set_xlabel('占該遊戲全部樣本（%）' if cjk else 'Share of all sampled reviews for this game (%)')
            ax.grid(axis='x',alpha=.16)
            ax.set_axisbelow(True)
        if mode=='feedback':
            axes.flat[0].legend(loc='lower right',fontsize=9)
        title=('各款遊戲主要批評面向｜AI 初判' if mode=='criticism' else '主要批評面向中的肯定、批評與混合｜AI 初判') if cjk else ('Leading criticism topics | preliminary AI labels' if mode=='criticism' else 'Praise, criticism and mixed feedback within leading criticism topics | AI labels')
        fig.suptitle(title,fontsize=19,x=.04,ha='left',y=.98,fontweight='bold')
        note='每款取批評筆數前五名。同評論同主題只計一次；可跨主題重複。混合另列，不併入批評。\n標籤尚未人工驗證；鳴潮「內容與養成」有重複誤分類，該面向數字與排名須審慎解讀。' if cjk else 'Top five topics ranked by criticism count per game; one count per review-topic; topics may overlap. Mixed is separate.\nAI labels are not human-validated. Content/progression labels for Wuthering Waves need correction before interpretation.'
        fig.text(.04,.015,note,fontsize=10,color='#555555',va='bottom')
        fig.tight_layout(rect=[0,.085,1,.94],h_pad=3,w_pad=3)
        for ext in ['png','svg','pdf']:
            fig.savefig(output/f'{mode}.{ext}',dpi=180,bbox_inches='tight')
        plt.close(fig)

def select_reviews(df, long, stats):
    primary=[]
    leaders=stats.sort_values(['game','批評','topic'],ascending=[True,False,True]).groupby('game',sort=True).head(2)
    for _,leader in leaders.iterrows():
        pool=long[long.game.eq(leader.game)&long.topic.eq(leader.topic)&long.attitude_AI.eq('批評')].sort_values('review_id')
        for rid in pool.sample(n=3,random_state=42).review_id:
            primary.append((leader.game,leader.topic,str(rid),'主要抽查',42))
    used={r[2] for r in primary if r[0]=='鳴潮' and r[1]=='內容與養成'}
    pool=long[long.game.eq('鳴潮')&long.topic.eq('內容與養成')&long.attitude_AI.eq('批評')&~long.review_id.isin(used)].sort_values('review_id')
    extra=[('鳴潮','內容與養成',str(rid),'補充抽查',43) for rid in pool.sample(n=10,random_state=43).review_id]
    assert len(primary)==24 and len(extra)==10
    return primary+extra

def export_review(df, long, stats, notes, output):
    records=[]
    for game,topic,rid,phase,seed in select_reviews(df,long,stats):
        r=df[df.review_id.eq(rid)].iloc[0]
        result,description,quote=notes[rid]
        assert quote in r.review, f'引文非原文子字串：{rid}'
        records.append({'抽查階段':phase,'random_seed':seed,'game':game,'目標主題':topic,'review_id':rid,
            'AI_文字情緒':r['文字情緒_AI'],'AI_主題態度':r['各主題態度_AI'],
            'AI_語意說明':r['語意說明_AI'],'review':r.review,'具體問題_助理摘要':description,
            '助理抽查結果':result,'原文證據':quote,'複核者類型':'AI 助理；待使用者人工確認',
            '原始人工驗證狀態':r['人工驗證狀態'],'人工確認結果':'','人工確認主題態度':'','人工複核備註':'',
            '研究期後更新':r['研究期後更新']})
    checks=pd.DataFrame(records)
    assert len(checks)==34
    output=Path(output)
    checks[checks['抽查階段'].eq('主要抽查')].to_csv(output/'review_check_24.csv',index=False,encoding='utf-8-sig')
    checks[checks['抽查階段'].eq('補充抽查')].to_csv(output/'review_check_supplement_10.csv',index=False,encoding='utf-8-sig')
    checks.to_csv(output/'review_check_all_34.csv',index=False,encoding='utf-8-sig')
    lines=['# 原文抽查紀錄','',
        '主抽查：每款遊戲批評筆數最高兩面向，各三則，共 24 個評論×主題紀錄。排序評論 ID 後各組以 random_state=42 抽樣；同一評論可跨主題出現。',
        '補抽：鳴潮／內容與養成在主抽查反覆出現主題不符後，排除原三則再以 random_state=43 抽十則。這不是重新抽取研究樣本。',
        '以下是 AI 助理讀原文後的第二次抽查，**不是人工驗證**。所有人工確認欄留白，原始 AI 標籤與人工狀態未修改。不可用抽查紀錄估計細項比例或分類準確率。','']
    for _,r in checks.iterrows():
        lines += [f"## {r['抽查階段']}｜{r.game}｜{r['目標主題']}｜{r.review_id}",'',
            f"- 原 AI 標籤：{r['AI_主題態度']}",f"- 助理抽查：{r['助理抽查結果']}",
            f"- 問題與邊界：{r['具體問題_助理摘要']}",f"- 原文摘錄：{r['原文證據']}",
            '- 人工確認：待確認','', '<details><summary>完整原文</summary>','',r.review,'','</details>','']
    (output/'review_check.md').write_text('\n'.join(lines),encoding='utf-8')
    return checks

def markdown_table(frame):
    # Avoid optional tabulate dependency; keep CSV as the exact numeric source.
    def esc(v):
        return str(v).replace('|','／').replace('\n',' ')
    header='| '+' | '.join(map(esc,frame.columns))+' |'
    rule='| '+' | '.join(['---']*len(frame.columns))+' |'
    return '\n'.join([header,rule]+['| '+' | '.join(map(esc,row))+' |' for row in frame.itertuples(index=False,name=None)])

def build_report(df, stats, top5, positive, emotions, sensitivity, report, checks, output):
    output=Path(output)
    def val(game,topic,att='批評'):
        r=stats[stats.game.eq(game)&stats.topic.eq(topic)].iloc[0]
        return f"{int(r[att])}／{EXPECTED[game]}（{r[att+'_pct']:.1f}%）"
    recommendations=[
        ['Overwatch','新玩家配對體驗與溝通環境',val('Overwatch','配對與排位'),
         '234431993：「4把游戏，因为是萌新在熟悉游戏而被队友骂了3把」；另有 233026072、235765547 直接批評匹配。',
         '依新玩家／模式／地區／段位差分層，查對局分差、勝負差距、組隊狀態、聊天檢舉與前幾場體驗；核對是配對落差還是社群互動。',
         '92 則是整個配對與排位面向，並非 92 則新手受辱，也未證明演算法不公平。'],
        ['Apex Legends','掉線與重新連線流程',val('Apex Legends','連線'),
         '237645911：「我朋友一晚上掉4回」；236465435 批評伺服器但無重現細節。',
         '先收時段、伺服器區域、網路供應商、錯誤碼與斷線紀錄；重現斷線→重連→排位處罰流程，核對伺服器與客戶端日誌。',
         '44 則並非全都回報掉線；不能由評論認定伺服器根因或反作弊因果。'],
        ['鳴潮','抽卡保底成本與機制理解',val('鳴潮','付費與抽卡'),
         '238133779：「不优化卡池的话，那就差评」；231793305：「抽卡昂貴」。',
         '分開查保底規則理解、付費成本感受與抽取紀錄；測試卡池說明、保底進度與成本呈現是否易懂，機率異常須由實際日誌另驗。',
         '不採用受污染的內容與養成排名推導具體內容缺陷；不把月卡後歪卡視為機率改變。'],
        ['燕雲十六聲','更新內容與養成材料解鎖時程銜接',val('燕雲十六聲','客服與營運'),
         '233270638：「奇術突破材料要到新地圖拿新地圖要等全服共建」；233258748 另提更新品質與活動冗長。',
         '核對更新／共建／地圖與材料開放時間；用不同進度帳號測試取得新奇術後能否升級、介面是否清楚說明門檻與預期開放時間。',
         '28 則屬整個客服與營運面向，不能視為 28 則材料解鎖問題；原文未證明實際規則或缺陷。']]
    summary=pd.DataFrame(recommendations,columns=['遊戲','優先調查事項','對應面向數據_AI初判','原文證據','下一個查證動作','解讀界線'])
    summary.to_csv(output/'investigation_summary.csv',index=False,encoding='utf-8-sig')
    table=top5[['game','topic','批評','批評_pct']].copy()
    table['批評_pct']=table['批評_pct'].map(lambda x:f'{x:.1f}%')
    table.columns=['遊戲','批評面向_AI','筆數','占該遊戲全部樣本']
    praise=positive[['game','topic','肯定','肯定_pct']].copy()
    praise['肯定_pct']=praise['肯定_pct'].map(lambda x:f'{x:.1f}%')
    praise.columns=['遊戲','肯定面向_AI','筆數','占該遊戲全部樣本']
    sections=['# Steam 中文玩家體驗分析｜v0.2 工作包成果','',
        '**狀態：AI 初判統計＋助理原文抽查；尚未完成人工驗證。** 原始資料與標籤保持不變。',
        '', '## 研究問題與範圍','',
        '各款評論者肯定／批評哪些體驗，以及營運團隊可先查什麼？本版使用使用者提供的 1,600 則樣本：Overwatch 500、Apex Legends 500、鳴潮 300、燕雲十六聲 300。建立時間限定台灣時間 2026/08/01–2026/10/31。語言是 Steam 繁簡中文標記，不保證原文全為中文。未重新抽樣、未做時數分組或機器學習；平均時數圖不納入主要結論。',
        '', '## 驗證結果','',
        f"- 1,600 列、35 欄；配額與 App ID 相符，評論 ID 全部唯一；必要分析欄無缺值，原文無空白。人工確認欄留白屬預期。",
        f"- 建立時間：{report['created_min_taipei']} 至 {report['created_max_taipei']}；月份與台灣時間一致。",
        '- 同遊戲同文字但不同評論 ID 共 133 列額外重複，保留，不以文字去重。檔案本身不能證明帳號獨立性或來源真實性。',
        '- 9 則評論於研究期後更新（Overwatch 4、Apex 1、鳴潮 2、燕雲 2）；只有收集時原文，無法還原研究期末版本。主分析保留，另附排除這九則的敏感度表。',
        '- 分析適用性：921 則可作產品語意分析、564 則僅情緒／語氣參考、115 則無法判讀產品體驗。679 則無具體主題；主題占比仍以各款全部樣本為分母。',
        f"- 原始人工狀態全為未驗證。來源 SHA-256：`{report['sha256']}`。",'',
        '## 計數方法','',
        '解析「各主題態度_AI」，核對其主題集合與「主題_AI」一致。每個遊戲＋評論 ID＋主題只計一次；態度衝突會停止。批評只計「批評」，肯定只計「肯定」；「混合」「中性提及」「不確定」另列，不把整體負面情緒或 Steam 不推薦推成每個主題都負面。',
        '占比＝該款符合目標態度的評論×主題筆數／該款全部樣本。跨主題可重複，總和可能超過 100%；不以有效資訊數或批評評論數改分母，不合併四款推論市場。前五名按筆數遞減，同筆數按主題字串排序。',
        '', '## 主要批評面向','',
        '![各款遊戲主要批評面向](criticism.png)','',markdown_table(table),'',
        '**鳴潮「內容與養成」71 則／23.7% 是原 AI 標籤統計，已發現反覆誤分類，不能據此認定內容問題最多。所有主題數字仍是待人工驗證的描述。**',
        '', '## 肯定與批評並列','',
        '![同面向各種回饋](feedback.png)','',
        f"燕雲十六聲「內容與養成」有肯定 {val('燕雲十六聲','內容與養成','肯定')}、批評 {val('燕雲十六聲','內容與養成')}、混合 {val('燕雲十六聲','內容與養成','混合')}；不能單以批評面向排名描述整體口碑。鳴潮同面向肯定 {val('鳴潮','內容與養成','肯定')}、批評 {val('鳴潮','內容與養成')}、混合 {val('鳴潮','內容與養成','混合')}，但其標籤邊界有問題，兩側比例都需複核。",
        '', '各款 AI 肯定面向前五名如下；只列明確的主題肯定，不把籠統「好玩」補成玩法或內容。', '',markdown_table(praise),'',
        '可支持肯定的具體案例（目的選例，另於 evidence_examples.csv 保留全文，不屬 24 筆隨機抽查）：Apex 237431132「战斗爽」；Overwatch 237241641 喜歡新模式並希望常駐；燕雲 232274254 描述自行規劃採藥路線與轉乘；鳴潮 232285054 描述高畫質設備下的畫面優勢。這些案例不代表整個主題所有評論。',
        '', '## 原文抽查與標籤限制','',
        '每款前兩大批評面向，各抽三則，共 24 個抽查紀錄。各組先按 review_id 排序，以種子 42 抽取；同評論可出現在不同面向。本次讀原文者仍是 AI 助理，新增助理摘要／結果並留白人工確認欄，不能稱為人工驗證或分類準確率驗收。完整原文見 review_check.md 與 CSV。',
        '- Apex 連線案例中有明確掉線描述，也有只有辱罵或拼音的短句；啟動面向有進入困難，但部分未分清當機、踢出或反作弊限制。',
        '- Overwatch 配對三則支持玩家不滿，但不能驗證公平性；帳號面向的榮譽等級聊天限制存在主題邊界疑問，不能都當登入或驗證問題。',
        '- 燕雲內容面向有世界等級與主線難度案例，但第三章比較缺細節，衣服外觀較貼近美術／自訂。營運案例支持查更新時程及活動設計，不代表客服失效。',
        '- 鳴潮內容與養成主抽三則中，兩則分別只談技能說明與抽卡，沒有支持目標主題；另一則疑為反諷。因反覆不符，排除原三則後以種子 43 補抽十則，其中六則只談抽卡／中獎、兩則資訊不足，另兩則分別涉及聲骸與角色敘事。這是抽查紀錄，**不能外推誤判率，也不能直接扣減全體 71 則**。',
        '- 額外檢視肯定案例時，Overwatch 231976333 明確批評新模式，卻被標「內容與養成：肯定」；燕雲 234215648「風景沒話說」不足以獨立支持內容養成肯定。肯定比例亦不能視為人工確認結果；問題記錄另列，不混入隨機抽查。',
        '後續完整複核應先明訂內容／養成、抽卡、介面／教學、社群治理的邊界，逐則記錄修正理由與人工確認欄，之後再重算排名。現階段不計算「掉線」「材料解鎖」「新手受辱」等細項比例。',
        '', '## 每款一項優先調查事項','',markdown_table(summary),'',
        '以上是優先蒐證方向，並非修復排序。評論能指出問題線索，不能直接證明 Bug、嚴重程度、流失原因或營收影響。',
        '', '## 研究期後更新敏感度','',
        '排除研究期後更新評論時，分母同步改為 Overwatch 496、Apex 499、鳴潮 298、燕雲 298；保留同一計數方法。完整結果見 sensitivity_excluding_post_period_updates.csv。此檢查不能還原舊原文，也不取代主要樣本。',
        '', '## 檔案與重現','',
        '- `Steam_Experience_Analysis_v02.ipynb`：已執行並保留輸出；Colab 可上傳同名 CSV，其他檔名可填 INPUT_PATH。',
        '- `analysis.py`、`review_notes.json`：分析函式與可稽核的助理抽查註記。',
        '- `review_topic_long.csv`、`topic_statistics_AI.csv`、`top5_criticism_AI.csv`、`top5_praise_AI.csv`：完整計數及占比。',
        '- `review_check_24.csv`、`review_check_supplement_10.csv`、`review_check_all_34.csv`、`review_check.md`：抽查紀錄，人工欄留白。',
        '- `investigation_summary.csv`、`README_summary.md`：優先調查摘要與可貼入 GitHub 的文字。',
        '- `criticism`／`feedback`：PNG、SVG、PDF 圖檔；資料標註 AI 初判。',
        '- `evidence_examples.csv` 與 `additional_label_issues.csv`：目的選取的肯定案例及額外標籤疑點。',
        '- `validation.json`、`sample_composition.csv`、`emotion_statistics_AI.csv`：品質、組成及整體情緒（與主題態度分開）。',
        '', '尚未驗證抽樣母體、抽樣過程、來源介面或標籤產生流程，亦未同步 Google Drive 或修改原始 CSV。研究結論僅限指定樣本。']
    (output/'analysis_report.md').write_text('\n'.join(sections),encoding='utf-8')
    readme=['## Steam 中文玩家體驗分析｜階段成果','',
        '**AI 初判統計，尚待人工複核。** 研究使用 2026/08/01–2026/10/31（台灣時間）建立的 1,600 則 Steam 繁簡中文評論：Overwatch 500、Apex Legends 500、鳴潮 300、燕雲十六聲 300。樣本配額、評論 ID 唯一性與建立日期檢查通過；9 則原文於研究期後更新。','',
        '以「評論 × 主題」計數，同評論同主題只計一次，各主題占比以該款全部樣本為分母；「混合」另列，不併入批評。多主題占比可超過 100%。','',
        '- Overwatch：配對與排位批評 92／500（18.4%），帳號與平台 85／500（17.0%）。優先蒐證新玩家的配對落差與溝通環境。',
        '- Apex Legends：連線批評 44／500（8.8%），當機與啟動 37／500（7.4%）。優先蒐證掉線、重連及處罰流程。',
        '- 鳴潮：付費與抽卡批評 63／300（21.0%），優先查保底規則理解與成本感受。「內容與養成」原標 71／300（23.7%）有反覆誤分類，暫不據此推導內容問題排名。',
        '- 燕雲十六聲：內容與養成批評 35／300（11.7%），客服與營運 28／300（9.3%）；內容面向也有肯定 75／300（25.0%）、混合 38／300（12.7%）。優先查更新內容與材料解鎖時程的銜接。','',
        '助理抽查 24 個評論×主題案例，並對鳴潮內容面向補查 10 則。這是 AI 助理再次閱讀原文，未冒充人工驗證；原標籤保留，人工確認欄留白。另見肯定標籤誤判，正反比例均需人工確認。細項比例須等完整標記後再算。','',
        '正面案例包含 Apex 戰鬥手感、Overwatch 新模式、燕雲路線規劃與鳴潮畫面表現；案例不代表整體比例。建議皆為下一步調查事項，修復排序需結合營運資料與 QA 重現。結論僅限本樣本，不代表所有平台或所有玩家。']
    (output/'README_summary.md').write_text('\n'.join(readme),encoding='utf-8')
    return summary

def export_extra_evidence(df, output):
    selected={'237431132':'Apex 戰鬥肯定','237241641':'Overwatch 新模式肯定',
              '232274254':'燕雲路線規劃肯定','232285054':'鳴潮畫面肯定'}
    evidence=df[df.review_id.isin(selected)].copy()
    evidence['用途']=evidence.review_id.map(selected)
    evidence['選例方式']='目的選例；不是隨機抽查，不估計比例'
    evidence[['game','review_id','各主題態度_AI','review','用途','選例方式']].to_csv(Path(output)/'evidence_examples.csv',index=False,encoding='utf-8-sig')
    issues={'231976333':'原文批評新模式，與內容肯定標籤不符。',
            '234215648':'僅肯定風景，不足以獨立支持內容養成肯定。'}
    extra=df[df.review_id.isin(issues)].copy()
    extra['助理觀察']=extra.review_id.map(issues)
    extra['人工確認']='待確認'
    extra[['game','review_id','各主題態度_AI','review','助理觀察','人工確認']].to_csv(Path(output)/'additional_label_issues.csv',index=False,encoding='utf-8-sig')

def run_analysis(path, output, notes):
    df,long,validation=validate_and_expand(path,output)
    stats,top5,positive,emotions,sensitivity=summarize(df,long,output)
    make_figures(stats,output)
    checks=export_review(df,long,stats,notes,output)
    export_extra_evidence(df,output)
    summary=build_report(df,stats,top5,positive,emotions,sensitivity,validation,checks,output)
    print('PASS: sample counts, unique IDs, required fields, dates, topic alignment, quote provenance')
    print(f'Exported {len(long)} unique review-topic pairs, {len(checks)} review checks to {output}')
    return df,long,stats,top5,positive,emotions,sensitivity,checks,summary,validation

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    input_path=Path(sys.argv[1]) if len(sys.argv)>1 else root/'steam_chinese_1600_semantic_v02.csv'
    output=Path(sys.argv[2]) if len(sys.argv)>2 else root/'results'
    notes=json.loads((root/'review_notes.json').read_text(encoding='utf-8'))
    run_analysis(input_path,output,notes)
