"""
Supabase 表创建脚本
通过 Supabase Management API 或 psycopg2 直连
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / '.env')

import httpx

SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
PROJECT_REF = 'lasfvznnxtqzfrnafpmf'

ALL_SQL = []

# buyers
ALL_SQL.append(("CREATE TABLE IF NOT EXISTS buyers", """CREATE TABLE IF NOT EXISTS buyers (
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
);"""))

ALL_SQL.append(("CREATE INDEX idx_buyers_country", "CREATE INDEX IF NOT EXISTS idx_buyers_country ON buyers(国家_地区);"))
ALL_SQL.append(("CREATE INDEX idx_buyers_continent", "CREATE INDEX IF NOT EXISTS idx_buyers_continent ON buyers(大洲);"))
ALL_SQL.append(("CREATE INDEX idx_buyers_category", "CREATE INDEX IF NOT EXISTS idx_buyers_category ON buyers(主营品类);"))
ALL_SQL.append(("CREATE INDEX idx_buyers_intent", "CREATE INDEX IF NOT EXISTS idx_buyers_intent ON buyers(合作意向_final);"))

# exhibitors
ALL_SQL.append(("CREATE TABLE IF NOT EXISTS exhibitors", """CREATE TABLE IF NOT EXISTS exhibitors (
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
);"""))

ALL_SQL.append(("CREATE INDEX idx_exhibitors_province", "CREATE INDEX IF NOT EXISTS idx_exhibitors_province ON exhibitors(省份);"))
ALL_SQL.append(("CREATE INDEX idx_exhibitors_category", "CREATE INDEX IF NOT EXISTS idx_exhibitors_category ON exhibitors(主营品类);"))

# category_analysis
ALL_SQL.append(("CREATE TABLE IF NOT EXISTS category_analysis", """CREATE TABLE IF NOT EXISTS category_analysis (
    id SERIAL PRIMARY KEY,
    品类 TEXT NOT NULL,
    采购商数_两届合计 INTEGER,
    参展商数 INTEGER,
    供需比_采购商参展商 FLOAT,
    撮合建议 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);"""))

# country_stats
ALL_SQL.append(("CREATE TABLE IF NOT EXISTS country_stats", """CREATE TABLE IF NOT EXISTS country_stats (
    id SERIAL PRIMARY KEY,
    排名 INTEGER,
    国家_地区 TEXT NOT NULL,
    大洲 TEXT,
    采购商数量 INTEGER,
    占比 FLOAT,
    市场类型 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);"""))

# top_exhibitors
ALL_SQL.append(("CREATE TABLE IF NOT EXISTS top_exhibitors", """CREATE TABLE IF NOT EXISTS top_exhibitors (
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
);"""))

# pairing
ALL_SQL.append(("CREATE TABLE IF NOT EXISTS pairing", """CREATE TABLE IF NOT EXISTS pairing (
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
);"""))

ALL_SQL.append(("CREATE INDEX idx_pairing_category", "CREATE INDEX IF NOT EXISTS idx_pairing_category ON pairing(品类);"))

# RLS + Policies
for t in ['buyers', 'exhibitors', 'category_analysis', 'country_stats', 'top_exhibitors', 'pairing']:
    ALL_SQL.append((f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY", f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;"))
    ALL_SQL.append((f"Policy: {t} public read", f'CREATE POLICY "Allow public read" ON {t} FOR SELECT USING (true);'))


def try_psycopg2():
    """方法1: psycopg2 直连（需要数据库密码）"""
    import psycopg2

    # 尝试从环境变量获取连接字符串
    db_url = os.getenv('SUPABASE_DB_URL', '')
    if not db_url:
        # 尝试从 .env 读取
        env_path = PROJECT_ROOT / '.env'
        with open(env_path) as f:
            for line in f:
                if 'SUPABASE_DB_URL' in line and '=' in line:
                    db_url = line.split('=', 1)[1].strip()
                elif 'DATABASE_URL' in line and '=' in line:
                    db_url = line.split('=', 1)[1].strip()

    if not db_url:
        return False, "未配置 SUPABASE_DB_URL"

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        success = 0
        failed = 0
        for desc, sql in ALL_SQL:
            try:
                cur.execute(sql)
                conn.commit()
                success += 1
                print(f"  ✓ {desc}")
            except Exception as e:
                # 可能已存在，忽略
                if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                    print(f"  ~ {desc} (已存在)")
                    success += 1
                else:
                    failed += 1
                    print(f"  ✗ {desc}: {e}")

        cur.close()
        conn.close()

        print(f"\npsycopg2 直连: {success} 成功, {failed} 失败")
        return True, None
    except Exception as e:
        return False, str(e)


def try_management_api():
    """方法2: Supabase Management API（需要 PAT）"""
    pat = os.getenv('SUPABASE_PAT', '')
    if not pat:
        # 尝试从 .env 读取
        env_path = PROJECT_ROOT / '.env'
        with open(env_path) as f:
            for line in f:
                if 'SUPABASE_PAT' in line and '=' in line:
                    pat = line.split('=', 1)[1].strip()

    if not pat:
        return False, "未配置 SUPABASE_PAT"

    mgmt_headers = {
        'Authorization': f'Bearer {pat}',
        'Content-Type': 'application/json',
    }

    base_url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

    success = 0
    failed = 0
    for desc, sql in ALL_SQL:
        resp = httpx.post(
            base_url,
            headers=mgmt_headers,
            json={"query": sql},
            timeout=120
        )
        if resp.status_code in (200, 201, 204):
            print(f"  ✓ {desc}")
            success += 1
        elif resp.status_code == 400 and ('already exists' in resp.text.lower() or 'duplicate' in resp.text.lower()):
            print(f"  ~ {desc} (已存在)")
            success += 1
        else:
            failed += 1
            print(f"  ✗ {desc} ({resp.status_code}): {resp.text[:100]}")

    print(f"\nManagement API: {success} 成功, {failed} 失败")
    return failed == 0, None


def try_pg_connection_pool():
    """方法3: 通过 Supabase 的 pgBouncer 连接"""
    import psycopg2

    # Supabase 直连格式（端口 5432，通过 pgBouncer）
    # 需要 postgres 用户密码
    password = os.getenv('POSTGRES_PASSWORD', '')
    if not password:
        env_path = PROJECT_ROOT / '.env'
        with open(env_path) as f:
            for line in f:
                if 'POSTGRES_PASSWORD' in line and '=' in line:
                    password = line.split('=', 1)[1].strip()

    if not password:
        return False, "未配置 POSTGRES_PASSWORD"

    try:
        conn = psycopg2.connect(
            host=f"db.{PROJECT_REF}.supabase.co",
            port=5432,
            database="postgres",
            user="postgres",
            password=password,
            sslmode='require',
            connect_timeout=30
        )
        cur = conn.cursor()

        success = 0
        failed = 0
        for desc, sql in ALL_SQL:
            try:
                cur.execute(sql)
                conn.commit()
                print(f"  ✓ {desc}")
                success += 1
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                    print(f"  ~ {desc} (已存在)")
                    success += 1
                else:
                    failed += 1
                    print(f"  ✗ {desc}: {str(e)[:100]}")

        cur.close()
        conn.close()
        print(f"\npgBouncer 直连: {success} 成功, {failed} 失败")
        return True, None
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("CantonFair Pro — 创建 Supabase 数据库表")
    print("=" * 60)
    print()

    # 先检查表是否已存在
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/buyers",
        headers={'apikey': SERVICE_KEY, 'Authorization': f'Bearer {SERVICE_KEY}'},
        params={'limit': 1},
        timeout=30
    )
    if resp.status_code == 200:
        print("✓ buyers 表已存在，跳过创建步骤")
        print()
        return

    print("buyers 表不存在，开始创建...")
    print()

    tried = []

    # 方法1: psycopg2 直连
    print("尝试方法 1: psycopg2 直连...")
    ok, err = try_psycopg2()
    tried.append(('psycopg2', ok))
    if ok:
        print("✓ 成功！")
    else:
        print(f"  失败: {err}")
    print()

    # 方法2: Management API
    print("尝试方法 2: Management API (需要 PAT)...")
    ok, err = try_management_api()
    tried.append(('Management API', ok))
    if ok:
        print("✓ 成功！")
    else:
        print(f"  失败: {err}")
    print()

    # 方法3: pgBouncer
    print("尝试方法 3: pgBouncer 直连...")
    ok, err = try_pg_connection_pool()
    tried.append(('pgBouncer', ok))
    if ok:
        print("✓ 成功！")
    else:
        print(f"  失败: {err}")
    print()

    # 汇总
    if any(ok for _, ok in tried):
        print("=" * 60)
        print("✅ 部分表创建成功！请在 Supabase Dashboard 确认:")
        print("  https://supabase.com/dashboard/project/lasfvznnxtqzfrnafpmf/database/tables")
    else:
        print("=" * 60)
        print("❌ 所有方法均失败")
        print()
        print("需要配置数据库凭据。")
        print()
        print("获取 POSTGRES_PASSWORD:")
        print("1. 打开 https://supabase.com/dashboard/project/lasfvznnxtqzfrnafpmf/settings/database")
        print("2. 在 'Connection string' 区域找到 'postgres' 用户的密码")
        print("3. 在 .env 中添加: POSTGRES_PASSWORD=你的密码")
        print()
        print("或获取 SUPABASE_PAT:")
        print("1. 打开 https://supabase.com/dashboard/account/tokens")
        print("2. 点击 'New Token'")
        print("3. 在 .env 中添加: SUPABASE_PAT=sb_xxxxx")


if __name__ == '__main__':
    main()
