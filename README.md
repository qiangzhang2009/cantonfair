# CantonFair Pro

智能外贸撮合系统 — 基于第138届、139届广交会数据构建，覆盖 110,000+ 采购商与 37,000+ 参展商。

## 核心功能

- 数据总览：采购商国家分布、品类分布、意向分析
- 采购商/参展商双向搜索与筛选
- 智能供需匹配
- 客户评分与分层（S/A/B/C/D）
- 线索跟踪与外呼管理
- AI 自然语言搜索

## 部署

使用 Docker 部署到 [Render](https://render.com)：

1. Fork 并推送代码到 GitHub
2. 在 Render 创建新 Web Service，连接 GitHub 仓库
3. 配置 R2 环境变量（见 `.env.example`）
4. 部署完成

## 本地运行

```bash
cd cantonfair_system
pip install -r requirements.txt
python -m streamlit run ui/app.py --server.port 8502
```
