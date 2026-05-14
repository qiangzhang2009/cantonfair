"""
自进化引擎
基于用户行为数据持续优化匹配算法和评分模型
"""
import json, os, datetime
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


@dataclass
class BehaviorEvent:
    """用户行为事件"""
    event_type: str   # match_view / outreach_send / outreach_reply / deal_close / outreach_fail
    entity_type: str  # buyer / exhibitor
    entity_id: str
    metadata: dict
    timestamp: str


@dataclass
class EvolutionInsight:
    """进化洞察"""
    category: str
    metric: str
    value: float
    trend: str  # up / down / stable
    confidence: float  # 置信度 0-1
    sample_size: int
    recommendation: str


class EvolutionEngine:
    """
    自进化引擎：通过收集和分析用户行为，持续优化系统
    - 哪些品类匹配率高 → 优先推送
    - 哪些触达渠道更有效 → 优先使用
    - 哪些话术回复率高 → 优先使用
    - 评分模型校准 → 自动调整权重
    """

    def __init__(self, save_path='evolution_data.json'):
        self.save_path = save_path
        self.events: List[BehaviorEvent] = []
        self.match_success_counter = Counter()      # 品类 → 成交次数
        self.channel_performance = defaultdict(lambda: {'send': 0, 'reply': 0, 'fail': 0})
        self.tier_accuracy = {'S': {'converted': 0, 'total': 0},
                              'A': {'converted': 0, 'total': 0},
                              'B': {'converted': 0, 'total': 0},
                              'C': {'converted': 0, 'total': 0},
                              'D': {'converted': 0, 'total': 0}}
        self.buyer_country_success = Counter()
        self.scoring_weights = {
            'intent': 0.35,
            'reach': 0.25,
            'value': 0.25,
            'quality': 0.15,
        }
        self.category_rank = []  # 按成功率排序的品类
        self.load()

    def record_event(self, event: BehaviorEvent):
        """记录用户行为"""
        self.events.append(event)
        self._process_event(event)
        self.evolve()
        self.save()

    def _process_event(self, event: BehaviorEvent):
        """处理单个事件，更新统计"""
        if event.event_type == 'outreach_send':
            channel = event.metadata.get('channel', 'unknown')
            self.channel_performance[channel]['send'] += 1

        elif event.event_type == 'outreach_reply':
            channel = event.metadata.get('channel', 'unknown')
            self.channel_performance[channel]['reply'] += 1
            entity_type = event.entity_type
            entity_id = event.entity_id
            self.match_success_counter[f"reply_{entity_type}"] += 1

        elif event.event_type == 'deal_close':
            cat = event.metadata.get('category', 'unknown')
            country = event.metadata.get('country', 'unknown')
            tier = event.metadata.get('tier', 'unknown')
            self.match_success_counter[cat] += 1
            self.buyer_country_success[country] += 1
            if tier in self.tier_accuracy:
                self.tier_accuracy[tier]['converted'] += 1

        elif event.event_type == 'outreach_fail':
            channel = event.metadata.get('channel', 'unknown')
            self.channel_performance[channel]['fail'] += 1

    def evolve(self):
        """基于累积数据进化算法"""
        # 1. 更新品类排序
        self._update_category_ranking()

        # 2. 校准评分权重
        self._calibrate_weights()

        # 3. 更新渠道性能
        self._update_channel_ranking()

    def _update_category_ranking(self):
        """按成交率排序品类"""
        cat_scores = {}
        for cat, count in self.match_success_counter.items():
            if cat.startswith('reply_') or cat.startswith('deal_'):
                continue
            sent = sum(1 for e in self.events
                      if e.event_type == 'outreach_send'
                      and e.metadata.get('category') == cat)
            if sent > 0:
                cat_scores[cat] = count / sent
        self.category_rank = sorted(cat_scores.items(), key=lambda x: -x[1])

    def _calibrate_weights(self):
        """基于等级准确率校准评分权重"""
        # 如果S级转化率低，说明价值分权重过高
        s_rate = (self.tier_accuracy['S']['converted'] /
                  max(self.tier_accuracy['S']['total'], 1))
        if self.tier_accuracy['S']['total'] > 5:
            if s_rate < 0.05:  # S级转化率低于5%
                self.scoring_weights['value'] = max(0.10, self.scoring_weights['value'] - 0.05)
                self.scoring_weights['intent'] = min(0.50, self.scoring_weights['intent'] + 0.05)

    def _update_channel_ranking(self):
        """按回复率排序触达渠道"""
        pass  # 已在 channel_performance 中维护

    def get_best_channel(self, entity_type: str = 'buyer') -> str:
        """获取最佳触达渠道"""
        best = None
        best_rate = -1
        for channel, perf in self.channel_performance.items():
            total = perf['send']
            replies = perf['reply']
            if total >= 3:  # 至少3次发送才统计
                rate = replies / total
                if rate > best_rate:
                    best_rate = rate
                    best = channel
        return best or 'WhatsApp'

    def get_category_priority(self, category: str) -> float:
        """获取品类优先级（0-1）"""
        if not self.category_rank:
            return 0.5
        if not self.category_rank:
            return 0.5
        # 归一化
        max_score = max(s for _, s in self.category_rank) if self.category_rank else 1
        for cat, score in self.category_rank:
            if cat == category:
                return min(score / max(max_score, 1), 1.0)
        return 0.3

    def get_insights(self, limit: int = 10) -> List[EvolutionInsight]:
        """生成系统洞察"""
        insights = []

        # 渠道效果洞察
        if self.channel_performance:
            best_c = self.get_best_channel()
            total_replies = sum(p['reply'] for p in self.channel_performance.values())
            insights.append(EvolutionInsight(
                category='运营',
                metric='最佳触达渠道',
                value=0,
                trend='stable',
                confidence=min(total_replies / 50, 1.0),
                sample_size=total_replies,
                recommendation=f'优先使用 {best_c} 触达客户，回复率最高'
            ))

        # 品类机会洞察
        if self.category_rank[:3]:
            top3 = [c for c, _ in self.category_rank[:3]]
            insights.append(EvolutionInsight(
                category='品类',
                metric='高成交品类',
                value=0,
                trend='up',
                confidence=0.7,
                sample_size=sum(self.match_success_counter.values()),
                recommendation=f'TOP 3 成交品类: {", ".join(top3)}，优先推送'
            ))

        # 采购商国家洞察
        if self.buyer_country_success:
            top_country = self.buyer_country_success.most_common(1)
            if top_country:
                country, count = top_country[0]
                insights.append(EvolutionInsight(
                    category='市场',
                    metric='高成交市场',
                    value=count,
                    trend='stable',
                    confidence=0.6,
                    sample_size=sum(self.buyer_country_success.values()),
                    recommendation=f'{country} 采购商成交率最高({count}次)，重点开发'
                ))

        # 评分模型校准
        s_total = self.tier_accuracy['S']['total']
        if s_total >= 5:
            s_rate = self.tier_accuracy['S']['converted'] / s_total
            insights.append(EvolutionInsight(
                category='模型',
                metric='S级客户转化率',
                value=s_rate * 100,
                trend='stable',
                confidence=min(s_total / 30, 1.0),
                sample_size=s_total,
                recommendation=f'S级客户实际转化率 {s_rate*100:.1f}%，建议{"提高" if s_rate > 0.05 else "大幅提高"}S级标准'
            ))

        return insights[:limit]

    def get_scoring_weights(self) -> dict:
        """获取当前评分权重"""
        return self.scoring_weights.copy()

    def to_summary(self) -> dict:
        """系统摘要"""
        total_events = len(self.events)
        total_deals = sum(self.match_success_counter.values())
        total_replies = sum(p['reply'] for p in self.channel_performance.values())
        total_sends = sum(p['send'] for p in self.channel_performance.values())
        return {
            'total_events': total_events,
            'total_deals': total_deals,
            'total_outreach_sent': total_sends,
            'total_replies': total_replies,
            'reply_rate': f"{(total_replies/max(total_sends,1))*100:.1f}%",
            'best_channel': self.get_best_channel(),
            'top_categories': [c for c, _ in self.category_rank[:5]],
            'scoring_weights': self.scoring_weights,
            'insights': [str(i.recommendation) for i in self.get_insights()],
            'last_updated': datetime.datetime.now().isoformat(),
        }

    def save(self):
        data = {
            'events_count': len(self.events),
            'match_success': dict(self.match_success_counter),
            'channel_performance': dict(self.channel_performance),
            'tier_accuracy': self.tier_accuracy,
            'buyer_country_success': dict(self.buyer_country_success),
            'scoring_weights': self.scoring_weights,
            'category_rank': self.category_rank[:20],
            'saved_at': datetime.datetime.now().isoformat(),
        }
        os.makedirs(os.path.dirname(self.save_path) if os.path.dirname(self.save_path) else '.', exist_ok=True)
        with open(self.save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        if not os.path.exists(self.save_path):
            return
        try:
            with open(self.save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.match_success_counter = Counter(data.get('match_success', {}))
            self.channel_performance = defaultdict(
                lambda: {'send': 0, 'reply': 0, 'fail': 0},
                data.get('channel_performance', {})
            )
            self.tier_accuracy = data.get('tier_accuracy', self.tier_accuracy)
            self.buyer_country_success = Counter(data.get('buyer_country_success', {}))
            self.scoring_weights = data.get('scoring_weights', self.scoring_weights)
            self.category_rank = data.get('category_rank', [])
        except Exception as e:
            print(f"加载进化数据失败: {e}")


# 全局单例
_evolution_engine = None


def get_evolution_engine(save_path='evolution_data.json') -> EvolutionEngine:
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = EvolutionEngine(save_path)
    return _evolution_engine
