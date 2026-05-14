# CantonFair Pro — 广交会智能外贸撮合系统

基于第138届、139届广交会数据构建的智能外贸获客与撮合平台。

> **生产部署**：推荐使用 Railway + Cloudflare R2，见 [DEPLOY.md](DEPLOY.md)。

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
| ⚙️ **系统设置** | 数据刷新、导出、自进化引擎洞察 |

## 本地开发

```bash
cd cantonfair_system
pip install -r requirements.txt
chmod +x start.sh
./start.sh
```

访问 **http://localhost:8502**

## 生产部署

详见 [DEPLOY.md](DEPLOY.md)。

## 系统架构

```
cantonfair_system/
├── auth.py               # 认证与权限管理
├── cloud_storage.py      # Cloudflare R2 云存储管理
├── data/
│   └── data_loader.py    # 数据加载（支持本地/R2）
├── engine/
│   ├── matching.py       # 智能匹配引擎
│   ├── scoring.py        # 客户评分引擎
│   └── evolution.py      # 自进化引擎
├── outreach/
│   └── tracking.py       # 外呼管理与线索跟踪
├── ui/
│   └── app.py            # Streamlit 主界面
├── Dockerfile            # 容器化部署
├── railway.toml           # Railway 配置
├── requirements.txt      # Python 依赖
└── .env.example          # 环境变量示例
```

## 数据规模

- 采购商：**110,808** 条
- 参展商：**37,192** 家
- 品类覆盖：**43** 个
- 有邮箱采购商：**66,173** 条
- 高意向采购商：**46,075** 条（两届均到场）

## 核心算法

- **匹配引擎**：TF-IDF文本向量化 + 品类关键词规则匹配 + Jaccard相似度
- **评分引擎**：意向分×35% + 触达分×25% + 价值分×25% + 质量分×15%
- **自进化**：触达渠道回复率追踪 → 优化推送优先级 → 评分权重校准

## 技术栈

Python 3 + Streamlit + Pandas + Plotly + boto3 (Cloudflare R2)
