# Supabase 部署指南

## 概述

将 CantonFair Pro 的数据层从本地 Excel 迁移到 Supabase PostgreSQL，实现真正的 Serverless 架构：
- 数据查询下推到数据库（而不是每次启动加载 27MB Excel）
- Streamlit Cloud 部署无需包含数据文件
- 查询性能大幅提升

---

## 第一步：在 Supabase 创建表

1. 打开 https://supabase.com/dashboard/project/lasfvznnxtqzfrnafpmf/sql editor

2. 复制以下 SQL，粘贴执行：

```sql
-- CantonFair Pro 数据库表结构
-- 复制粘贴到 Supabase SQL Editor 中执行

-- ============================================================
-- 采购商数据表
-- ============================================================
CREATE TABLE buyers (
    id SERIAL PRIMARY KEY,
    序号 INTEGER,
    采购商企业全称 TEXT,
    联系人 TEXT,
    职位 TEXT,
    国家_地区 TEXT,
    大洲 TEXT,
    市场层级 TEXT,
    采购商类型 TEXT,
    主营品类 TEXT,
    采购意向品类 TEXT,
    合作意向 TEXT,
    合作模式 TEXT,
    联系方式_电话 TEXT,
    联系方式_邮箱 TEXT,
    联系方式_WhatsApp TEXT,
    联系方式_传真 TEXT,
    官网 TEXT,
    地址 TEXT,
    参展届次 TEXT,
    数据来源 TEXT,
    联系电话有效性 TEXT,
    国家_标准化 TEXT,
    采购商类型_final TEXT,
    合作意向_final TEXT,
    合作模式_final TEXT,
    综合评分 FLOAT,
    客户等级 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_buyers_country ON buyers(国家_地区);
CREATE INDEX idx_buyers_continent ON buyers(大洲);
CREATE INDEX idx_buyers_category ON buyers(主营品类);
CREATE INDEX idx_buyers_intent ON buyers(合作意向_final);

-- ============================================================
-- 参展商数据表
-- ============================================================
CREATE TABLE exhibitors (
    id SERIAL PRIMARY KEY,
    序号 INTEGER,
    参展商企业全称 TEXT,
    联系人 TEXT,
    职位 TEXT,
    手机 TEXT,
    邮箱 TEXT,
    微信_WhatsApp TEXT,
    省份 TEXT,
    城市 TEXT,
    企业类型 TEXT,
    企业规模 TEXT,
    主营品类 TEXT,
    主营产品关键词 TEXT,
    贸易形式 TEXT,
    海关认证 TEXT,
    高新展商 TEXT,
    品牌展商 TEXT,
    创新奖 TEXT,
    CF奖 TEXT,
    多届参展 TEXT,
    参展届次 TEXT,
    可对接采购商品类 TEXT,
    合作意向 TEXT,
    合作模式 TEXT,
    官网 TEXT,
    备注 TEXT,
    企业类型_final TEXT,
    核心优势 TEXT,
    综合评分 FLOAT,
    客户等级 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_exhibitors_province ON exhibitors(省份);
CREATE INDEX idx_exhibitors_category ON exhibitors(主营品类);

-- ============================================================
-- 品类撮合分析表
-- ============================================================
CREATE TABLE category_analysis (
    id SERIAL PRIMARY KEY,
    品类 TEXT NOT NULL,
    采购商数_两届合计 INTEGER,
    参展商数 INTEGER,
    供需比_采购商参展商 FLOAT,
    撮合建议 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 采购商来源分析表
-- ============================================================
CREATE TABLE country_stats (
    id SERIAL PRIMARY KEY,
    排名 INTEGER,
    国家_地区 TEXT NOT NULL,
    大洲 TEXT,
    采购商数量 INTEGER,
    占比 FLOAT,
    市场类型 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 高价值展商速查表
-- ============================================================
CREATE TABLE top_exhibitors (
    id SERIAL PRIMARY KEY,
    展商名称 TEXT,
    省份 TEXT,
    城市 TEXT,
    企业类型 TEXT,
    贸易形式 TEXT,
    主营产品前100字 TEXT,
    海关认证 TEXT,
    高新展商 TEXT,
    品牌展商 TEXT,
    多届参展 TEXT,
    参展届次 TEXT,
    可对接品类 TEXT,
    手机 TEXT,
    邮箱 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 品类撮合配对表
-- ============================================================
CREATE TABLE pairing (
    id SERIAL PRIMARY KEY,
    品类 TEXT,
    展商名称 TEXT,
    展商省份 TEXT,
    展商城市 TEXT,
    展商类型 TEXT,
    展商贸易形式 TEXT,
    展商亮点标签 TEXT,
    展商主营产品 TEXT,
    采购商名称 TEXT,
    采购商国家 TEXT,
    采购商大洲 TEXT,
    采购商市场层级 TEXT,
    采购商类型 TEXT,
    采购商合作意向 TEXT,
    展商联系方式 TEXT,
    采购商电话 TEXT,
    采购商WhatsApp链接 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pairing_category ON pairing(品类);
```

3. 执行后会看到 "Success" 提示

---

## 第二步：配置环境变量

创建或更新 `.env` 文件：

```bash
# 在 cantonfair_system/ 目录下

# Supabase 配置（必需）
SUPABASE_URL=https://lasfvznnxtqzfrnafpmf.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxhc2Z2em5ueHRxemZybmFmcG1mIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg3MjY4NTEsImV4cCI6MjA5NDMwMjg1MX0.yvtw_hXrPz7_GO-KmDCBLqqC1njMAhsbADvHvoP6iDM

# 服务端密钥（仅导入脚本用，不要暴露在前端）
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxhc2Z2em5ueHRxemZybmFmcG1mIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODcyNjg1MSwiZXhwIjoyMDk0MzAyODUxfQ.cOWTHIlMe7MScRgBs-2yCWsbJjG9H4dkUseuKKWPCP4
```

> **安全提醒**：`SUPABASE_KEY` 是公开密钥，可以安全地在前端使用（只有读权限）。`SUPABASE_SERVICE_ROLE_KEY` 是服务端密钥，只有在导入数据时才需要，**不要提交到 GitHub**。

---

## 第三步：安装依赖并导入数据

```bash
cd cantonfair_system

# 安装 Supabase Python 客户端
pip install supabase>=2.0.0

# 运行数据导入脚本（耗时约 10-15 分钟）
python -m supabase.import_data
```

导入过程：
- 采购商 110,808 行
- 参展商 37,192 行
- 其他表约 18,000 行
- 总计约 165,000 行

---

## 第四步：验证数据导入

在 Supabase Dashboard → Table Editor 中查看各表行数，确认数据已导入。

---

## 第五步：部署到 Streamlit Cloud

1. 推送代码到 GitHub（确保 `.env` 不在 GitHub 中）

2. 在 https://streamlit.io/cloud 中 Connect GitHub repo

3. 设置环境变量：
   - `SUPABASE_URL` = `https://lasfvznnxtqzfrnafpmf.supabase.co`
   - `SUPABASE_KEY` = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`（anon public key）

4. 设置 App settings：
   - Main file path: `cantonfair_system/ui/app.py`
   - Python version: 3.11

5. 点击 Deploy！

---

## 工作原理

```
用户访问 Streamlit Cloud
        ↓
app.py 加载
        ↓
data_loader.py 检查环境变量
        ↓
有 SUPABASE_KEY? → 从 Supabase 查询（毫秒级）
无 SUPABASE_KEY?  → 回退到本地 Excel
        ↓
返回 DataFrame，后续逻辑完全不变
```

---

## 常见问题

**Q: Streamlit Cloud 有哪些限制？**
- 服务器在美国，中国访问较慢
- outreach_data.json / evolution_data.json 无法持久化
- 每次冷启动无状态

**Q: 如何更新数据？**
重新运行导入脚本，数据会被追加或覆盖：
```bash
python -m supabase.import_data
```

**Q: 隐私数据怎么处理？**
联系方式（邮箱/电话/WhatsApp）目前在 DB 中是公开可读的。
如需保护，在 Supabase Dashboard → Authentication → Row Level Security 中修改策略。
