# CantonFair Pro — 广交会智能外贸撮合系统

基于第138届、139届广交会数据构建的智能外贸获客与撮合平台。

## 快速部署到 Streamlit Cloud

1. **Fork 本仓库** 到你的 GitHub
2. **创建 Supabase 项目**（免费）：https://supabase.com
3. **在 Supabase SQL Editor** 执行 `supabase/migrations/001_create_tables.sql` 创建表
4. **导入数据**：`cd cantonfair_system && python3 supabase/import_data_async.py`
5. **在 Streamlit Cloud**：点击 "New app" → 选择你的 repo → 设置：
   - **Repository**: `your-username/展会数据分析3`
   - **Branch**: `main`
   - **Main file path**: `cantonfair_system/ui/app.py`
6. **添加 Secrets**（Advanced settings）：

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

7. 点击 **Deploy!**

> **免费套餐限制**：Streamlit Cloud Community 适合个人/小团队，数据库免费 500MB，500MB 存储。

## 功能模块

| 模块 | 功能 |
|------|------|
| 📊 **数据总览** | 采购商/参展商全量数据可视化，大洲分布、国家排名、品类分析 |
| 🔍 **采购商搜索** | 多维度筛选（国家/品类/意向/联系方式），关键词全文搜索 |
| 🏭 **参展商搜索** | 按省份/类型/产品搜索，优质展商快速定位 |
| 🤝 **智能匹配** | 选择品类，自动匹配展商×采购商，生成一对一配对表 |
| ⭐ **客户评分** | S/A/B/C/D五级分层，综合意向/触达/价值/质量四维评分 |
| 📞 **外呼管理** | 线索池管理、状态跟踪、话术生成、跟进提醒 |
| 🧠 **AI智能搜索** | 自然语言描述需求，系统自动理解并匹配最相关客户 |
| ⚙️ **系统设置** | 数据刷新、导出，自进化引擎洞察 |

## 本地开发

```bash
cd cantonfair_system
pip install -r requirements.txt
cp .env.example .env  # 填入你的 Supabase 凭据
chmod +x start.sh
./start.sh
```

访问 **http://localhost:8501**

## 数据架构

```
Supabase (PostgreSQL)  ← REST API 分页查询（绕过 1000 行限制）
       ↓
data_loader.py         ← 统一数据加载接口
       ↓
app.py (Streamlit)     ← 用户界面
```

## 数据库表

| 表名 | 说明 | 行数 |
|------|------|------|
| `buyers` | 采购商数据 | ~110,808 |
| `exhibitors` | 参展商数据 | ~37,192 |
| `category_analysis` | 品类撮合分析 | ~43 |
| `country_stats` | 采购商来源分析 | ~199 |
| `top_exhibitors` | 高价值展商速查 | ~5,000 |
| `pairing` | 品类撮合配对表 | ~12,900 |

## 系统架构

```
cantonfair_system/
├── auth.py               # 认证与权限管理
├── cloud_storage.py      # Cloudflare R2 云存储管理
├── data/
│   └── data_loader.py    # 数据加载（Supabase + 本地 Excel）
├── engine/
│   ├── matching.py       # 智能匹配引擎
│   ├── scoring.py        # 客户评分引擎
│   └── evolution.py      # 自进化引擎
├── outreach/
│   └── tracking.py       # 外呼管理与线索跟踪
├── ui/
│   └── app.py            # Streamlit 主界面
├── supabase/
│   ├── migrations/       # 数据库 DDL 脚本
│   └── import_data_async.py  # 高速数据导入工具
├── Dockerfile            # 容器化部署
├── requirements.txt      # Python 依赖
├── .env.example          # 环境变量示例
└── .streamlit/
    └── secrets.toml      # Streamlit Cloud Secrets（勿提交 git）
```

## 核心算法

- **匹配引擎**：TF-IDF文本向量化 + 品类关键词规则匹配 + Jaccard相似度
- **评分引擎**：意向分×35% + 触达分×25% + 价值分×25% + 质量分×15%
- **自进化**：触达渠道回复率追踪 → 优化推送优先级 → 评分权重校准

## 技术栈

Python 3 + Streamlit + Pandas + Plotly + Supabase (PostgreSQL) + httpx
