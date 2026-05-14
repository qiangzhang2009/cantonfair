"""
线索评分与分层引擎
基于多维度指标对采购商和参展商进行价值评估
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class LeadScore:
    """线索评分结果"""
    overall: float       # 0-100 总分
    intent_score: float  # 意向分
    reach_score: float   # 触达分
    value_score: float   # 价值分
    quality_score: float # 质量分
    tier: str            # 等级: S/A/B/C/D
    tier_color: str      # 颜色: gold/silver/bronze/gray/blue
    breakdown: dict      # 分项得分明细


TIER_CONFIG = {
    'S': {'min': 80, 'color': '#FFD700', 'label': 'S级 钻石客户', 'emoji': '💎'},
    'A': {'min': 65, 'color': '#4169E1', 'label': 'A级 重点客户', 'emoji': '⭐'},
    'B': {'min': 50, 'color': '#228B22', 'label': 'B级 优质客户', 'emoji': '👍'},
    'C': {'min': 35, 'color': '#FFA500', 'label': 'C级 普通客户', 'emoji': '📌'},
    'D': {'min': 0,  'color': '#808080', 'label': 'D级 潜在客户', 'emoji': '📋'},
}


def calc_contact_score(row) -> float:
    """触达可能性评分 0-100"""
    score = 0
    has_email = str(row.get('联系方式-邮箱', '')).strip() not in ('', 'nan')
    has_phone = str(row.get('联系方式-电话', '')).strip() not in ('', 'nan')
    has_wa = str(row.get('联系方式-WhatsApp', '')).strip() not in ('', 'nan')
    has_contact = str(row.get('联系人', '')).strip() not in ('', 'nan')

    # 联系方式数量
    contact_count = sum([has_email, has_phone, has_wa])
    score += contact_count * 25  # 每种联系方式+25

    # 有联系人姓名额外加分
    if has_contact: score += 15

    # 有WhatsApp优先
    if has_wa: score += 10

    return min(score, 100)


def calc_value_score(row, continent: str = None) -> float:
    """采购商价值评分 0-100"""
    score = 0

    # 大洲市场权重
    market_weights = {
        '北美洲': 25, '欧洲': 22, '大洋洲': 18,
        '亚洲': 12, '南美洲': 10, '非洲': 8, '其他': 5
    }
    cont = continent or str(row.get('大洲', '其他'))
    score += market_weights.get(cont, 5)

    # 采购商类型
    buyer_type = str(row.get('采购商类型_final', row.get('采购商类型', '')))
    type_weights = {
        '跨国进口商': 25, '连锁商超采购': 25, '品牌代理商': 20,
        '跨境电商大卖': 20, '工程采购方': 18, '区域批发商': 15,
        '贸易中间商': 10, '中小零售商': 8, '': 5,
    }
    score += type_weights.get(buyer_type, 5)

    # 合作模式
    trade_mode = str(row.get('合作模式_final', row.get('合作模式', '')))
    if 'OEM' in trade_mode or '代工' in trade_mode: score += 15
    elif '批量' in trade_mode: score += 12
    elif '长期' in trade_mode: score += 10
    elif '代理' in trade_mode: score += 8

    # 活跃度
    sessions = str(row.get('参展届次', ''))
    score += min(sessions.count(';') * 10 + sessions.count('届') * 5, 20)

    return min(score, 100)


def calc_intent_score(row) -> float:
    """意向强度评分 0-100"""
    score = 0
    intent = str(row.get('合作意向_final', row.get('合作意向', '')))
    if '高意向' in intent: score += 50
    elif '中意向' in intent: score += 30
    else: score += 10

    # 参加届次
    sessions = str(row.get('参展届次', ''))
    if '138' in sessions and '139' in sessions: score += 40
    elif '138' in sessions or '139' in sessions: score += 20

    # 多品类采购
    cats = str(row.get('主营品类', ''))
    cat_count = cats.count(';') + (1 if cats.strip() else 0)
    score += min(cat_count * 5, 15)

    return min(score, 100)


def calc_quality_score(row) -> float:
    """数据质量评分 0-100"""
    score = 0
    # 企业名称完整度
    name = str(row.get('采购商企业全称', ''))
    if len(name) > 5: score += 25
    if any(c.isalpha() for c in name) and any('\u4e00' <= c <= '\u9fff' for c in name): score += 15
    elif any(c.isalpha() for c in name): score += 20

    # 地址信息
    addr = str(row.get('地址', ''))
    if addr and addr not in ('', 'nan'): score += 20

    # 国家信息
    country = str(row.get('国家/地区', ''))
    if country and country not in ('', 'nan'): score += 20

    # 官网
    website = str(row.get('官网', ''))
    if website and website not in ('', 'nan') and '.' in website: score += 20

    return min(score, 100)


def calc_exhibitor_value_score(row) -> float:
    """参展商价值评分 0-100"""
    score = 0
    # 标签加成
    for col in ['海关认证展商','高新展商','品牌展商','创新奖','CF奖']:
        if str(row.get(col, '')).strip() == 'Y': score += 15

    # 企业类型
    etype = str(row.get('企业类型_final', row.get('企业类型', '')))
    type_scores = {
        '源头工厂': 30, '工贸一体': 28, 'OEM/ODM代工厂': 25,
        '品牌方': 25, '纯外贸公司': 15,
    }
    score += type_scores.get(etype, 10)

    # 主营产品丰富度
    prod = str(row.get('主营产品', ''))
    if len(prod) > 100: score += 20
    elif len(prod) > 50: score += 15
    elif len(prod) > 20: score += 10

    # 联系方式
    phone = str(row.get('手机', '')).strip()
    email = str(row.get('邮箱', '')).strip()
    if phone and phone not in ('', 'nan'): score += 10
    if email and email not in ('', 'nan'): score += 10

    # 双届参展
    sessions = str(row.get('参展届次', ''))
    if '138' in sessions and '139' in sessions: score += 15
    elif '138' in sessions or '139' in sessions: score += 5

    return min(score, 100)


def score_buyer(row) -> LeadScore:
    """综合评分采购商"""
    i_score = calc_intent_score(row)
    r_score = calc_contact_score(row)
    v_score = calc_value_score(row)
    q_score = calc_quality_score(row)

    # 加权总评
    overall = i_score * 0.35 + r_score * 0.25 + v_score * 0.25 + q_score * 0.15

    # 确定等级
    tier = 'D'
    tier_color = '#808080'
    for t, cfg in TIER_CONFIG.items():
        if overall >= cfg['min']:
            tier = t
            tier_color = cfg['color']
            break

    return LeadScore(
        overall=round(overall, 1),
        intent_score=round(i_score, 1),
        reach_score=round(r_score, 1),
        value_score=round(v_score, 1),
        quality_score=round(q_score, 1),
        tier=tier,
        tier_color=tier_color,
        breakdown={'意向分': i_score, '触达分': r_score, '价值分': v_score, '质量分': q_score}
    )


def score_exhibitor(row) -> LeadScore:
    """综合评分参展商"""
    v_score = calc_exhibitor_value_score(row)
    # 参展商触达分（仅看联系方式）
    r_score = 50 if str(row.get('手机','')).strip() not in ('','nan') else 0
    if str(row.get('邮箱','')).strip() not in ('','nan'): r_score += 30
    if str(row.get('微信/WhatsApp','')).strip() not in ('','nan'): r_score += 20
    r_score = min(r_score, 100)

    overall = v_score  # 参展商暂以价值分为总评基准
    tier = 'D'
    tier_color = '#808080'
    for t, cfg in TIER_CONFIG.items():
        if overall >= cfg['min']:
            tier = t
            tier_color = cfg['color']
            break

    return LeadScore(
        overall=round(overall, 1),
        intent_score=50,  # N/A for exhibitors
        reach_score=round(r_score, 1),
        value_score=round(v_score, 1),
        quality_score=50,
        tier=tier,
        tier_color=tier_color,
        breakdown={'触达分': r_score, '价值分': v_score}
    )


def rank_buyers(df: pd.DataFrame, sample_limit: int = None) -> pd.DataFrame:
    """批量评分采购商"""
    if df.empty:
        return df

    limit = sample_limit or len(df)
    sample_df = df.head(limit).copy()

    scores = []
    for _, row in sample_df.iterrows():
        s = score_buyer(row)
        scores.append({
            '综合评分': s.overall,
            '意向分': s.intent_score,
            '触达分': s.reach_score,
            '价值分': s.value_score,
            '质量分': s.quality_score,
            '客户等级': s.tier,
            '等级颜色': s.tier_color,
        })

    score_df = pd.DataFrame(scores)
    result = pd.concat([sample_df.reset_index(drop=True), score_df], axis=1)
    return result


def rank_exhibitors(df: pd.DataFrame, sample_limit: int = None) -> pd.DataFrame:
    """批量评分参展商"""
    if df.empty:
        return df

    limit = sample_limit or len(df)
    sample_df = df.head(limit).copy()

    scores = []
    for _, row in sample_df.iterrows():
        s = score_exhibitor(row)
        scores.append({
            '综合评分': s.overall,
            '触达分': s.reach_score,
            '价值分': s.value_score,
            '客户等级': s.tier,
            '等级颜色': s.tier_color,
        })

    score_df = pd.DataFrame(scores)
    result = pd.concat([sample_df.reset_index(drop=True), score_df], axis=1)
    return result


def get_tier_distribution(df: pd.DataFrame, score_col='客户等级') -> dict:
    """获取等级分布"""
    if score_col not in df.columns:
        return {}
    return df[score_col].value_counts().to_dict()


def filter_top_tier(df: pd.DataFrame, tier: str = 'S', score_col='客户等级') -> pd.DataFrame:
    """筛选特定等级以上的客户"""
    tiers = ['S', 'A', 'B', 'C', 'D']
    if tier not in tiers:
        return df
    min_idx = tiers.index(tier)
    allowed = tiers[min_idx:]
    return df[df[score_col].isin(allowed)]
