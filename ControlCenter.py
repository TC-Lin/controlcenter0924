import streamlit as st
import pandas as pd
import plotly.express as px
import os # 新增 os 模組用來處理檔案
# ==========================================
# --- 系統預設值與後台設定檔邏輯 ---
# ==========================================
CONFIG_FILE = "marquee_thresholds.csv"

# 若設定檔不存在，系統自動建立一份預設的層級與金額
if not os.path.exists(CONFIG_FILE):
    default_data = {
        "層級": ["總管理中心", "總管理中心", "地區營運中心", "地區營運中心", "地區營運中心", "地區營運中心", "分行", "分行", "分行", "分行"],
        "職位": ["總經理", "副總經理", "營運長", "副營運長", "襄理", "科長", "經理", "副理", "襄理", "科長"],
        "通報門檻_元": [500000000, 200000000, 100000000, 50000000, 30000000, 10000000, 50000000, 30000000, 10000000, 5000000]
    }
    pd.DataFrame(default_data).to_csv(CONFIG_FILE, index=False)

# 讀取最新的門檻設定
threshold_df = pd.read_csv(CONFIG_FILE)
# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="全行業務戰情室", layout="wide")
st.title("🏦 全行業務與績效戰情看板 (Demo版)")
st.markdown("---")

# --- 2. 側邊欄：資料導入 ---
st.sidebar.header("📂 資料導入")
uploaded_file = st.sidebar.file_uploader("請上傳最新業務資料表 (Excel)", type=["xlsx"])

if uploaded_file:
    # 讀取與清理資料
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()
    # 🌟 新增：清洗「分行」與「行員」代號，去除小數點並替換特定代號
    if '分行' in df.columns:
        # 轉為字串後，將結尾的 .0 去除
        df['分行'] = df['分行'].astype(str).str.replace(r'\.0$', '', regex=True)
        
    if '行員' in df.columns:
        # 轉為字串後，將結尾的 .0 去除
        df['行員'] = df['行員'].astype(str).str.replace(r'\.0$', '', regex=True)
    
    # 教 Python 看懂「萬」與「億」的轉換邏輯
    def parse_money(val):
        val_str = str(val).replace(',', '').strip()
        if '億' in val_str:
            return float(val_str.replace('億', '')) * 100000000
        elif '萬' in val_str:
            return float(val_str.replace('萬', '')) * 10000
        else:
            try:
                return float(val_str)
            except:
                return 0

    # 🌟 關鍵調整：將所有可能包含「萬/億」的欄位，統統交給 parse_money 處理
    money_columns = ['通報金額', '成案金額', '存款餘額', '授信餘額', '基金餘額', '本月購買基金', '貢獻']
    
    for col in money_columns:
        if col in df.columns:
            df[col] = df[col].apply(parse_money)
    # 確保其他數值欄位格式正確
    
    numeric_cols = ['存款餘額', '授信餘額', '基金餘額', '本月購買基金', '貢獻', '成案金額']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- 3. 模擬登入身分 ---
# --- 模擬登入身分與權限過濾 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔐 模擬登入身分")
    
    # 1. 選擇單位層級 (簡化名稱以對應設定檔)
    role_level = st.sidebar.radio(
        "選擇單位層級",
        ["總管理中心", "地區營運中心", "分行"]
    )
    
    # 🌟 關鍵修復：依據層級，過濾出該使用者能看到的資料範圍 (產生 filtered_df)
    filtered_df = df.copy() 
    selected_region = "全區"
    selected_branch = "全行"
    
    if role_level == "地區營運中心":
        allowed_regions = df['區別'].dropna().unique()
        selected_region = st.sidebar.selectbox("請選擇您的管轄區", allowed_regions)
        filtered_df = df[df['區別'] == selected_region]
        st.sidebar.success(f"目前權限：已鎖定【{selected_region}】轄下資料")
        
    elif role_level == "分行":
        allowed_branches = df['分行'].dropna().unique()
        selected_branch = st.sidebar.selectbox("請選擇您的分行", allowed_branches)
        filtered_df = df[df['分行'] == selected_branch]
        st.sidebar.success(f"目前權限：已鎖定【{selected_branch}】內部資料")

    # 2. 動態連動：根據選到的層級，去設定檔抓出對應的「職位」選單
    available_titles = threshold_df[threshold_df['層級'] == role_level]['職位'].tolist()
    user_title = st.sidebar.selectbox("選擇您的職位", available_titles)
    
    # 3. 找出當前使用者的跑馬燈門檻金額
    current_threshold = threshold_df[(threshold_df['層級'] == role_level) & (threshold_df['職位'] == user_title)]['通報門檻_元'].values[0]
    st.sidebar.caption(f"🔔 您目前的跑馬燈追蹤門檻：大於 {current_threshold:,.0f} 元")

    # ==========================================
    # --- UI 後台管理介面 (不需改程式碼即可調整金額) ---
    # ==========================================
    with st.sidebar.expander("⚙️ 管理員後台 (調整門檻)"):
        st.write("直接在下方表格修改金額，然後點擊儲存：")
        edited_thresholds = st.data_editor(threshold_df, num_rows="dynamic", hide_index=True)
        if st.button("💾 儲存新門檻"):
            edited_thresholds.to_csv(CONFIG_FILE, index=False)
            st.success("✅ 門檻設定已更新！(請重新整理網頁套用)")
 # ==========================================
    # --- 新增：重大追蹤案跑馬燈 (追蹤下級進度) ---
    # ==========================================
    # 1. 條件改為判斷「通報金額」是否大於門檻
    pending_cases = filtered_df[
        (filtered_df['成案'] != '有') & 
        (filtered_df['通報金額'] >= current_threshold)
    ].copy()
    
    # 2. 抓出「通報金額」最大的前 5 筆重大案件
    top_pending = pending_cases.sort_values(by='通報金額', ascending=False).head(5)

    if not top_pending.empty:
        marquee_texts = []
        for _, row in top_pending.iterrows():
            # 3. 顯示文字改為通報金額
            amount_str = f"{row['通報金額']:,.0f}"
            text = f"🔥 【{row['分行']}】{row['行員']} 於 {row['日期']} 呈報 {row['通報業務']} 案件 (通報金額: ${amount_str}) - 目前狀態: {row['成案']}"
            marquee_texts.append(text)
            
        marquee_content = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;".join(marquee_texts)
        
        st.markdown(f"""
            <div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 6px solid #ffc107; margin-bottom: 20px;">
                <marquee scrollamount="6" style="font-size: 18px; font-weight: bold; color: #856404;">
                    {marquee_content}
                </marquee>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"✅ 目前轄下無大於 {current_threshold:,.0f} 元之重大追蹤案件。")
        
        
    # --- 4. 頂部核心 KPI (依據權限自動變動) ---
    st.subheader(f"🎯 核心指標 ({role_level.split(' ')[0]})")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏦 總存款餘額", f"${filtered_df['存款餘額'].sum():,.0f}")
    with col2:
        st.metric("🤝 總授信餘額", f"${filtered_df['授信餘額'].sum():,.0f}")
    with col3:
        st.metric("📈 總基金餘額", f"${filtered_df['基金餘額'].sum():,.0f}")
    with col4:
        st.metric("🌟 總貢獻值", f"{filtered_df['貢獻'].sum():,.0f}")
    
    st.markdown("---")

    # --- 5. 智慧鑽取分析區 (核心功能) ---
    tab1, tab2, tab3 = st.tabs(["🗺️ 組織層級鑽取", "📊 業務成案佔比", "🧑‍💼 行員戰鬥力總表"])
    
    with tab1:
        # 確保「組別」欄位格式乾淨，排除空值或橫線
        if '組別' in filtered_df.columns:
            filtered_df['組別'] = filtered_df['組別'].astype(str).str.strip()
        
        # ==========================================
        # 情境一：總管理中心視角 (地區 / 規模 / 全行)
        # ==========================================
        if role_level == "總管理中心":
            # 建立次頁籤
            sub_tab1, sub_tab2, sub_tab3 = st.tabs(["🗺️ 地區分組貢獻", "🏢 規模分組貢獻", "🏦 全國分行總覽"])
            
            with sub_tab1:
                st.markdown("### 🗺️ 各地區餘額總覽 (點擊色塊展開分行明細)")
                # 1. 主圖表
                region_perf = filtered_df.groupby('區別')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                fig_hq_reg = px.bar(region_perf, x='區別', y=['存款餘額', '授信餘額', '基金餘額'], barmode='group', text_auto=True)
                fig_hq_reg.update_xaxes(type='category')
                fig_hq_reg.update_yaxes(rangemode='nonnegative')
                event_hq_reg = st.plotly_chart(fig_hq_reg, on_select="rerun", key="hq_reg_view", use_container_width=True)
                
                # 2. 點擊後展開的分行明細圖表
                if event_hq_reg and event_hq_reg.selection.get("points"):
                    clicked_region = event_hq_reg.selection["points"][0]["x"]
                    st.markdown("---")
                    st.markdown(f"#### 📍 【{clicked_region}】轄下分行餘額資料")
                    branch_df = filtered_df[filtered_df['區別'] == clicked_region]
                    b_perf = branch_df.groupby('分行')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                    fig_reg_detail = px.bar(b_perf, x='分行', y=['存款餘額', '授信餘額', '基金餘額'], barmode='group', text_auto=True)
                    fig_reg_detail.update_xaxes(type='category')
                    fig_reg_detail.update_yaxes(rangemode='nonnegative')
                    st.plotly_chart(fig_reg_detail, use_container_width=True, key="hq_reg_detail")
                    
            with sub_tab2:
                st.markdown("### 🏢 各規模群組餘額總覽 (點擊色塊展開分行明細)")
                # 1. 主圖表
                valid_group_df = filtered_df[~filtered_df['組別'].isin(['—', '-', 'nan', ''])].copy()
                scale_perf = valid_group_df.groupby('組別')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                fig_hq_scale = px.bar(scale_perf, x='組別', y=['存款餘額', '授信餘額', '基金餘額'], barmode='group', text_auto=True)
                fig_hq_scale.update_xaxes(type='category')
                fig_hq_scale.update_yaxes(rangemode='nonnegative')
                event_hq_scale = st.plotly_chart(fig_hq_scale, on_select="rerun", key="hq_scale_view", use_container_width=True)
                
                # 2. 點擊後展開的分行明細圖表
                if event_hq_scale and event_hq_scale.selection.get("points"):
                    clicked_group = event_hq_scale.selection["points"][0]["x"]
                    st.markdown("---")
                    st.markdown(f"#### 🏢 【第 {clicked_group} 組】轄下分行餘額資料")
                    g_branch_df = valid_group_df[valid_group_df['組別'] == clicked_group]
                    g_b_perf = g_branch_df.groupby('分行')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                    fig_scale_detail = px.bar(g_b_perf, x='分行', y=['存款餘額', '授信餘額', '基金餘額'], barmode='group', text_auto=True)
                    fig_scale_detail.update_xaxes(type='category')
                    fig_scale_detail.update_yaxes(rangemode='nonnegative')
                    st.plotly_chart(fig_scale_detail, use_container_width=True, key="hq_scale_detail")
                    
            with sub_tab3:
                st.markdown("### 🏦 全國分行餘額總覽")
                # 1. 抓出所有餘額欄位進行加總
                all_branch_perf = filtered_df.groupby('分行')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                
                # 2. 將 y 軸設為清單，並加入 barmode='group'
                fig_hq_all = px.bar(
                    all_branch_perf, 
                    x='分行', 
                    y=['存款餘額', '授信餘額', '基金餘額'], 
                    barmode='group',
                    text_auto=True
                )
                
                fig_hq_all.update_xaxes(type='category')
                fig_hq_all.update_yaxes(rangemode='nonnegative')
                st.plotly_chart(fig_hq_all, use_container_width=True, key="hq_all_view")
        # ==========================================
        # 情境二：地區營運中心視角 (規模 / 該區全分行)
        # ==========================================
        elif role_level == "地區營運中心":
            sub_tab1, sub_tab2 = st.tabs(["🏢 轄區規模分組貢獻", "🏦 轄區全分行總覽"])
            
            with sub_tab1:
                st.markdown(f"### 🏢 【{selected_region}】各規模群組餘額總覽 (點擊色塊展開)")
                # 1. 主圖表
                valid_group_df = filtered_df[~filtered_df['組別'].isin(['—', '-', 'nan', ''])].copy()
                scale_perf = valid_group_df.groupby('組別')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                fig_reg_scale = px.bar(scale_perf, x='組別', y=['存款餘額', '授信餘額', '基金餘額'], barmode='group', text_auto=True)
                fig_reg_scale.update_xaxes(type='category')
                fig_reg_scale.update_yaxes(rangemode='nonnegative')
                event_reg_scale = st.plotly_chart(fig_reg_scale, on_select="rerun", key="reg_scale_view", use_container_width=True)
                
                # 2. 點擊後展開的分行明細圖表
                if event_reg_scale and event_reg_scale.selection.get("points"):
                    clicked_group = event_reg_scale.selection["points"][0]["x"]
                    st.markdown("---")
                    st.markdown(f"#### 🏢 {selected_region}【第 {clicked_group} 組】分行餘額資料")
                    g_branch_df = valid_group_df[valid_group_df['組別'] == clicked_group]
                    g_b_perf = g_branch_df.groupby('分行')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                    fig_reg_scale_detail = px.bar(g_b_perf, x='分行', y=['存款餘額', '授信餘額', '基金餘額'], barmode='group', text_auto=True)
                    fig_reg_scale_detail.update_xaxes(type='category')
                    fig_reg_scale_detail.update_yaxes(rangemode='nonnegative')
                    st.plotly_chart(fig_reg_scale_detail, use_container_width=True, key="reg_scale_detail")
                    
            with sub_tab2:
                st.markdown(f"### 🏦 【{selected_region}】轄區全分行餘額總覽 (點擊展開行員)")
                # 1. 抓出所有餘額欄位進行加總
                branch_perf = filtered_df.groupby('分行')[['存款餘額', '授信餘額', '基金餘額']].sum().reset_index()
                
                # 2. 將 y 軸設為清單，並加入 barmode='group'
                fig_reg_all = px.bar(
                    branch_perf, 
                    x='分行', 
                    y=['存款餘額', '授信餘額', '基金餘額'], 
                    barmode='group',
                    text_auto=True
                )
                
                fig_reg_all.update_xaxes(type='category')
                fig_reg_all.update_yaxes(rangemode='nonnegative')
                event_reg_all = st.plotly_chart(fig_reg_all, on_select="rerun", key="reg_all_view", use_container_width=True)
        # ==========================================
        # 情境三：分行經理視角 (直接看行員)
        # ==========================================
        else:
            st.markdown(f"### 🧑‍💼 【{selected_branch}】行員貢獻總覽")
            clerk_perf = filtered_df.groupby('行員')['貢獻'].sum().reset_index().sort_values(by='貢獻', ascending=False)
            fig_branch_mgr = px.bar(clerk_perf, x='行員', y='貢獻', color='行員', text_auto=True)
            
            fig_branch_mgr.update_xaxes(type='category')
            fig_branch_mgr.update_yaxes(rangemode='nonnegative')
            st.plotly_chart(fig_branch_mgr, use_container_width=True)
    # --- 6. 其他共同維度分析 ---
    with tab2:
        st.markdown("### 📊 業務成案狀態分佈")
        status_counts = filtered_df['成案'].value_counts().reset_index()
        status_counts.columns = ['成案', '案件數']
        fig_status = px.pie(status_counts, names='成案', values='案件數', hole=0.4)
        st.plotly_chart(fig_status, use_container_width=True)

    with tab3:
        st.markdown("### 🏆 轄下行員戰力排行榜 (熱力圖)")
        clerk_table = filtered_df.groupby(['分行', '科別', '行員']).agg(
            總貢獻=('貢獻', 'sum'),
            總成案金額=('成案金額', 'sum'),
            通報案件=('通報業務', 'count')
        ).reset_index().sort_values(by='總貢獻', ascending=False)
        
        st.dataframe(
            clerk_table.style.background_gradient(cmap='Blues', subset=['總貢獻', '總成案金額']),
            use_container_width=True,
            hide_index=True
        )
        
        #st.dataframe(
        #    clerk_table,
        #    use_container_width=True,
        #    hide_index=True
        #)


else:
    st.info("請從左側上傳您的資料表以啟動戰情室。")