"""
广交会智能外贸撮合系统 - Streamlit 主程序
设计风格：企业级深色科技风 + 数据仪表盘
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os, sys, time, datetime, json, re
from collections import Counter

# ====== 健康检查端点（独立于 Streamlit 主路由）=======
if os.environ.get("ENABLE_STANDALONE_HEALTH") == "1":
    import http.server
    import socketserver
    import threading

    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, *args): pass

    def run_health_server():
        with socketserver.TCPServer(("", 8503), HealthHandler) as httpd:
            httpd.serve_forever()

    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()

# ====== 页面配置 ======
st.set_page_config(
    page_title="CantonFair Pro — 智能外贸撮合系统",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====== 自定义 CSS ======
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    :root {
        --primary: #2563EB;
        --primary-dark: #1D4ED8;
        --accent: #10B981;
        --accent2: #F59E0B;
        --bg-dark: #0F172A;
        --bg-card: #1E293B;
        --bg-card2: #334155;
        --text: #F1F5F9;
        --text-muted: #94A3B8;
        --border: #334155;
        --gold: #F59E0B;
        --blue-tier: #3B82F6;
        --green-tier: #22C55E;
        --orange-tier: #F97316;
        --gray-tier: #6B7280;
    }

    * { font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif !important; }

    body { background: var(--bg-dark); color: var(--text); }

    .stApp { background: var(--bg-dark); }

    /* 卡片样式 */
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 20px 24px;
        margin: 8px 0;
        text-align: center;
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); border-color: #2563EB; }
    .metric-card h3 { font-size: 12px; color: #94A3B8; text-transform: uppercase;
                      letter-spacing: 1px; margin: 0 0 8px 0; font-weight: 500; }
    .metric-card h1 { font-size: 32px; margin: 0; font-weight: 700; }
    .metric-card .sub { font-size: 13px; color: #64748B; margin-top: 4px; }
    .metric-card .delta { font-size: 12px; padding: 2px 8px; border-radius: 10px;
                          display: inline-block; margin-top: 4px; }

    .stMetric { background: transparent !important; }
    .stMetric label { color: #94A3B8 !important; font-size: 12px !important;
                       text-transform: uppercase; letter-spacing: 1px !important; }
    .stMetric [data-testid="stMetricValue"] { color: #F1F5F9 !important; font-weight: 700 !important; }

    /* Sidebar */
    [data-testid="stSidebar"] { background: #0F172A !important; border-right: 1px solid #1E293B; }
    [data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label, [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span { color: #94A3B8 !important; }

    /* 按钮 */
    .stButton > button {
        background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 20px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
        box-shadow: 0 4px 12px rgba(37,99,235,0.3) !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(37,99,235,0.5) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; background: #1E293B; border-radius: 12px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px !important; color: #94A3B8 !important;
                                    font-weight: 500 !important; padding: 6px 16px !important; }
    .stTabs [aria-selected="true"] { background: #2563EB !important; color: white !important; }

    /* DataFrames */
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
    .dataframe { border: none !important; }
    .dataframe thead th { background: #1E293B !important; color: #94A3B8 !important;
                           font-weight: 600 !important; font-size: 12px !important;
                           text-transform: uppercase !important; letter-spacing: 0.5px !important;
                           border-bottom: 1px solid #334155 !important; padding: 10px 12px !important; }
    .dataframe tbody tr:hover { background: #1E293B !important; }
    .dataframe tbody td { border-bottom: 1px solid #1E293B !important;
                          color: #E2E8F0 !important; padding: 8px 12px !important; }

    /* Headers */
    h1, h2, h3 { color: #F1F5F9 !important; }
    h1 { font-size: 28px !important; font-weight: 800 !important; }
    h2 { font-size: 20px !important; font-weight: 700 !important; border-bottom: 2px solid #2563EB;
         padding-bottom: 8px !important; }
    h3 { font-size: 16px !important; font-weight: 600 !important; }

    /* Info boxes */
    .info-box { background: #1E293B; border-left: 4px solid #2563EB; padding: 16px; border-radius: 0 12px 12px 0; margin: 12px 0; }
    .success-box { background: #1E293B; border-left: 4px solid #10B981; padding: 16px; border-radius: 0 12px 12px 0; margin: 12px 0; }
    .warn-box { background: #1E293B; border-left: 4px solid #F59E0B; padding: 16px; border-radius: 0 12px 12px 0; margin: 12px 0; }

    /* Plotly chart backgrounds */
    .js-plotly-plot .plotly, .js-plotly-plot .plotly div { background: transparent !important; }

    /* 滚动条 */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #1E293B; }
    ::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }

    /* 进度条 */
    .stProgress > div > div { background: linear-gradient(90deg, #2563EB, #10B981) !important; }

    /* Expanders */
    .streamlit-expanderHeader { background: #1E293B !important; border-radius: 12px !important;
                                 color: #E2E8F0 !important; }
</style>
""", unsafe_allow_html=True)

# ====== 路径设置 ======
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)  # cantonfair_system/
DATA_FILE = os.environ.get('DATA_FILE_PATH',
    os.path.join(PROJECT_DIR, '广交会数据综合整理_标准格式.xlsx'))
sys.path.insert(0, PROJECT_DIR)

# ====== 认证检查 ======
try:
    from auth import inject_auth_check
    inject_auth_check()
except ImportError:
    pass  # 本地开发模式无认证


def _render_auth():
    try:
        from auth import is_authenticated, render_auth_sidebar, logout_user
        if is_authenticated():
            render_auth_sidebar()
    except ImportError:
        pass

# ====== 缓存数据 ======
@st.cache_data(ttl=3600)
def load_all_data():
    import traceback
    from data.data_loader import get_loader
    try:
        loader = get_loader(DATA_FILE)
        buyers = loader.load_buyers()
        exhibitors = loader.load_exhibitors()
        pairing = loader.load_pairing_data()
        analysis = loader.load_analysis_data()
        country_stats = loader.load_country_stats()

        # 确保关键列存在（双重保护）
        if buyers is not None and isinstance(buyers, pd.DataFrame):
            if '合作意向_final' not in buyers.columns:
                buyers = buyers.copy()
                buyers['合作意向_final'] = '意向待定'

        # 尝试获取统计数据，如果失败则使用默认值
        try:
            stats = loader.get_stats()
        except Exception as stats_error:
            print(f"get_stats failed: {stats_error}")
            # 返回默认统计数据
            stats = {
                'buyer_count': len(buyers) if buyers is not None else 0,
                'exhibitor_count': len(exhibitors) if exhibitors is not None else 0,
                'buyer_with_email': 0, 'buyer_with_phone': 0,
                'buyer_with_wa': 0, 'high_intent_buyers': 0,
                'two_session_buyers': 0, 'exhibitors_two_session': 0,
                'continents': {},
            }

        return buyers, exhibitors, pairing, analysis, country_stats, stats
    except Exception as e:
        # 显示完整错误信息用于调试
        error_detail = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        raise Exception(f"数据加载失败: {error_detail}")

@st.cache_data(ttl=300)
def search_buyers(buyers_df, country=None, category=None, tier=None,
                  intent=None, has_contact=None, search_text=''):
    df = buyers_df.copy()

    # 确保必要的衍生列存在
    if '合作意向_final' not in df.columns:
        if '参展届次' in df.columns:
            def _infer_intent(s):
                if pd.isna(s) or str(s).strip() == '':
                    return '意向待定'
                sessions = str(s)
                if ';' in sessions:
                    return '高意向（多届参展）'
                return '一般意向'
            df['合作意向_final'] = df['参展届次'].apply(_infer_intent)
        else:
            df['合作意向_final'] = '意向待定'

    if country and country != '全部':
        df = df[df['国家/地区'] == country]
    if category and category != '全部':
        df = df[df['主营品类'].fillna('').str.contains(category[:4], na=False)]
    if tier and tier != '全部':
        if '综合评分' in df.columns:
            if tier == 'S级': df = df[df['综合评分'] >= 80]
            elif tier == 'A级': df = df[(df['综合评分'] >= 65) & (df['综合评分'] < 80)]
            elif tier == 'B级': df = df[(df['综合评分'] >= 50) & (df['综合评分'] < 65)]
            elif tier == 'C级': df = df[(df['综合评分'] >= 35) & (df['综合评分'] < 50)]
            else: df = df[df['综合评分'] < 35]
    if intent and intent != '全部':
        df = df[df['合作意向_final'].str.contains(intent[:2], na=False)]
    if has_contact == '有邮箱':
        df = df[df['联系方式-邮箱'].notna() & (df['联系方式-邮箱'] != '')]
    elif has_contact == '有电话':
        df = df[df['联系方式-电话'].notna() & (df['联系方式-电话'] != '')]
    elif has_contact == '有WhatsApp':
        df = df[df['联系方式-WhatsApp'].notna() & (df['联系方式-WhatsApp'] != '')]
    if search_text:
        mask = (df['采购商企业全称'].fillna('').str.contains(search_text, case=False, na=False) |
                df['联系人'].fillna('').str.contains(search_text, case=False, na=False) |
                df['主营品类'].fillna('').str.contains(search_text, case=False, na=False))
        df = df[mask]
    return df

@st.cache_data(ttl=300)
def search_exhibitors(exhibitors_df, province=None, etype=None, search_text=''):
    df = exhibitors_df.copy()
    if province and province != '全部':
        df = df[df['省份'] == province]
    if etype and etype != '全部':
        df = df[df['企业类型'].fillna('').str.contains(etype, na=False)]
    if search_text:
        mask = (df['展商名称'].fillna('').str.contains(search_text, case=False, na=False) |
                df['主营产品'].fillna('').str.contains(search_text, case=False, na=False))
        df = df[mask]
    return df

# ====== 侧边栏 ======
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 16px 0;">
        <div style="font-size:32px;">🏭</div>
        <div style="font-size:20px; font-weight:800; color:#F1F5F9; margin-top:8px;">
            CantonFair Pro
        </div>
        <div style="font-size:12px; color:#64748B; margin-top:4px;">
            智能外贸撮合系统 v1.0
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "功能导航",
        [
            "📊 数据总览",
            "🔍 采购商搜索",
            "🏭 参展商搜索",
            "🤝 智能匹配",
            "⭐ 客户评分",
            "📞 外呼管理",
            "🧠 AI 智能搜索",
            "⚙️ 系统设置",
        ],
        index=0,
        label_visibility="collapsed"
    )

    st.divider()

    # 渲染认证状态
    try:
        from auth import is_authenticated, render_auth_sidebar, logout_user, get_current_user
        if is_authenticated():
            user = get_current_user()
            st.caption(f"👤 {user}")
            if st.button("退出登录", use_container_width=True):
                logout_user()
                st.rerun()
    except ImportError:
        pass

    # 数据状态
    with st.expander("ℹ️ 数据状态", expanded=False):
        st.caption(f"数据文件: `{os.path.basename(DATA_FILE)}`")
        st.caption(f"更新时间: {datetime.datetime.now().strftime('%Y-%m-%d')}")
        st.caption("缓存: 自动刷新")

# ====== 全局加载数据 ======
# DEBUG MARKER: 如果看到这个标记，说明代码已更新 - 2026-05-14 16:45
try:
    buyers, exhibitors, pairing, analysis, country_stats, stats = load_all_data()
    data_loaded = True
except Exception as e:
    data_loaded = False
    st.error(f"数据加载失败 (更新版本): {e}")
    st.markdown("""
    ---
    ### 🔧 配置指南

    请在 Streamlit Cloud 的 **Settings → Secrets** 中配置以下环境变量：

    ```
    # Supabase 连接信息（从 Supabase 项目设置 → API 获取）
    SUPABASE_URL = "https://your-project.supabase.co"
    SUPABASE_KEY = "your-anon-key"
    SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"

    # 应用信息（可选）
    APP_NAME = "CantonFair Pro"
    APP_VERSION = "1.0.0"
    ```

    **获取 Supabase 密钥：**
    1. 登录 [Supabase](https://supabase.com/dashboard)
    2. 进入你的项目 → Settings → API
    3. 复制 Project URL 和 `anon` / `service_role` public key
    """)

    # 提供清除缓存重试
    st.warning("💡 如果刚配置完 Secrets，请点击下方按钮清除缓存并重试：")
    if st.button("🗑️ 清除缓存并重试"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# ============================================================
# 页面1: 数据总览
# ============================================================
if page == "📊 数据总览":
    st.title("📊 数据总览")

    # 顶部指标卡
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("采购商总数", f"{stats['buyer_count']:,}", f"有效联系 {stats['buyer_with_email']+stats['buyer_with_wa']:,}")
    with col2:
        st.metric("参展商总数", f"{stats['exhibitor_count']:,}", f"两届参展 {stats['exhibitors_two_session']:,}")
    with col3:
        st.metric("有邮箱采购商", f"{stats['buyer_with_email']:,}", f"覆盖率 {stats['buyer_with_email']/stats['buyer_count']*100:.1f}%")
    with col4:
        st.metric("有电话采购商", f"{stats['buyer_with_phone']:,}", f"覆盖率 {stats['buyer_with_phone']/stats['buyer_count']*100:.1f}%")
    with col5:
        st.metric("高意向采购商", f"{stats['high_intent_buyers']:,}", f"两届到场 {stats['two_session_buyers']:,}")

    st.divider()

    # 图表区
    tab1, tab2, tab3, tab4 = st.tabs(["🌍 采购商国家分布", "📦 品类分布", "📈 趋势分析", "🏆 TOP品类机会"])

    with tab1:
        st.subheader("采购商来源国家分布 TOP 20")
        if not country_stats.empty:
            top_countries = country_stats.head(20)
            fig = px.bar(
                top_countries,
                x='国家/地区', y='采购商数量',
                color='市场类型',
                color_discrete_map={'发达':'#2563EB', '新兴':'#10B981'},
                template='plotly_dark'
            )
            fig.update_layout(
                plot_bgcolor='transparent', paper_bgcolor='transparent',
                font=dict(color='#E2E8F0'),
                height=500,
                xaxis=dict(tickangle=-45),
                showlegend=True,
                legend=dict(title_text='市场类型')
            )
            fig.update_traces(marker=dict(opacity=0.85, line=dict(width=0)))
            st.plotly_chart(fig, use_container_width=True)

            col_a, col_b = st.columns(2)
            with col_a:
                fig_pie = px.pie(
                    country_stats.head(10),
                    values='采购商数量', names='国家/地区',
                    hole=0.4, template='plotly_dark',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_pie.update_layout(
                    plot_bgcolor='transparent', paper_bgcolor='transparent',
                    font=dict(color='#E2E8F0'), height=400
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_b:
                # 大洲分布
                cont_dist = buyers['大洲'].value_counts()
                fig_cont = px.pie(
                    names=cont_dist.index, values=cont_dist.values,
                    hole=0.4, template='plotly_dark',
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_cont.update_layout(
                    plot_bgcolor='transparent', paper_bgcolor='transparent',
                    font=dict(color='#E2E8F0'), height=400,
                    title='大洲分布'
                )
                st.plotly_chart(fig_cont, use_container_width=True)

    with tab2:
        st.subheader("品类采购商分布")
        if '主营品类' in buyers.columns:
            cat_dist = buyers['主营品类'].value_counts().head(20)
            fig_cat = px.bar(
                x=cat_dist.values, y=cat_dist.index,
                orientation='h', template='plotly_dark',
                color=cat_dist.values,
                color_continuous_scale='Blues'
            )
            fig_cat.update_layout(
                plot_bgcolor='transparent', paper_bgcolor='transparent',
                font=dict(color='#E2E8F0'), height=600,
                xaxis_title='采购商数量', showlegend=False,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_cat, use_container_width=True)

    with tab3:
        st.subheader("采购商意向与类型分析")
        col1, col2 = st.columns(2)
        with col1:
            intent_col = buyers['合作意向_final'] if '合作意向_final' in buyers.columns else pd.Series(['意向待定'] * len(buyers))
            intent_dist = intent_col.value_counts()
            fig_int = px.pie(
                names=intent_dist.index, values=intent_dist.values,
                hole=0.5, template='plotly_dark',
                color_discrete_map={
                    '高意向（紧急找货）':'#10B981',
                    '中意向（选品备货）':'#F59E0B',
                    '低意向（市场调研）':'#6B7280'
                }
            )
            fig_int.update_layout(
                plot_bgcolor='transparent', paper_bgcolor='transparent',
                font=dict(color='#E2E8F0'), height=400
            )
            st.plotly_chart(fig_int, use_container_width=True)
        with col2:
            bt_dist = buyers['采购商类型_final'].value_counts().head(8)
            fig_bt = px.bar(
                x=bt_dist.values, y=bt_dist.index,
                orientation='h', template='plotly_dark',
                color=bt_dist.values, color_continuous_scale='Teal'
            )
            fig_bt.update_layout(
                plot_bgcolor='transparent', paper_bgcolor='transparent',
                font=dict(color='#E2E8F0'), height=400,
                xaxis_title='数量', showlegend=False, coloraxis_showscale=False
            )
            st.plotly_chart(fig_bt, use_container_width=True)

    with tab4:
        st.subheader("品类撮合机会矩阵")
        if not analysis.empty:
            analysis_sorted = analysis.sort_values('品类', ascending=True)
            fig_matrix = px.scatter(
                analysis_sorted.head(25),
                x='参展商数', y='采购商数(两届合计)',
                size='供需比(采购商/参展商)' if '供需比(采购商/参展商)' in analysis_sorted.columns else None,
                color='品类',
                hover_name='品类',
                template='plotly_dark',
                size_max=50
            )
            fig_matrix.update_layout(
                plot_bgcolor='transparent', paper_bgcolor='transparent',
                font=dict(color='#E2E8F0'), height=500
            )
            st.plotly_chart(fig_matrix, use_container_width=True)

            # 表格展示
            st.dataframe(
                analysis_sorted[['品类','采购商数(两届合计)','参展商数','供需比(采购商/参展商)','撮合建议']].head(20),
                use_container_width=True, height=400,
                hide_index=True
            )

# ============================================================
# 页面2: 采购商搜索
# ============================================================
elif page == "🔍 采购商搜索":
    st.title("🔍 采购商搜索")

    col_f, col_c = st.columns([3, 1])
    with col_f:
        search_text = st.text_input("🔎 关键词搜索", placeholder="输入公司名/联系人/品类...", label_visibility="collapsed")
    with col_c:
        st.write("")
        if st.button("🚀 开始搜索", use_container_width=True):
            st.cache_data.clear()

    # 筛选栏
    with st.expander("🔧 高级筛选", expanded=True):
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        with fcol1:
            countries = ['全部'] + sorted(buyers['国家/地区'].dropna().unique().tolist())
            sel_country = st.selectbox("国家/地区", countries)
        with fcol2:
            cats = ['全部'] + sorted(buyers['主营品类'].dropna().unique().tolist())
            sel_cat = st.selectbox("采购品类", cats)
        with fcol3:
            sel_intent = st.selectbox("合作意向", ['全部','高意向（紧急找货）','中意向（选品备货）'])
        with fcol4:
            sel_contact = st.selectbox("联系方式", ['全部','有邮箱','有电话','有WhatsApp'])

    # 执行搜索
    filtered = search_buyers(buyers, sel_country, sel_cat, None, sel_intent, sel_contact, search_text)
    st.success(f"找到 {len(filtered):,} 条采购商记录")

    # 显示字段选择
    show_cols = st.multiselect(
        "显示字段（默认全部）",
        options=[c for c in filtered.columns if c not in ('Unnamed', 'index')],
        default=['采购商企业全称','联系人','国家/地区','大洲','主营品类','合作意向_final',
                 '联系方式-电话','联系方式-邮箱','联系方式-WhatsApp','参展届次']
    )

    if show_cols:
        display_df = filtered[show_cols].head(500).copy()
        display_df.columns = [c.replace('_final','').replace('联系方式-','') for c in display_df.columns]
        st.dataframe(display_df, use_container_width=True, height=500, hide_index=True)

        # 导出
        csv = filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 导出CSV",
            csv,
            f"采购商搜索结果_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )
    else:
        st.dataframe(filtered.head(100), use_container_width=True, height=500, hide_index=True)

# ============================================================
# 页面3: 参展商搜索
# ============================================================
elif page == "🏭 参展商搜索":
    st.title("🏭 参展商搜索")

    col_f, col_c = st.columns([3, 1])
    with col_f:
        ex_search = st.text_input("🔎 关键词搜索", placeholder="输入展商名/主营产品...", label_visibility="collapsed")
    with col_c:
        st.write("")
        if st.button("🚀 搜索", use_container_width=True):
            st.cache_data.clear()

    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        provinces = ['全部'] + sorted(exhibitors['省份'].dropna().unique().tolist())
        sel_prov = st.selectbox("省份", provinces)
    with fcol2:
        etypes = ['全部','源头工厂','工贸一体','纯外贸公司','品牌方','OEM/ODM代工厂']
        sel_etype = st.selectbox("企业类型", etypes)
    with fcol3:
        two_session = st.checkbox("仅两届均参展")

    filtered_ex = search_exhibitors(exhibitors, sel_prov, sel_etype, ex_search)
    if two_session:
        if '参展届次' in filtered_ex.columns:
            filtered_ex = filtered_ex[filtered_ex['参展届次'].str.contains(';', na=False)]

    st.success(f"找到 {len(filtered_ex):,} 家参展商")

    ex_cols = st.multiselect(
        "显示字段",
        options=[c for c in filtered_ex.columns if c not in ('Unnamed',)],
        default=['展商名称','省份','城市','企业类型','主营产品','海关认证展商','高新展商','品牌展商','创新奖','手机']
    )

    if ex_cols:
        st.dataframe(filtered_ex[ex_cols].head(300), use_container_width=True, height=500, hide_index=True)
        csv = filtered_ex.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 导出CSV",
            csv,
            f"参展商搜索结果_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )

# ============================================================
# 页面4: 智能匹配
# ============================================================
elif page == "🤝 智能匹配":
    st.title("🤝 智能供需匹配")

    st.markdown("""
    <div class="info-box">
    选择一个品类，系统将自动匹配该品类下的优质展商和采购商，并生成一对一对接建议。
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        match_cat = st.selectbox(
            "选择品类",
            options=sorted(buyers['主营品类'].dropna().unique().tolist())
        )
    with col2:
        match_top = st.slider("每方展示数量", 5, 50, 15)

    if st.button("🔄 开始匹配", use_container_width=True):
        from engine.matching import FastMatcher
        with st.spinner("正在匹配中..."):
            from data.data_loader import get_loader
            loader = get_loader(DATA_FILE)
            m = FastMatcher()
            m.build_index(loader.load_exhibitors(), loader.load_buyers())

            matched = m.batch_match_by_category_static(
                loader.load_exhibitors(), loader.load_buyers(),
                match_cat, top_ex=match_top, top_buyer=match_top
            )

            if not matched.empty:
                st.success(f"生成 {len(matched)} 条配对记录")
                st.dataframe(matched.head(100), use_container_width=True, height=500, hide_index=True)
                csv = matched.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 导出配对结果",
                    csv,
                    f"品类配对_{match_cat}_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
            else:
                st.warning("该品类暂无匹配数据")

    st.divider()
    st.subheader("📋 品类撮合分析（全部）")
    if not analysis.empty:
        analysis_d = analysis.copy()
        st.dataframe(
            analysis_d.sort_values('采购商数(两届合计)' if '采购商数(两届合计)' in analysis_d.columns else analysis_d.columns[0], ascending=False),
            use_container_width=True, height=500, hide_index=True
        )

# ============================================================
# 页面5: 客户评分
# ============================================================
elif page == "⭐ 客户评分":
    st.title("⭐ 客户评分与分层")

    st.markdown("""
    <div class="info-box">
    系统基于意向强度、触达可能性、市场价值和数据质量四个维度对客户进行综合评分，分为 S/A/B/C/D 五个等级。
    </div>
    """, unsafe_allow_html=True)

    tab_s, tab_b = st.tabs(["🏭 参展商评分", "🔍 采购商评分"])

    with tab_s:
        st.subheader("参展商价值评分")
        from engine.scoring import rank_exhibitors, get_tier_distribution
        if st.button("🔄 开始评分", use_container_width=True):
            with st.spinner("评分中，请稍候..."):
                ranked_ex = rank_exhibitors(exhibitors.head(5000))
                st.session_state['ranked_exhibitors'] = ranked_ex

        if 'ranked_exhibitors' in st.session_state:
            df = st.session_state['ranked_exhibitors']
            tier_dist = get_tier_distribution(df, '客户等级')
            cols = st.columns(5)
            tier_labels = [('S', '💎 钻石', '#F59E0B'), ('A', '⭐ 重点', '#3B82F6'),
                          ('B', '👍 优质', '#22C55E'), ('C', '📌 普通', '#F97316'), ('D', '📋 潜在', '#6B7280')]
            for (tier, label, color), col in zip(tier_labels, cols):
                cnt = tier_dist.get(tier, 0)
                col.markdown(f"""
                <div class="metric-card">
                    <h3>{label}</h3>
                    <h1 style="color:{color}">{cnt:,}</h1>
                    <div class="sub">{tier_dist.get(tier,0)/max(len(df),1)*100:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)

            disp_cols = ['展商名称','省份','企业类型_final','综合评分','触达分','价值分','客户等级','主营产品']
            avail = [c for c in disp_cols if c in df.columns]
            st.dataframe(df[avail].sort_values('综合评分', ascending=False).head(200),
                        use_container_width=True, height=500, hide_index=True)

    with tab_b:
        st.subheader("采购商价值评分")
        from engine.scoring import rank_buyers
        if st.button("🔄 评分采购商", use_container_width=True):
            with st.spinner("评分中..."):
                ranked_b = rank_buyers(buyers.head(5000))
                st.session_state['ranked_buyers'] = ranked_b

        if 'ranked_buyers' in st.session_state:
            df = st.session_state['ranked_buyers']
            tier_dist = get_tier_distribution(df, '客户等级')
            cols = st.columns(5)
            tier_labels = [('S', '💎 钻石', '#F59E0B'), ('A', '⭐ 重点', '#3B82F6'),
                          ('B', '👍 优质', '#22C55E'), ('C', '📌 普通', '#F97316'), ('D', '📋 潜在', '#6B7280')]
            for (tier, label, color), col in zip(tier_labels, cols):
                cnt = tier_dist.get(tier, 0)
                col.markdown(f"""
                <div class="metric-card">
                    <h3>{label}</h3>
                    <h1 style="color:{color}">{cnt:,}</h1>
                    <div class="sub">{tier_dist.get(tier,0)/max(len(df),1)*100:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)

            disp_cols = ['采购商企业全称','国家/地区','大洲','综合评分','意向分','触达分','价值分','客户等级','主营品类']
            avail = [c for c in disp_cols if c in df.columns]
            st.dataframe(df[avail].sort_values('综合评分', ascending=False).head(200),
                        use_container_width=True, height=500, hide_index=True)

# ============================================================
# 页面6: 外呼管理
# ============================================================
elif page == "📞 外呼管理":
    st.title("📞 外呼管理与线索跟踪")

    from outreach.tracking import OutreachManager, OUTREACH_TEMPLATES, generate_personalized_message

    save_path = os.path.join(APP_DIR, 'outreach_data.json')
    manager = OutreachManager(save_path)
    manager.recalc_stats()

    # 顶部统计
    stat_cols = st.columns(8)
    stat_items = [
        ("总线索", manager.stats['total'], "#94A3B8"),
        ("新线索", manager.stats['new'], "#2563EB"),
        ("已联系", manager.stats['contacted'], "#10B981"),
        ("有意向", manager.stats['interested'], "#F59E0B"),
        ("寄样中", manager.stats['sample'], "#8B5CF6"),
        ("洽谈中", manager.stats['negotiating'], "#EC4899"),
        ("已下单", manager.stats['ordered'], "#22C55E"),
        ("无效", manager.stats['invalid'], "#EF4444"),
    ]
    for (label, val, color), col in zip(stat_items, stat_cols):
        col.markdown(f"""
        <div class="metric-card" style="padding:14px 8px">
            <h3>{label}</h3>
            <h1 style="font-size:24px;color:{color}">{val}</h1>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📋 线索管理", "✉️ 批量导入线索", "📝 话术生成"])

    with tab1:
        st.subheader("我的线索")
        df = manager.to_dataframe()
        if not df.empty:
            disp = df[['contact_name','country','category','tier','status','score','phone','whatsapp','email']].head(200)
            st.dataframe(disp, use_container_width=True, height=400, hide_index=True)
        else:
            st.info("暂无线索，请先从采购商数据中导入")

        # 状态更新
        with st.expander("🔄 更新线索状态", expanded=True):
            ucol1, ucol2, ucol3, ucol4 = st.columns([2,2,2,1])
            with ucol1:
                update_id = st.text_input("线索ID")
            with ucol2:
                new_status = st.selectbox("新状态", [
                    "新线索","已联系","有意向","寄样中","洽谈中","已下单","跟进中","无效线索","黑名单"
                ])
            with ucol3:
                update_notes = st.text_input("备注")
            with ucol4:
                st.write("")
                if st.button("更新"):
                    if update_id:
                        manager.update_lead(update_id, new_status, notes=update_notes)
                        st.success("状态已更新")
                        st.rerun()

    with tab2:
        st.subheader("从采购商数据导入线索")
        imp_cols = st.columns([2,1])
        with imp_cols[0]:
            imp_cat = st.selectbox("选择品类", ['全部'] + sorted(buyers['主营品类'].dropna().unique().tolist()))
        with imp_cols[1]:
            imp_limit = st.number_input("导入数量上限", 10, 1000, 100)

        if st.button("📥 导入到线索池"):
            filt = buyers[buyers['主营品类'].fillna('').str.contains(imp_cat[:4], na=False)].head(imp_limit)
            manager.add_leads_from_df(filt)
            st.success(f"已导入 {len(filt)} 条线索到管理池")
            manager.recalc_stats()
            st.rerun()

    with tab3:
        st.subheader("个性化话术生成")
        tcol1, tcol2 = st.columns([1,1])
        with tcol1:
            tmpl_key = st.selectbox("选择话术模板", list(OUTREACH_TEMPLATES.keys()),
                                    format_func=lambda k: OUTREACH_TEMPLATES[k]['name'])
        with tcol2:
            tmpl_lang = st.radio("语言", ['cn','en'], format_func=lambda x: '🇨🇳 中文' if x=='cn' else '🇺🇸 英文',
                                 horizontal=True)

        tmpl = OUTREACH_TEMPLATES[tmpl_key]
        st.markdown(f"**适用渠道**: {', '.join(tmpl['channels'])}")

        tcol3, tcol4 = st.columns(2)
        with tcol3:
            tvar_contact = st.text_input("联系人/公司名", "Mr. Zhang")
            tvar_cat = st.text_input("品类", "工具")
            tvar_country = st.text_input("国家", "美国")
            tvar_count = st.text_input("采购商数量", "50")
        with tcol4:
            msg = generate_personalized_message(
                tmpl_key,
                {'contact_name': tvar_contact, 'category': tvar_cat,
                 'country': tvar_country, 'count': tvar_count},
                tmpl_lang
            )
            st.text_area("生成的话术", value=msg, height=200, label_visibility="collapsed")
            if st.button("📋 复制话术"):
                st.code(msg, language=None)

# ============================================================
# 页面7: AI智能搜索
# ============================================================
elif page == "🧠 AI 智能搜索":
    st.title("🧠 AI 智能搜索")

    st.markdown("""
    <div class="info-box">
    输入任意描述，系统将自动理解您的需求，从 37,000+ 展商和 110,000+ 采购商中找到最匹配的候选。
    </div>
    """, unsafe_allow_html=True)

    ai_query = st.text_area(
        "🔮 用自然语言描述你要找什么",
        placeholder="例如：帮我找欧洲做五金工具的采购商，要有邮箱，最好是批发商\n或者：找深圳做LED灯具的源头工厂，要有海关认证",
        height=100
    )

    aicol1, aicol2, aicol3 = st.columns(3)
    with aicol1:
        ai_role = st.selectbox("角色", ["采购商", "展商"])
    with aicol2:
        ai_topk = st.slider("返回数量", 5, 50, 10)
    with aicol3:
        ai_min_score = st.slider("最低匹配分", 0.0, 1.0, 0.1)

    if st.button("🧠 AI 智能匹配", use_container_width=True):
        if ai_query:
            with st.spinner("正在理解需求并匹配..."):
                from engine.matching import FastMatcher
                from data.data_loader import get_loader
                loader = get_loader(DATA_FILE)
                m = FastMatcher()
                m.build_index(loader.load_exhibitors(), loader.load_buyers())

                results = m.ai_search(ai_query, role=ai_role, top_k=ai_topk)

                if results:
                    st.success(f"找到 {len(results)} 条匹配结果")
                    for i, r in enumerate(results, 1):
                        data = r['data']
                        score_pct = r['score'] * 100
                        score_bar = "█" * int(score_pct / 5) + "░" * (20 - int(score_pct / 5))

                        with st.expander(f"#{i} [{score_bar}] {score_pct:.0f}% — {data.get('展商名称', data.get('采购商企业全称', 'N/A'))}", expanded=i<=3):
                            if ai_role == '采购商':
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.write(f"**企业**: {data.get('展商名称','N/A')}")
                                    st.write(f"**类型**: {data.get('企业类型', data.get('企业类型_final','N/A'))}")
                                    st.write(f"**省份**: {data.get('省份','N/A')}")
                                    st.write(f"**贸易形式**: {data.get('贸易形式','N/A')}")
                                with c2:
                                    st.write(f"**主营产品**: {str(data.get('主营产品',''))[:100]}")
                                    st.write(f"**手机**: {data.get('手机','N/A')}")
                                    st.write(f"**邮箱**: {data.get('邮箱','N/A')}")
                                    tags = []
                                    for col in ['海关认证展商','高新展商','品牌展商']:
                                        if data.get(col) == 'Y': tags.append(col.replace('展商',''))
                                    if tags: st.write(f"**标签**: {' '.join(tags)}")
                            else:
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.write(f"**企业**: {data.get('采购商企业全称','N/A')}")
                                    st.write(f"**国家**: {data.get('国家/地区','N/A')}")
                                    st.write(f"**大洲**: {data.get('大洲','N/A')}")
                                    st.write(f"**市场**: {data.get('市场层级','N/A')}")
                                with c2:
                                    st.write(f"**品类**: {data.get('主营品类','N/A')}")
                                    st.write(f"**类型**: {data.get('采购商类型_final','N/A')}")
                                    st.write(f"**意向**: {data.get('合作意向_final','N/A')}")
                                    st.write(f"**电话**: {data.get('联系方式-电话','N/A')}")
                else:
                    st.warning("未找到匹配结果，请尝试其他描述")
        else:
            st.info("请输入搜索描述")

    st.divider()

    # 常用搜索快捷入口
    st.subheader("⚡ 常用搜索")
    shortcuts = [
        ("🇺🇸 美国高意向采购商", "美国高意向采购商", "采购商"),
        ("🇩🇪 德国工具采购商", "德国五金工具采购商", "采购商"),
        ("🏭 深圳LED源头工厂", "深圳LED灯具源头工厂", "展商"),
        ("🇧🇷 巴西跨境电商买家", "巴西跨境电商采购商", "采购商"),
        ("🏭 广东五金源头工厂", "广东五金工具工厂", "展商"),
        ("🇸🇦 中东汽配采购商", "中东沙特阿拉伯汽车配件采购商", "采购商"),
    ]
    for label, query, role in shortcuts:
        col1, col2 = st.columns([1, 4])
        with col1:
            st.button(label, key=f"sc_{label}")
        with col2:
            if f"sc_{label}" in st.session_state and st.session_state[f"sc_{label}"]:
                from engine.matching import FastMatcher
                from data.data_loader import get_loader
                loader = get_loader(DATA_FILE)
                m = FastMatcher()
                m.build_index(loader.load_exhibitors(), loader.load_buyers())
                results = m.ai_search(query, role=role, top_k=5)
                if results:
                    for r in results:
                        d = r['data']
                        name = d.get('展商名称', d.get('采购商企业全称', 'N/A'))
                        st.write(f"  {name}")

# ============================================================
# 页面8: 系统设置
# ============================================================
elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统设置")

    tab_s1, tab_s2, tab_s3 = st.tabs(["📊 数据管理", "🧠 进化引擎", "ℹ️ 关于"])

    with tab_s1:
        st.subheader("数据文件管理")
        st.write(f"**当前数据文件**: `{DATA_FILE}`")
        st.write(f"**文件大小**: {os.path.getsize(DATA_FILE)/1024/1024:.1f} MB")
        st.write(f"**采购商数据**: {stats['buyer_count']:,} 条")
        st.write(f"**参展商数据**: {stats['exhibitor_count']:,} 条")

        if st.button("🔄 刷新数据缓存"):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.subheader("数据导出")
        ecol1, ecol2 = st.columns(2)
        with ecol1:
            if st.button("📦 导出全部采购商数据"):
                csv = buyers.to_csv(index=False).encode('utf-8-sig')
                st.download_button("下载CSV", csv, "全部采购商.csv", "text/csv")
        with ecol2:
            if st.button("📦 导出全部参展商数据"):
                csv = exhibitors.to_csv(index=False).encode('utf-8-sig')
                st.download_button("下载CSV", csv, "全部参展商.csv", "text/csv")

    with tab_s2:
        st.subheader("🧠 自进化引擎")
        from engine.evolution import get_evolution_engine
        evo = get_evolution_engine(os.path.join(APP_DIR, 'evolution_data.json'))
        summary = evo.to_summary()

        st.write(f"**累计事件数**: {summary['total_events']}")
        st.write(f"**触达总数**: {summary['total_outreach_sent']}")
        st.write(f"**回复总数**: {summary['total_replies']}")
        st.write(f"**总成交数**: {summary['total_deals']}")
        st.write(f"**回复率**: {summary['reply_rate']}")
        st.write(f"**最佳渠道**: {summary['best_channel']}")
        st.write(f"**TOP品类**: {', '.join(summary['top_categories'][:5])}")

        insights = evo.get_insights()
        if insights:
            st.subheader("📈 智能洞察")
            for insight in insights:
                conf = "🟢" if insight.confidence > 0.7 else "🟡" if insight.confidence > 0.4 else "🔴"
                st.markdown(f"""
                <div class="{'success-box' if insight.trend=='up' else 'info-box'}">
                    {conf} **[{insight.category}] {insight.metric}** = {insight.value:.1f}
                    <br>{insight.recommendation}
                    <br><small>置信度 {insight.confidence*100:.0f}% | 样本量 {insight.sample_size}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("使用系统越久，洞察越精准。开始触达并记录结果吧！")

    with tab_s3:
        st.subheader("ℹ️ 系统信息")
        st.markdown("""
        **CantonFair Pro — 智能外贸撮合系统**

        基于第138届、139届广交会数据构建，覆盖：
        - **110,000+** 采购商数据
        - **37,000+** 参展商数据
        - **43** 个产品品类

        核心功能：
        - 🔍 智能双向搜索
        - 🤝 供需精准匹配
        - ⭐ 多维度客户评分
        - 📞 线索跟踪管理
        - 🧠 AI自然语言搜索
        - 📊 可视化数据分析
        - 🧬 自进化引擎

        > 数据来源：广交会官方名录，由世贸数据整理
        """)

st.markdown("""
<div style="text-align:center; padding: 24px 0 8px; color: #475569; font-size: 12px;">
    CantonFair Pro v1.0 | Built with ❤️ + AI | 数据更新: 2026年5月
</div>
""", unsafe_allow_html=True)
