"""
CantonFair Pro — 高速数据导入
使用 asyncio + httpx 并发插入

运行:
    python3 supabase/import_data_async.py
"""
import os, sys, asyncio, time, json, re
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / '.env')

import pandas as pd
import httpx

SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')

HEADERS = {
    'apikey': SERVICE_KEY,
    'Authorization': f'Bearer {SERVICE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal',
}


def lower_keys(d: dict) -> dict:
    return {k.lower(): v for k, v in d.items()}

# 并发数
MAX_CONCURRENCY = 30
BATCH_SIZE = 200

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


def col_mapping(name: str) -> str:
    return re.sub(r'[*\s/　-]+', '', str(name).strip()).lower()


def load_excel(sheet: str) -> pd.DataFrame:
    print(f"  读取 Excel 工作表 '{sheet}'...")
    df = pd.read_excel(DATA_FILE, sheet_name=sheet)
    df.columns = [col_mapping(str(c)) for c in df.columns]
    print(f"  读取完成: {len(df):,} 行")
    return df


def _score_to_tier(score: float) -> str:
    if score >= 80: return 'S'
    if score >= 65: return 'A'
    if score >= 50: return 'B'
    if score >= 35: return 'C'
    return 'D'


def prepare_buyers(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        country_raw = str(r.get('国家_地区', '')) if pd.notna(r.get('国家_地区')) else ''
        from data.data_loader import normalize_country, get_continent, get_market_level, infer_buyer_type, infer_trade_mode, infer_intent
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

        rows.append(lower_keys({
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
            '联系方式_whatsapp': str(r.get('联系方式_whatsapp', '')) if pd.notna(r.get('联系方式_whatsapp')) else '',
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
        }))
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
        rows.append(lower_keys({
            '序号': int(r['序号']) if pd.notna(r.get('序号')) else None,
            '参展商企业全称': str(r.get('参展商企业全称', '')) if pd.notna(r.get('参展商企业全称')) else '',
            '联系人': str(r.get('联系人', '')) if pd.notna(r.get('联系人')) else '',
            '职位': str(r.get('职位', '')) if pd.notna(r.get('职位')) else '',
            '手机': str(r.get('手机', '')) if pd.notna(r.get('手机')) else '',
            '邮箱': str(r.get('邮箱', '')) if pd.notna(r.get('邮箱')) else '',
            '微信_WhatsApp': str(r.get('微信WhatsApp', '')) if pd.notna(r.get('微信WhatsApp')) else '',
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
        }))
    return rows


def prepare_category_analysis(df: pd.DataFrame) -> list[dict]:
    return [lower_keys({
        '品类': str(r.get('品类', '')) if pd.notna(r.get('品类')) else '',
        '采购商数_两届合计': int(r.get('采购商数(两届合计)', 0)) if pd.notna(r.get('采购商数(两届合计)')) else 0,
        '参展商数': int(r.get('参展商数', 0)) if pd.notna(r.get('参展商数')) else 0,
        '供需比_采购商参展商': float(r.get('供需比(采购商/参展商)', 0)) if pd.notna(r.get('供需比(采购商/参展商)')) else 0.0,
        '撮合建议': str(r.get('撮合建议', '')) if pd.notna(r.get('撮合建议')) else '',
    }) for _, r in df.iterrows()]


def _parse_ratio(val) -> float:
    try:
        return float(str(val).strip().rstrip('%').replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0

def prepare_country_stats(df: pd.DataFrame) -> list[dict]:
    return [lower_keys({
        '排名': int(r.get('排名', 0)) if pd.notna(r.get('排名')) else 0,
        '国家_地区': str(r.get('国家/地区', '')) if pd.notna(r.get('国家/地区')) else '',
        '大洲': str(r.get('大洲', '')) if pd.notna(r.get('大洲')) else '',
        '采购商数量': int(r.get('采购商数量', 0)) if pd.notna(r.get('采购商数量')) else 0,
        '占比': _parse_ratio(r.get('占比', '0')),
        '市场类型': str(r.get('市场类型', '')) if pd.notna(r.get('市场类型')) else '',
    }) for _, r in df.iterrows()]


def prepare_top_exhibitors(df: pd.DataFrame) -> list[dict]:
    return [lower_keys({
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
    }) for _, r in df.iterrows()]


def prepare_pairing(df: pd.DataFrame) -> list[dict]:
    return [lower_keys({
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
    }) for _, r in df.iterrows()]


async def insert_batch(client: httpx.AsyncClient, table: str, batch: list[dict], semaphore: asyncio.Semaphore, progress: dict, lock: asyncio.Lock):
    """插入单个批次"""
    async with semaphore:
        try:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                json=batch,
                timeout=httpx.Timeout(60.0),
            )
            if resp.status_code in (200, 201, 204):
                async with lock:
                    progress['done'] += len(batch)
                    done = progress['done']
                    total = progress['total']
                    pct = int(done / total * 100) if total else 0
                    print(f"\r  [{table}] {done:,}/{total:,} ({pct}%)", end='', flush=True)
            else:
                async with lock:
                    progress['failed'] += len(batch)
                    err_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
                    if err_msg not in progress['errors']:
                        progress['errors'].append(err_msg)
        except Exception as e:
            async with lock:
                progress['failed'] += len(batch)
                progress['errors'].append(str(e)[:100])


async def insert_all(table: str, data: list[dict]):
    """并发插入所有数据"""
    total = len(data)
    progress = {'done': 0, 'failed': 0, 'total': total, 'errors': []}
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    batches = [data[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    connector = httpx.AsyncHTTP2Connection(min_flush_interval=0.001) if hasattr(httpx, 'AsyncHTTP2Connection') else None
    async with httpx.AsyncClient(headers=HEADERS, timeout=httpx.Timeout(60.0), limits=httpx.Limits(max_connections=MAX_CONCURRENCY)) as client:
        tasks = [insert_batch(client, table, batch, semaphore, progress, lock) for batch in batches]
        await asyncio.gather(*tasks)

    print()
    if progress['failed']:
        print(f"  ⚠ {progress['failed']:,} 行失败")
        for err in progress['errors'][:3]:
            print(f"    {err[:100]}")
    return progress['done']


async def import_table(table: str, loader_fn, name: str):
    """导入单个表"""
    print(f"\n{'='*50}")
    print(f"{name}...")
    t0 = time.time()

    print(f"  准备数据...")
    data = loader_fn()
    print(f"  数据准备完成: {len(data):,} 行, 预计 {len(data)//BATCH_SIZE + 1} 个批次")
    print(f"  并发数: {MAX_CONCURRENCY}, 批次大小: {BATCH_SIZE}")

    inserted = await insert_all(table, data)
    elapsed = time.time() - t0
    rate = inserted / elapsed if elapsed > 0 else 0
    print(f"  完成: {inserted:,}/{len(data):,} 行, 耗时 {elapsed:.1f}s ({rate:.0f} 行/秒)")
    return inserted


async def main():
    print("=" * 60)
    print("CantonFair Pro — 高速数据导入 (异步并发版)")
    print("=" * 60)
    print(f"数据文件: {DATA_FILE}")
    print(f"Supabase:  {SUPABASE_URL}")
    print(f"并发数: {MAX_CONCURRENCY}, 批次: {BATCH_SIZE}")
    print()

    total_time = 0

    # 1. 采购商
    t0 = time.time()
    print("📊 采购商数据...")
    df = load_excel('采购商数据')
    data = prepare_buyers(df)
    inserted = await insert_all('buyers', data)
    elapsed = time.time() - t0
    print(f"  完成: {inserted:,} 行, {elapsed:.1f}s")
    total_time += elapsed

    # 2. 参展商
    t0 = time.time()
    print("\n🏭 参展商数据...")
    df = load_excel('参展商数据')
    data = prepare_exhibitors(df)
    inserted = await insert_all('exhibitors', data)
    elapsed = time.time() - t0
    print(f"  完成: {inserted:,} 行, {elapsed:.1f}s")
    total_time += elapsed

    # 3. 品类撮合分析
    t0 = time.time()
    print("\n📈 品类撮合分析...")
    df = load_excel('品类撮合分析')
    data = prepare_category_analysis(df)
    inserted = await insert_all('category_analysis', data)
    elapsed = time.time() - t0
    print(f"  完成: {inserted:,} 行, {elapsed:.1f}s")
    total_time += elapsed

    # 4. 采购商来源分析
    t0 = time.time()
    print("\n🌍 采购商来源分析...")
    df = load_excel('采购商来源分析')
    data = prepare_country_stats(df)
    inserted = await insert_all('country_stats', data)
    elapsed = time.time() - t0
    print(f"  完成: {inserted:,} 行, {elapsed:.1f}s")
    total_time += elapsed

    # 5. 高价值展商速查
    t0 = time.time()
    print("\n⭐ 高价值展商速查...")
    df = load_excel('高价值展商速查')
    data = prepare_top_exhibitors(df)
    inserted = await insert_all('top_exhibitors', data)
    elapsed = time.time() - t0
    print(f"  完成: {inserted:,} 行, {elapsed:.1f}s")
    total_time += elapsed

    # 6. 品类撮合配对表
    t0 = time.time()
    print("\n🤝 品类撮合配对表...")
    df = load_excel('品类撮合配对表')
    data = prepare_pairing(df)
    inserted = await insert_all('pairing', data)
    elapsed = time.time() - t0
    print(f"  完成: {inserted:,} 行, {elapsed:.1f}s")
    total_time += elapsed

    print()
    print("=" * 60)
    print(f"🎉 全部完成! 总耗时: {total_time:.0f}s")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
