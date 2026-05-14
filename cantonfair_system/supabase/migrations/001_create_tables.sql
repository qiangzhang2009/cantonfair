-- CantonFair Pro 数据库迁移脚本
-- 创建所有数据表

-- ============================================================
-- 采购商数据表 (buyers)
-- ============================================================
CREATE TABLE IF NOT EXISTS buyers (
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
    -- 标准化衍生字段
    国家_标准化 TEXT,
    采购商类型_final TEXT,
    合作意向_final TEXT,
    合作模式_final TEXT,
    综合评分 FLOAT,
    客户等级 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 采购商索引
CREATE INDEX IF NOT EXISTS idx_buyers_country ON buyers(国家_地区);
CREATE INDEX IF NOT EXISTS idx_buyers_continent ON buyers(大洲);
CREATE INDEX IF NOT EXISTS idx_buyers_category ON buyers(主营品类);
CREATE INDEX IF NOT EXISTS idx_buyers_intent ON buyers(合作意向_final);
CREATE INDEX IF NOT EXISTS idx_buyers_email ON buyers(联系方式_邮箱) WHERE 联系方式_邮箱 IS NOT NULL AND 联系方式_邮箱 != '';
CREATE INDEX IF NOT EXISTS idx_buyers_phone ON buyers(联系方式_电话) WHERE 联系方式_电话 IS NOT NULL AND 联系方式_电话 != '';
CREATE INDEX IF NOT EXISTS idx_buyers_whatsapp ON buyers(联系方式_WhatsApp) WHERE 联系方式_WhatsApp IS NOT NULL AND 联系方式_WhatsApp != '';

-- ============================================================
-- 参展商数据表 (exhibitors)
-- ============================================================
CREATE TABLE IF NOT EXISTS exhibitors (
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
    -- 标准化衍生字段
    企业类型_final TEXT,
    核心优势 TEXT,
    综合评分 FLOAT,
    客户等级 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 参展商索引
CREATE INDEX IF NOT EXISTS idx_exhibitors_province ON exhibitors(省份);
CREATE INDEX IF NOT EXISTS idx_exhibitors_type ON exhibitors(企业类型);
CREATE INDEX IF NOT EXISTS idx_exhibitors_category ON exhibitors(主营品类);
CREATE INDEX IF NOT EXISTS idx_exhibitors_phone ON exhibitors(手机) WHERE 手机 IS NOT NULL AND 手机 != '';

-- ============================================================
-- 品类撮合分析表 (category_analysis)
-- ============================================================
CREATE TABLE IF NOT EXISTS category_analysis (
    id SERIAL PRIMARY KEY,
    品类 TEXT NOT NULL,
    采购商数_两届合计 INTEGER,
    参展商数 INTEGER,
    供需比_采购商参展商 FLOAT,
    撮合建议 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_category_analysis_category ON category_analysis(品类);

-- ============================================================
-- 采购商来源分析表 (country_stats)
-- ============================================================
CREATE TABLE IF NOT EXISTS country_stats (
    id SERIAL PRIMARY KEY,
    排名 INTEGER,
    国家_地区 TEXT NOT NULL,
    大洲 TEXT,
    采购商数量 INTEGER,
    占比 FLOAT,
    市场类型 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_country_stats_country ON country_stats(国家_地区);
CREATE INDEX IF NOT EXISTS idx_country_stats_continent ON country_stats(大洲);

-- ============================================================
-- 高价值展商速查表 (top_exhibitors)
-- ============================================================
CREATE TABLE IF NOT EXISTS top_exhibitors (
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

CREATE INDEX IF NOT EXISTS idx_top_exhibitors_province ON top_exhibitors(省份);
CREATE INDEX IF NOT EXISTS idx_top_exhibitors_type ON top_exhibitors(企业类型);

-- ============================================================
-- 品类撮合配对表 (pairing)
-- ============================================================
CREATE TABLE IF NOT EXISTS pairing (
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

CREATE INDEX IF NOT EXISTS idx_pairing_category ON pairing(品类);
CREATE INDEX IF NOT EXISTS idx_pairing_exhibitor ON pairing(展商名称);
CREATE INDEX IF NOT EXISTS idx_pairing_country ON pairing(采购商国家);

-- ============================================================
-- 启用 RLS (行级安全策略)
-- ============================================================
ALTER TABLE buyers ENABLE ROW LEVEL SECURITY;
ALTER TABLE exhibitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE country_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE top_exhibitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE pairing ENABLE ROW LEVEL SECURITY;

-- 公开读取策略（用于 anon key）
CREATE POLICY "Allow public read" ON buyers FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON exhibitors FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON category_analysis FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON country_stats FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON top_exhibitors FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON pairing FOR SELECT USING (true);

-- 启用自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_buyers_updated_at BEFORE UPDATE ON buyers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_exhibitors_updated_at BEFORE UPDATE ON exhibitors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
