"""
数据加载与预处理层
支持模式：
  1. Supabase (优先) — Serverless，查询下推到数据库
  2. 本地 Excel (回退) — 开发/本地调试用
"""
import os, re, json, asyncio
import pandas as pd
import numpy as np
import httpx
from collections import Counter
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))


# ========== 配置 ==========
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')  # anon key
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
# 服务端优先用 service_role key 避免 PostgREST page_size 限制
USE_SUPABASE_KEY = SUPABASE_SERVICE_KEY or SUPABASE_KEY
USE_SUPABASE = bool(SUPABASE_URL and USE_SUPABASE_KEY)

DATA_FILE = os.environ.get(
    'DATA_FILE_PATH',
    os.path.join(BASE_DIR, '广交会数据综合整理_标准格式.xlsx')
)

PARQUET_DIR = os.path.join(BASE_DIR, 'data', 'parquet_cache')
os.makedirs(PARQUET_DIR, exist_ok=True)

SHEET_TO_PARQUET = {
    '采购商数据': 'buyers',
    '参展商数据': 'exhibitors',
    '品类撮合分析': 'category_analysis',
    '采购商来源分析': 'country_stats',
    '高价值展商速查': 'top_exhibitors',
    '品类撮合配对表': 'pairing',
}


# ========== Supabase 客户端 (懒加载) ==========
_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, USE_SUPABASE_KEY)
    return _supabase_client


async def _fetch_all_async(table: str, columns: str = '*', page_size: int = 1000) -> list[dict]:
    """通过 offset 分页获取表全部数据（绕过 PostgREST 1000 行限制）"""
    results = []
    headers = {
        'apikey': USE_SUPABASE_KEY,
        'Authorization': f'Bearer {USE_SUPABASE_KEY}',
        'Content-Type': 'application/json',
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        offset = 0
        while True:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/{table}?select={columns}&offset={offset}&limit={page_size}",
                headers=headers,
            )
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")
            rows = r.json()
            if not rows:
                break
            results.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size
            if offset >= 500_000:
                break
    return results


# ========== 国家/地区标准化映射 ==========
COUNTRY_NORMALIZE = {
    '中 国 香 港 .': '中国香港', '中 国 香 港': '中国香港', '香港': '中国香港',
    '中 国 澳 门 .': '中国澳门', '中 国 澳 门': '中国澳门', '澳门': '中国澳门',
    '中 国 台 湾 .': '中国台湾', '中 国 台 湾': '中国台湾', '台湾': '中国台湾',
    '台湾省': '中国台湾', '中 国': '中国', '中        国.': '中国',
    '美        国.': '美国', '美 国': '美国',
    '英        国.': '英国', '英 国': '英国',
    '德        国.': '德国', '德 国': '德国',
    '法        国.': '法国', '法 国': '法国',
    '意大利': '意大利', '意   大   利.': '意大利', '意 大 利': '意大利',
    '澳 大  利  亚.': '澳大利亚', '澳大利亚': '澳大利亚',
    '荷        兰.': '荷兰', '荷 兰': '荷兰',
    '日        本.': '日本', '日本': '日本',
    '韩        国.': '韩国', '韩国': '韩国',
    '印        度.': '印度', '印度': '印度',
    '泰        国.': '泰国', '泰国': '泰国',
    '西   班   牙.': '西班牙', '西 班 牙': '西班牙',
    '挪        威.': '挪威', '挪 威': '挪威',
    '瑞        典.': '瑞典', '瑞典': '瑞典',
    '丹        麦.': '丹麦', '丹 麦': '丹麦',
    '芬        兰.': '芬兰', '芬 兰': '芬兰',
    '俄   罗   斯.': '俄罗斯', '俄 罗 斯': '俄罗斯', '俄罗斯联邦': '俄罗斯',
    '奥   地   泊.': '奥地利', '奥地利': '奥地利',
    '希        腊.': '希腊', '希 腊': '希腊',
    '巴   拿   马.': '巴拿马', '巴 拿 马': '巴拿马',
    '阿拉伯联合酋长国': '阿联酋', '阿联酋': '阿联酋',
    '沙特阿拉伯': '沙特阿拉伯', '伊朗': '伊朗',
    '冰岛': '欧洲', '波斯尼亚黑塞哥维那共和国': '波斯尼亚和黑塞哥维那',
    '博茨瓦那': '博茨瓦纳',
}

CONTINENT_MAP = {
    '中国香港': '亚洲', '中国澳门': '亚洲', '中国台湾': '亚洲',
    '中国': '亚洲', '日本': '亚洲', '韩国': '亚洲', '印度': '亚洲',
    '印度尼西亚': '亚洲', '马来西亚': '亚洲', '新加坡': '亚洲',
    '泰国': '亚洲', '越南': '亚洲', '菲律宾': '亚洲',
    '美国': '北美洲', '加拿大': '北美洲', '墨西哥': '北美洲',
    '巴西': '南美洲', '阿根廷': '南美洲', '智利': '南美洲',
    '哥伦比亚': '南美洲', '秘鲁': '南美洲',
    '英国': '欧洲', '德国': '欧洲', '法国': '欧洲', '意大利': '欧洲', '荷兰': '欧洲',
    '比利时': '欧洲', '西班牙': '欧洲', '波兰': '欧洲', '俄罗斯': '欧洲',
    '瑞典': '欧洲', '丹麦': '欧洲', '挪威': '欧洲', '芬兰': '欧洲',
    '奥地利': '欧洲', '瑞士': '欧洲', '希腊': '欧洲',
    '澳大利亚': '大洋洲', '新西兰': '大洋洲',
    '埃及': '非洲', '南非': '非洲', '尼日利亚': '非洲', '肯尼亚': '非洲', '摩洛哥': '非洲',
}

MARKET_LEVEL_MAP = {'北美洲': '发达市场', '欧洲': '发达市场', '大洋洲': '发达市场'}

BUYER_TYPE_PATTERNS = {
    '跨国进口商': [r'IMPORT', r'TRADING', r'TRADE', r'GROUP', r'CORP', r'HOLDING'],
    '品牌代理商': [r'BRAND', r'AGENCY', r'DISTRIBUTOR'],
    '连锁商超采购': [r'SUPERMARKET', r'CHAIN', r'MART', r'RETAIL'],
    '工程采购方': [r'CONSTRUCTION', r'ENGINEERING', r'PROJECTS'],
    '跨境电商大卖': [r'AMAZON', r'EBAY', r'SHOPEE', r'LAZADA'],
    '区域批发商': [r'WHOLESALE', r'WHOLESALER'],
}

TRADE_MODE_PATTERNS = {
    'OEM/ODM代工': [r'OEM', r'ODM', r'MANUFACTUR'],
    '批量采购': [r'WHOLESALE', r'BULK'],
    '代理经销': [r'DISTRIBUTOR', r'AGENT'],
}


def normalize_country(raw):
    if not raw or pd.isna(raw):
        return '其他国家'
    t = str(raw).strip().rstrip('.').replace(' ', '')
    t = re.sub(r'数据由.*$', '', t)
    if not t:
        return '其他国家'
    if t in COUNTRY_NORMALIZE:
        return COUNTRY_NORMALIZE[t]
    for k, v in COUNTRY_NORMALIZE.items():
        if k in t or t in k:
            return v
    if t in CONTINENT_MAP:
        return t
    for k, v in CONTINENT_MAP.items():
        if k in t or t in k:
            return k
    return t


def get_continent(country):
    return CONTINENT_MAP.get(str(country).strip(), '其他')


def get_market_level(continent):
    return MARKET_LEVEL_MAP.get(continent, '新兴市场')


def infer_buyer_type(company, country):
    text = f"{company} {country}".upper()
    for btype, patterns in BUYER_TYPE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return btype
    return ''


def infer_trade_mode(company):
    text = str(company).upper()
    for mode, patterns in TRADE_MODE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return mode
    return ''


def infer_intent(sessions):
    if not sessions:
        return '中意向（选品备货）'
    return '高意向（紧急找货）' if ';' in str(sessions) else '中意向（选品备货）'


# ========== 数据加载器 ==========
class DataLoader:
    """
    统一数据加载接口。
    - 有 Supabase 凭据时：从 Supabase 查询（Serverless）
    - 无凭据时：回退到本地 Excel
    """

    def __init__(self, data_file=None):
        self._data_file = data_file
        self._buyers = None
        self._exhibitors = None
        self._stats = None

    @property
    def data_file(self):
        return self._data_file or DATA_FILE

    # ---- 底层数据获取 ----

    def _load_from_excel(self, sheet_name: str) -> pd.DataFrame:
        """从 Excel/Parquet 加载（回退方案）"""
        pq_name = SHEET_TO_PARQUET.get(sheet_name)
        if pq_name:
            pq_path = os.path.join(PARQUET_DIR, f'{pq_name}.parquet')
            if os.path.exists(pq_path):
                try:
                    return pd.read_parquet(pq_path)
                except Exception:
                    pass

        path = self._resolve_excel_path()
        if path and os.path.exists(path):
            try:
                return pd.read_excel(path, sheet_name=sheet_name)
            except Exception as e:
                print(f"[DataLoader] Excel 读取失败: {e}")
        return pd.DataFrame()

    def _resolve_excel_path(self) -> Optional[str]:
        if self._data_file and os.path.exists(self._data_file):
            return self._data_file
        default = os.path.join(BASE_DIR, '广交会数据综合整理_标准格式.xlsx')
        if os.path.exists(default):
            return default
        return None

    def _load_from_supabase(self, table: str, limit: int = 500000) -> pd.DataFrame:
        """从 Supabase 分页查询全部数据（绕过 PostgREST 1000 行限制）"""
        if not USE_SUPABASE:
            return pd.DataFrame()
        try:
            all_rows = asyncio.run(_fetch_all_async(table))
            if limit and len(all_rows) > limit:
                all_rows = all_rows[:limit]
            if all_rows:
                return pd.DataFrame(all_rows)
        except Exception as e:
            err_msg = str(e)
            if 'apikey' in err_msg.lower() or 'unauthorized' in err_msg.lower() or '403' in err_msg:
                raise Exception(
                    "⚠️ Supabase 密钥无效或已过期。请检查 Streamlit Cloud 的 Secrets 配置：\n"
                    "SUPABASE_URL、SUPABASE_KEY、SUPABASE_SERVICE_ROLE_KEY"
                ) from e
            if 'connection' in err_msg.lower() or 'timeout' in err_msg.lower() or 'network' in err_msg.lower():
                raise Exception(
                    "⚠️ 无法连接到 Supabase。请检查 SUPABASE_URL 是否正确，以及网络是否通畅。"
                ) from e
            # 未知错误也抛出，让调用方能感知
            raise Exception(f"Supabase 查询失败 ({table}): {e}") from e

    def _load_buyers_supabase(self) -> pd.DataFrame:
        df = self._load_from_supabase('buyers')
        if df.empty:
            return df

        # 补充标准化字段（如果 DB 没有则计算）
        if '国家_标准化' not in df.columns or df['国家_标准化'].isna().all():
            country_col = '国家_地区' if '国家_地区' in df.columns else ('国家/地区' if '国家/地区' in df.columns else None)
            raw_countries = df[country_col] if country_col else pd.Series([''] * len(df))
            df['国家_标准化'] = raw_countries.apply(normalize_country)
        if '大洲' not in df.columns or df['大洲'].isna().all():
            df['大洲'] = df['国家_标准化'].apply(get_continent)
        if '市场层级' not in df.columns or df['市场层级'].isna().all():
            df['市场层级'] = df['大洲'].apply(get_market_level)
        if '采购商类型_final' not in df.columns or df['采购商类型_final'].isna().all():
            btype_raw = self._safe_series(df, '采购商类型', '')
            btype_inf = df.apply(
                lambda r: infer_buyer_type(str(r.get('采购商企业全称', '')),
                                          str(r.get('国家_标准化', ''))), axis=1)
            df['采购商类型_final'] = btype_raw.where(btype_raw != '', btype_inf)
        if '合作意向_final' not in df.columns or df['合作意向_final'].isna().all():
            intent_raw = self._safe_series(df, '合作意向', '')
            sessions = self._safe_series(df, '参展届次', '')
            df['合作意向_final'] = intent_raw.where(intent_raw != '', sessions.apply(infer_intent))

        df = self._normalize_columns(df)
        return df

    def _load_exhibitors_supabase(self) -> pd.DataFrame:
        df = self._load_from_supabase('exhibitors')
        if df.empty:
            return df

        if '企业类型_final' not in df.columns or df['企业类型_final'].isna().all():
            etype = df['企业类型'].fillna('') if '企业类型' in df.columns else pd.Series([''] * len(df))
            df['企业类型_final'] = etype

        def get_advantages(row):
            advs = []
            for col in ['海关认证', '高新展商', '品牌展商', '创新奖', 'CF奖']:
                if str(row.get(col, '')).strip() == 'Y':
                    advs.append(col.replace('展商', ''))
            return '; '.join(advs) if advs else ''

        if '核心优势' not in df.columns or df['核心优势'].isna().all():
            df['核心优势'] = df.apply(get_advantages, axis=1)

        df = self._normalize_columns(df)
        return df

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """统一 DB 列名 → app.py 期望的列名（DB 列名全小写）"""
        if df.empty:
            return df
        # DB 列名全小写，映射到 app.py 期望的列名
        col_map = {
            # buyers
            '国家_地区': '国家/地区',
            '联系方式_电话': '联系方式-电话',
            '联系方式_邮箱': '联系方式-邮箱',
            '联系方式_whatsapp': '联系方式-WhatsApp',
            '联系方式_传真': '联系方式-传真',
            # exhibitors
            '参展商企业全称': '展商名称',
            # category_analysis
            '采购商数_两届合计': '采购商数(两届合计)',
            '供需比_采购商参展商': '供需比(采购商/参展商)',
            # top_exhibitors
            '主营产品前100字': '主营产品(前100字)',
        }
        df = df.rename(columns=col_map)
        # 兼容：若 DB 列名本身就是小写格式，补充短横线格式
        for db_col, app_col in [
            ('联系方式_电话', '联系方式-电话'),
            ('联系方式_邮箱', '联系方式-邮箱'),
            ('联系方式_whatsapp', '联系方式-WhatsApp'),
        ]:
            if app_col not in df.columns and db_col in df.columns:
                df[app_col] = df[db_col]
        return df

    # ---- 公开 API ----

    def _safe_series(self, df: pd.DataFrame, col: str, default=''):
        """安全获取列，防止重复列名返回 DataFrame"""
        if col not in df.columns:
            return pd.Series([default] * len(df), index=df.index)
        result = df[col]
        if isinstance(result, pd.DataFrame):
            return result.iloc[:, 0].fillna(default)
        return result.fillna(default)

    def load_buyers(self, force=False):
        if self._buyers is not None and not force:
            return self._buyers

        if USE_SUPABASE:
            df = self._load_buyers_supabase()
        else:
            df = self._load_from_excel('采购商数据')

        # 统一处理：确保 合作意向_final 列存在
        if '合作意向_final' not in df.columns or df['合作意向_final'].isna().all():
            if not df.empty:
                intent_raw = self._safe_series(df, '合作意向', '')
                sessions = self._safe_series(df, '参展届次', '')
                def _infer_int(s):
                    if pd.isna(s) or str(s).strip() == '':
                        return '意向待定'
                    sess = str(s)
                    if ';' in sess:
                        return '高意向（多届参展）'
                    return '一般意向'
                df['合作意向_final'] = intent_raw.where(intent_raw != '', sessions.apply(_infer_int))
            else:
                df['合作意向_final'] = pd.Series(dtype=str)

        self._buyers = df
        return df

    def load_exhibitors(self, force=False):
        if self._exhibitors is not None and not force:
            return self._exhibitors

        if USE_SUPABASE:
            df = self._load_exhibitors_supabase()
        else:
            df = self._load_from_excel('参展商数据')

        self._exhibitors = df
        return df

    def load_pairing_data(self):
        if USE_SUPABASE:
            df = self._load_from_supabase('pairing')
            return df.rename(columns={'采购商企业全称': '采购商企业全称'})
        return self._load_from_excel('品类撮合配对表')

    def load_analysis_data(self):
        if USE_SUPABASE:
            return self._load_from_supabase('category_analysis')
        return self._load_from_excel('品类撮合分析')

    def load_country_stats(self):
        if USE_SUPABASE:
            return self._load_from_supabase('country_stats')
        return self._load_from_excel('采购商来源分析')

    def load_high_value_exhibitors(self):
        if USE_SUPABASE:
            return self._load_from_supabase('top_exhibitors')
        return self._load_from_excel('高价值展商速查')

    def get_stats(self):
        if self._stats is not None:
            return self._stats

        buyers = self.load_buyers()
        exhibitors = self.load_exhibitors()

        # 无条件确保 buyers 有合作意向_final 列
        if '合作意向_final' not in buyers.columns:
            buyers['合作意向_final'] = '意向待定'
        if buyers.empty:
            self._stats = {
                'buyer_count': 0, 'exhibitor_count': 0,
                'buyer_with_email': 0, 'buyer_with_phone': 0,
                'buyer_with_wa': 0, 'high_intent_buyers': 0,
                'two_session_buyers': 0, 'exhibitors_two_session': 0,
                'continents': {},
            }
            return self._stats

        # 安全获取列数据
        def _safe(df, col, default=''):
            if col in df.columns:
                return df[col].fillna(default)
            return pd.Series([default] * len(df))

        email_col = _safe(buyers, '联系方式-邮箱')
        phone_col = _safe(buyers, '联系方式-电话')
        wa_col = _safe(buyers, '联系方式-WhatsApp')
        intent_col = _safe(buyers, '合作意向_final')
        session_col = _safe(buyers, '参展届次')
        continent_col = _safe(buyers, '大洲')
        ex_session_col = _safe(exhibitors, '参展届次') if not exhibitors.empty else pd.Series([''])

        self._stats = {
            'buyer_count': len(buyers),
            'exhibitor_count': len(exhibitors),
            'buyer_with_email': int((email_col.notna() & (email_col != '')).sum()),
            'buyer_with_phone': int((phone_col.notna() & (phone_col != '')).sum()),
            'buyer_with_wa': int((wa_col.notna() & (wa_col != '')).sum()),
            'high_intent_buyers': int((intent_col.str.contains('高意向', na=False)).sum()),
            'two_session_buyers': int((session_col.str.contains(';', na=False)).sum()),
            'exhibitors_two_session': int((ex_session_col.str.contains(';', na=False)).sum()),
            'continents': continent_col.value_counts().to_dict() if len(continent_col) else {},
        }
        return self._stats


_loader = None


def get_loader(data_file=None):
    global _loader
    if _loader is None:
        _loader = DataLoader(data_file)
    return _loader
