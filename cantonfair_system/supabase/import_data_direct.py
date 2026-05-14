"""
Supabase 直连导入 — 使用 psycopg2 绕过 REST API 限制
直接从 PostgreSQL 插入数据
"""
import os, sys, time, io
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / '.env')

import pandas as pd
import psycopg2
from psycopg2 import extras

from data.data_loader import normalize_country, get_continent, get_market_level, infer_buyer_type, infer_trade_mode, infer_intent

SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')

# 从 .env 读取数据库密码
_db_pass = os.getenv('SUPABASE_DB_PASSWORD', '')
if not _db_pass:
    env_path = PROJECT_ROOT / '.env'
    with open(env_path) as f:
        for line in f:
            if 'SUPABASE_DB_PASSWORD' in line and '=' in line:
                _db_pass = line.split('=', 1)[1].strip().rstrip('"').lstrip('"')
                break

# 从连接字符串格式提取密码
if not _db_pass:
    import re
    conn_str = os.getenv('SUPABASE_DB_STRING', os.getenv('DATABASE_URL', ''))
    m = re.search(r'postgres:(.+?)@', conn_str)
    if m:
        _db_pass = m.group(1)

# 如果无法从环境变量获取，提示用户
if not _db_pass:
    print("❌ 需要数据库密码")
    print("请从 Supabase Dashboard 获取:")
    print("  Settings → Database → Connection string → Copy")
    print("并在 .env 中添加: SUPABASE_DB_PASSWORD=你的密码")
    print("或者使用格式: postgresql://postgres:密码@db.xxx.supabase.co:5432/postgres")
    sys.exit(1)

# 构建连接参数
PROJECT_REF = 'lasfvznnxtqzfrnafpmf'
DB_PARAMS = {
    'host': f'db.{PROJECT_REF}.supabase.co',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': _db_pass,
    'sslmode': 'require',
    'connect_timeout': 30,
}

possible_paths = [
    PROJECT_ROOT / '广交会数据综合整理_标准格式.xlsx',
    PROJECT_ROOT.parent / '广交会数据综合整理_标准格式.xlsx',
]
DATA_FILE = None
for p in possible_paths:
    if p.exists():
        DATA_FILE = p
        break
if DATA_FILE is None:
    print("❌ 数据文件不存在")
    sys.exit(1)


def get_conn():
    return psycopg2.connect(**DB_PARAMS)


def col_mapping(name: str) -> str:
    return name.replace('/', '_').replace('-', '_')


def load_excel(sheet: str) -> pd.DataFrame:
    print(f"  读取 '{sheet}'...")
    df = pd.read_excel(DATA_FILE, sheet_name=sheet)
    df.columns = [col_mapping(str(c)) for c in df.columns]
    print(f"  完成: {len(df):,} 行")
    return df


def _score_to_tier(score: float) -> str:
    if score >= 80: return 'S'
    if score >= 65: return 'A'
    if score >= 50: return 'B'
    if score >= 35: return 'C'
    return 'D'


def insert_batch(conn, table: str, rows: list[dict], batch_num: int, total: int):
    """使用 execute_batch 批量插入"""
    if not rows:
        return 0
    try:
        cols = list(rows[0].keys())
        placeholders = ','.join(['%s'] * len(cols))
        col_names = ','.join(cols)
        sql = f'INSERT INTO {table} ({col_names}) VALUES ({placeholders})'
        values = [[r.get(c) for c in cols] for r in rows]
        extras.execute_batch(conn.cursor(), sql, values, batch_size=1000)
        conn.commit()
        done = batch_num * 1000 + len(rows)
        pct = min(int(done / total * 100), 100)
        bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
        print(f"  [{table}] {bar} {done:,}/{total:,} ({pct}%)", end='\r', flush=True)
        return len(rows)
    except Exception as e:
        conn.rollback()
        # 逐条重试
        failed = 0
        for row in rows:
            try:
                cols = list(row.keys())
                placeholders = ','.join(['%s'] * len(cols))
                col_names = ','.join(cols)
                sql = f'INSERT INTO {table} ({col_names}) VALUES ({placeholders})'
                values = [row.get(c) for c in cols]
                cur = conn.cursor()
                cur.execute(sql, values)
                conn.commit()
            except Exception:
                failed += 1
        print(f"\n  ⚠ {failed}/{len(rows)} 行失败")
        return len(rows) - failed


def insert_all(conn, table: str, data: list[dict], batch_size: int = 1000):
    total = len(data)
    for i in range(0, total, batch_size):
        batch = data[i:i+batch_size]
        insert_batch(conn, table, batch, i // batch_size, total)
    print()
    return total


# ---- 数据准备函数 ----

def prepare_buyers(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        country_raw = str(r.get('国家_地区', '')) if pd.notna(r.get('国家_地区')) else ''
        country_norm = normalize_country(country_raw)
        continent = get_continent(country_norm)
        market_level = get_market_level(continent)
        btype_raw = str(r.get('采购商类型', '')) if pd.notna(r.get('采购商类型')) else ''
        btype_inf = infer_buyer_type(str(r.get('采购商企业全称', '')), country_norm)
        btype_final = btype_raw if btype_raw else btype_inf
        tmode_raw = str(r.get('合作模式', '')) if pd.notna(r.get('合作模式')) else ''
        tmode_inf = infer_trade_mode(str(r.get('采购商企业全称', '')))
        tmode_final = tmode_raw if tmode_raw else tmode_inf
        intent_raw = str(r.get('合作意向', '')) if pd.notna(r.get('合作意向')) else ''
        sessions = str(r.get('参展届次', '')) if pd.notna(r.get('参展届次')) else ''
        intent_final = intent_raw if intent_raw else infer_intent(sessions)
        score = float(r.get('综合评分', 0)) if pd.notna(r.get('综合评分')) else 0.0
        rows.append({
            '序号': int(r['序号']) if pd.notna(r.get('序号')) else None,
            '采购商企业全称': str(r.get('采购商企业全称', '')) if pd.notna(r.get('采购商企业全称')) else '',
            '联系人': str(r.get('联系人', '')) if pd.notna(r.get('联系人')) else '',
            '职位': str(r.get('职位', '')) if pd.notna(r.get('职位')) else '',
            '国家_地区': country_raw,
            '大洲': str(r.get('大洲', continent)) if pd.notna(r.get('大洲')) else continent,
            '市场层级': str(r.get('市场层级', market_level)) if pd.notna(r.get('市场层级')) else market_level,
            '采购商类型': btype_raw,
            '主营品类': str(r.get('主营品类', '')) if pd.notna(r.get('主营品类')) else '',
            '采购意向品类': str(r.get('采购意向品类', '')) if pd.notna(r.get('采购意向品类')) else '',
            '合作意向': intent_raw,
            '合作模式': tmode_raw,
            '联系方式_电话': str(r.get('联系方式_电话', '')) if pd.notna(r.get('联系方式_电话')) else '',
            '联系方式_邮箱': str(r.get('联系方式_邮箱', '')) if pd.notna(r.get('联系方式_邮箱')) else '',
            '联系方式_WhatsApp': str(r.get('联系方式_WhatsApp', '')) if pd.notna(r.get('联系方式_WhatsApp')) else '',
            '联系方式_传真': str(r.get('联系方式_传真', '')) if pd.notna(r.get('联系方式_传真')) else '',
            '官网': str(r.get('官网', '')) if pd.notna(r.get('官网')) else '',
            '地址': str(r.get('地址', '')) if pd.notna(r.get('地址')) else '',
            '参展届次': sessions,
            '数据来源': str(r.get('数据来源', '')) if pd.notna(r.get('数据来源')) else '',
            '联系电话有效性': str(r.get('联系电话有效性', '')) if pd.notna(r.get('联系电话有效性')) else '',
            '国家_标准化': country_norm,
            '采购商类型_final': btype_final,
            '合作意向_final': intent_final,
            '合作模式_final': tmode_final,
            '综合评分': score,
            '客户等级': _score_to_tier(score),
        })
    return rows


def prepare_exhibitors(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        advs = []
        for col in ['海关认证', '高新展商', '品牌展商', '创新奖', 'CF奖']:
            val = str(r.get(col, '')).strip() if pd.notna(r.get(col)) else ''
            if val == 'Y':
                advs.append(col.replace('展商', ''))
        score = float(r.get('综合评分', 0)) if pd.notna(r.get('综合评分')) else 0.0
        rows.append({
            '序号': int(r['序号']) if pd.notna(r.get('序号')) else None,
            '参展商企业全称': str(r.get('展商名称', '')) if pd.notna(r.get('展商名称')) else '',
            '联系人': str(r.get('联系人', '')) if pd.notna(r.get('联系人')) else '',
            '职位': str(r.get('职位', '')) if pd.notna(r.get('职位')) else '',
            '手机': str(r.get('手机', '')) if pd.notna(r.get('手机')) else '',
            '邮箱': str(r.get('邮箱', '')) if pd.notna(r.get('邮箱')) else '',
            '微信_WhatsApp': str(r.get('微信_WhatsApp', '')) if pd.notna(r.get('微信_WhatsApp')) else '',
            '省份': str(r.get('省份', '')) if pd.notna(r.get('省份')) else '',
            '城市': str(r.get('城市', '')) if pd.notna(r.get('城市')) else '',
            '企业类型': str(r.get('企业类型', '')) if pd.notna(r.get('企业类型')) else '',
            '企业规模': str(r.get('企业规模', '')) if pd.notna(r.get('企业规模')) else '',
            '主营品类': str(r.get('主营品类', '')) if pd.notna(r.get('主营品类')) else '',
            '主营产品关键词': str(r.get('主营产品关键词', '')) if pd.notna(r.get('主营产品关键词')) else '',
            '贸易形式': str(r.get('贸易形式', '')) if pd.notna(r.get('贸易形式')) else '',
            '海关认证': str(r.get('海关认证', '')) if pd.notna(r.get('海关认证')) else '',
            '高新展商': str(r.get('高新展商', '')) if pd.notna(r.get('高新展商')) else '',
            '品牌展商': str(r.get('品牌展商', '')) if pd.notna(r.get('品牌展商')) else '',
            '创新奖': str(r.get('创新奖', '')) if pd.notna(r.get('创新奖')) else '',
            'CF奖': str(r.get('CF奖', '')) if pd.notna(r.get('CF奖')) else '',
            '多届参展': str(r.get('多届参展', '')) if pd.notna(r.get('多届参展')) else '',
            '参展届次': str(r.get('参展届次', '')) if pd.notna(r.get('参展届次')) else '',
            '可对接采购商品类': str(r.get('可对接采购商品类', '')) if pd.notna(r.get('可对接采购商品类')) else '',
            '合作意向': str(r.get('合作意向', '')) if pd.notna(r.get('合作意向')) else '',
            '合作模式': str(r.get('合作模式', '')) if pd.notna(r.get('合作模式')) else '',
            '官网': str(r.get('官网', '')) if pd.notna(r.get('官网')) else '',
            '备注': str(r.get('备注', '')) if pd.notna(r.get('备注')) else '',
            '企业类型_final': str(r.get('企业类型', '')) if pd.notna(r.get('企业类型')) else '',
            '核心优势': '; '.join(advs),
            '综合评分': score,
            '客户等级': _score_to_tier(score),
        })
    return rows


def prepare_category_analysis(df: pd.DataFrame) -> list[dict]:
    return [{
        '品类': str(r.get('品类', '')) if pd.notna(r.get('品类')) else '',
        '采购商数_两届合计': int(r['采购商数(两届合计)']) if pd.notna(r.get('采购商数(两届合计)')) else 0,
        '参展商数': int(r['参展商数']) if pd.notna(r.get('参展商数')) else 0,
        '供需比_采购商参展商': float(r['供需比(采购商/参展商)']) if pd.notna(r.get('供需比(采购商/参展商)')) else 0.0,
        '撮合建议': str(r.get('撮合建议', '')) if pd.notna(r.get('撮合建议')) else '',
    } for _, r in df.iterrows()]


def prepare_country_stats(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        ratio_str = str(r.get('占比', '0')).strip()
        ratio = 0.0
        if ratio_str:
            ratio_str = ratio_str.rstrip('%').replace(',', '')
            try:
                ratio = float(ratio_str)
            except ValueError:
                ratio = 0.0
        rows.append({
            '排名': int(r['排名']) if pd.notna(r.get('排名')) else 0,
            '国家_地区': str(r.get('国家/地区', '')) if pd.notna(r.get('国家/地区')) else '',
            '大洲': str(r.get('大洲', '')) if pd.notna(r.get('大洲')) else '',
            '采购商数量': int(r['采购商数量']) if pd.notna(r.get('采购商数量')) else 0,
            '占比': ratio,
            '市场类型': str(r.get('市场类型', '')) if pd.notna(r.get('市场类型')) else '',
        })
    return rows


def prepare_top_exhibitors(df: pd.DataFrame) -> list[dict]:
    return [{
        '展商名称': str(r.get('展商名称', '')) if pd.notna(r.get('展商名称')) else '',
        '省份': str(r.get('省份', '')) if pd.notna(r.get('省份')) else '',
        '城市': str(r.get('城市', '')) if pd.notna(r.get('城市')) else '',
        '企业类型': str(r.get('企业类型', '')) if pd.notna(r.get('企业类型')) else '',
        '贸易形式': str(r.get('贸易形式', '')) if pd.notna(r.get('贸易形式')) else '',
        '主营产品前100字': str(r.get('主营产品(前100字)', '')) if pd.notna(r.get('主营产品(前100字)')) else '',
        '海关认证': str(r.get('海关认证', '')) if pd.notna(r.get('海关认证')) else '',
        '高新展商': str(r.get('高新展商', '')) if pd.notna(r.get('高新展商')) else '',
        '品牌展商': str(r.get('品牌展商', '')) if pd.notna(r.get('品牌展商')) else '',
        '多届参展': str(r.get('多届参展', '')) if pd.notna(r.get('多届参展')) else '',
        '参展届次': str(r.get('参展届次', '')) if pd.notna(r.get('参展届次')) else '',
        '可对接品类': str(r.get('可对接品类', '')) if pd.notna(r.get('可对接品类')) else '',
        '手机': str(r.get('手机', '')) if pd.notna(r.get('手机')) else '',
        '邮箱': str(r.get('邮箱', '')) if pd.notna(r.get('邮箱')) else '',
    } for _, r in df.iterrows()]


def prepare_pairing(df: pd.DataFrame) -> list[dict]:
    return [{
        '品类': str(r.get('品类', '')) if pd.notna(r.get('品类')) else '',
        '展商名称': str(r.get('展商名称', '')) if pd.notna(r.get('展商名称')) else '',
        '展商省份': str(r.get('展商省份', '')) if pd.notna(r.get('展商省份')) else '',
        '展商城市': str(r.get('展商城市', '')) if pd.notna(r.get('展商城市')) else '',
        '展商类型': str(r.get('展商类型', '')) if pd.notna(r.get('展商类型')) else '',
        '展商贸易形式': str(r.get('展商贸易形式', '')) if pd.notna(r.get('展商贸易形式')) else '',
        '展商亮点标签': str(r.get('展商亮点标签', '')) if pd.notna(r.get('展商亮点标签')) else '',
        '展商主营产品': str(r.get('展商主营产品', '')) if pd.notna(r.get('展商主营产品')) else '',
        '采购商名称': str(r.get('采购商名称', '')) if pd.notna(r.get('采购商名称')) else '',
        '采购商国家': str(r.get('采购商国家', '')) if pd.notna(r.get('采购商国家')) else '',
        '采购商大洲': str(r.get('采购商大洲', '')) if pd.notna(r.get('采购商大洲')) else '',
        '采购商市场层级': str(r.get('采购商市场层级', '')) if pd.notna(r.get('采购商市场层级')) else '',
        '采购商类型': str(r.get('采购商类型', '')) if pd.notna(r.get('采购商类型')) else '',
        '采购商合作意向': str(r.get('采购商合作意向', '')) if pd.notna(r.get('采购商合作意向')) else '',
        '展商联系方式': str(r.get('展商联系方式', '')) if pd.notna(r.get('展商联系方式')) else '',
        '采购商电话': str(r.get('采购商电话', '')) if pd.notna(r.get('采购商电话')) else '',
        '采购商WhatsApp链接': str(r.get('采购商WhatsApp链接', '')) if pd.notna(r.get('采购商WhatsApp链接')) else '',
    } for _, r in df.iterrows()]


def count_rows(conn, table: str) -> int:
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT COUNT(*) FROM {table}')
        return cur.fetchone()[0]
    except:
        return 0


def truncate_table(conn, table: str):
    """清空表（用于重新导入）"""
    try:
        cur = conn.cursor()
        cur.execute(f'TRUNCATE TABLE {table} CASCADE')
        conn.commit()
        print(f"  ✓ 已清空 {table}")
    except Exception as e:
        print(f"  ⚠ {table} 清空失败: {e}")


def main():
    print("=" * 60)
    print("CantonFair Pro — 直连 PostgreSQL 导入")
    print("=" * 60)
    print(f"数据文件: {DATA_FILE}")
    print(f"目标: {SUPABASE_URL}")
    print()

    print("连接数据库...")
    conn = get_conn()
    print("✓ 连接成功\n")

    # 显示当前行数
    print("当前数据量:")
    for t in ['buyers', 'exhibitors', 'category_analysis', 'country_stats', 'top_exhibitors', 'pairing']:
        n = count_rows(conn, t)
        print(f"  {t}: {n:,} 行")
    print()

    # 确认是否清空
    total_now = sum(count_rows(conn, t) for t in ['buyers', 'exhibitors', 'category_analysis', 'country_stats', 'top_exhibitors', 'pairing'])
    if total_now > 0:
        print("⚠ 发现已有数据，需要清空后重新导入")
        for t in ['buyers', 'exhibitors', 'category_analysis', 'country_stats', 'top_exhibitors', 'pairing']:
            truncate_table(conn, t)
        print()

    total_time = 0

    # 1. 采购商
    t0 = time.time()
    print("📊 采购商数据...")
    df = load_excel('采购商数据')
    data = prepare_buyers(df)
    print(f"  准备完成 {len(data):,} 行，开始插入...")
    insert_all(conn, 'buyers', data)
    elapsed = time.time() - t0
    print(f"  完成! 耗时 {elapsed:.1f}s ({len(data)/elapsed:.0f} 行/秒)\n")
    total_time += elapsed

    # 2. 参展商
    t0 = time.time()
    print("🏭 参展商数据...")
    df = load_excel('参展商数据')
    data = prepare_exhibitors(df)
    print(f"  准备完成 {len(data):,} 行，开始插入...")
    insert_all(conn, 'exhibitors', data)
    elapsed = time.time() - t0
    print(f"  完成! 耗时 {elapsed:.1f}s ({len(data)/elapsed:.0f} 行/秒)\n")
    total_time += elapsed

    # 3. 品类撮合分析
    t0 = time.time()
    print("📈 品类撮合分析...")
    df = load_excel('品类撮合分析')
    data = prepare_category_analysis(df)
    insert_all(conn, 'category_analysis', data)
    elapsed = time.time() - t0
    print(f"  完成! 耗时 {elapsed:.1f}s\n")
    total_time += elapsed

    # 4. 采购商来源分析
    t0 = time.time()
    print("🌍 采购商来源分析...")
    df = load_excel('采购商来源分析')
    data = prepare_country_stats(df)
    insert_all(conn, 'country_stats', data)
    elapsed = time.time() - t0
    print(f"  完成! 耗时 {elapsed:.1f}s\n")
    total_time += elapsed

    # 5. 高价值展商速查
    t0 = time.time()
    print("⭐ 高价值展商速查...")
    df = load_excel('高价值展商速查')
    data = prepare_top_exhibitors(df)
    insert_all(conn, 'top_exhibitors', data)
    elapsed = time.time() - t0
    print(f"  完成! 耗时 {elapsed:.1f}s\n")
    total_time += elapsed

    # 6. 品类撮合配对表
    t0 = time.time()
    print("🤝 品类撮合配对表...")
    df = load_excel('品类撮合配对表')
    data = prepare_pairing(df)
    insert_all(conn, 'pairing', data)
    elapsed = time.time() - t0
    print(f"  完成! 耗时 {elapsed:.1f}s\n")
    total_time += elapsed

    # 最终验证
    print("=" * 60)
    print("最终数据量:")
    total = 0
    for t in ['buyers', 'exhibitors', 'category_analysis', 'country_stats', 'top_exhibitors', 'pairing']:
        n = count_rows(conn, t)
        total += n
        print(f"  {t}: {n:,} 行")
    print()
    print(f"总耗时: {total_time:.0f}s, 总数据量: {total:,} 行")
    print()
    print("🎉 数据导入完成！")

    conn.close()


if __name__ == '__main__':
    main()
