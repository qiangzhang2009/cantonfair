"""
外呼管理与线索跟踪系统
"""
import json, os, datetime
from dataclasses import dataclass, asdict, field
from typing import List, Optional
from enum import Enum
import pandas as pd


class ContactStatus(Enum):
    NEW = "新线索"
    CONTACTED = "已联系"
    INTERESTED = "有意向"
    SAMPLE = "寄样中"
    NEGOTIATING = "洽谈中"
    ORDERED = "已下单"
    FOLLOW_UP = "跟进中"
    INVALID = "无效线索"
    BLACKLIST = "黑名单"


class OutreachRecord:
    """单次触达记录"""

    def __init__(self, contact_id: str, contact_type: str,
                 channel: str, outcome: str, notes: str = '',
                 follow_up_date: str = '', contact_person: str = ''):
        self.id = f"{contact_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.contact_id = contact_id
        self.contact_type = contact_type  # buyer / exhibitor
        self.channel = channel  # whatsapp/email/phone/linkedin/wechat
        self.outcome = outcome  # 接通/未接/拒绝/有意向/无需求
        self.notes = notes
        self.follow_up_date = follow_up_date
        self.contact_person = contact_person
        self.timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.responses = []

    def add_response(self, response: str):
        self.responses.append({
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'text': response
        })

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'contact_type': self.contact_type,
            'channel': self.channel,
            'outcome': self.outcome,
            'notes': self.notes,
            'follow_up_date': self.follow_up_date,
            'contact_person': self.contact_person,
            'timestamp': self.timestamp,
            'responses': self.responses
        }


class LeadTracking:
    """线索跟踪"""

    def __init__(self, contact_id: str, contact_name: str,
                 contact_type: str, country: str, phone: str = '',
                 email: str = '', whatsapp: str = '', category: str = '',
                 intent: str = '', score: float = 0, tier: str = 'C',
                 match_exhibitor: str = '', match_reason: str = ''):
        self.contact_id = contact_id
        self.contact_name = contact_name
        self.contact_type = contact_type
        self.country = country
        self.phone = phone
        self.email = email
        self.whatsapp = whatsapp
        self.category = category
        self.intent = intent
        self.score = score
        self.tier = tier
        self.status = ContactStatus.NEW.value
        self.match_exhibitor = match_exhibitor
        self.match_reason = match_reason
        self.outreach_history: List[OutreachRecord] = []
        self.created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.updated_at = self.created_at
        self.next_follow_up = ''
        self.order_value = 0  # 预估订单金额
        self.probability = 0.0  # 成交概率

    def add_outreach(self, record: OutreachRecord):
        self.outreach_history.append(record)
        self.updated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def update_status(self, new_status: str, notes: str = ''):
        self.status = new_status
        self.updated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if notes:
            if self.outreach_history:
                self.outreach_history[-1].notes = notes
            else:
                rec = OutreachRecord(self.contact_id, self.contact_type,
                                    'system', 'status_update', notes)
                self.outreach_history.append(rec)

    def to_dict(self):
        return {
            'contact_id': self.contact_id,
            'contact_name': self.contact_name,
            'contact_type': self.contact_type,
            'country': self.country,
            'phone': self.phone,
            'email': self.email,
            'whatsapp': self.whatsapp,
            'category': self.category,
            'intent': self.intent,
            'score': self.score,
            'tier': self.tier,
            'status': self.status,
            'match_exhibitor': self.match_exhibitor,
            'match_reason': self.match_reason,
            'outreach_count': len(self.outreach_history),
            'last_outreach': self.outreach_history[-1].timestamp if self.outreach_history else '',
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'next_follow_up': self.next_follow_up,
            'order_value': self.order_value,
            'probability': self.probability,
        }

    @classmethod
    def from_buyer_row(cls, row, match_exhibitor='', match_reason=''):
        return cls(
            contact_id=str(row.get('序号', row.name)),
            contact_name=str(row.get('采购商企业全称', '')),
            contact_type='buyer',
            country=str(row.get('国家/地区', '')),
            phone=str(row.get('联系方式-电话', '')),
            email=str(row.get('联系方式-邮箱', '')),
            whatsapp=str(row.get('联系方式-WhatsApp', '')),
            category=str(row.get('主营品类', '')),
            intent=str(row.get('合作意向_final', '')),
            score=float(row.get('综合评分', 0)),
            tier=str(row.get('客户等级', 'C')),
            match_exhibitor=match_exhibitor,
            match_reason=match_reason,
        )


class OutreachManager:
    """外呼管理系统"""

    def __init__(self, save_path='outreach_data.json'):
        self.save_path = save_path
        self.leads: dict = {}  # contact_id -> LeadTracking
        self.stats = {
            'total': 0, 'new': 0, 'contacted': 0, 'interested': 0,
            'sample': 0, 'negotiating': 0, 'ordered': 0,
            'invalid': 0, 'follow_up': 0
        }
        self.load()

    def add_lead(self, lead: LeadTracking):
        self.leads[lead.contact_id] = lead
        self.stats['total'] = len(self.leads)
        self.save()

    def add_leads_from_df(self, df, match_exhibitor_col='', match_reason_col=''):
        for _, row in df.iterrows():
            me = str(row.get(match_exhibitor_col, '')) if match_exhibitor_col else ''
            mr = str(row.get(match_reason_col, '')) if match_reason_col else ''
            lead = LeadTracking.from_buyer_row(row, me, mr)
            if lead.contact_id not in self.leads:
                self.leads[lead.contact_id] = lead
        self.stats['total'] = len(self.leads)
        self.save()

    def update_lead(self, contact_id: str, status: str, channel: str = '',
                    notes: str = '', outcome: str = '', follow_up_date: str = ''):
        if contact_id not in self.leads:
            return False
        lead = self.leads[contact_id]
        lead.update_status(status, notes)
        if channel:
            rec = OutreachRecord(contact_id, lead.contact_type, channel,
                                 outcome, notes, follow_up_date)
            lead.add_outreach(rec)
        self.save()
        return True

    def get_leads_by_tier(self, tier: str) -> List[LeadTracking]:
        return [l for l in self.leads.values() if l.tier == tier]

    def get_leads_by_status(self, status: str) -> List[LeadTracking]:
        return [l for l in self.leads.values() if l.status == status]

    def get_follow_up_leads(self) -> List[LeadTracking]:
        today = datetime.date.today().isoformat()
        return [l for l in self.leads.values()
                if l.next_follow_up and l.next_follow_up <= today
                and l.status not in (ContactStatus.ORDERED.value, ContactStatus.INVALID.value)]

    def recalc_stats(self):
        s = Counter(l.status for l in self.leads.values())
        self.stats = {
            'total': len(self.leads),
            'new': s.get(ContactStatus.NEW.value, 0),
            'contacted': s.get(ContactStatus.CONTACTED.value, 0),
            'interested': s.get(ContactStatus.INTERESTED.value, 0),
            'sample': s.get(ContactStatus.SAMPLE.value, 0),
            'negotiating': s.get(ContactStatus.NEGOTIATING.value, 0),
            'ordered': s.get(ContactStatus.ORDERED.value, 0),
            'invalid': s.get(ContactStatus.INVALID.value, 0),
            'follow_up': s.get(ContactStatus.FOLLOW_UP.value, 0),
        }
        return self.stats

    def to_dataframe(self) -> pd.DataFrame:
        records = [l.to_dict() for l in self.leads.values()]
        return pd.DataFrame(records)

    def save(self):
        data = {
            'leads': {k: v.to_dict() for k, v in self.leads.items()},
            'stats': self.stats,
            'saved_at': datetime.datetime.now().isoformat()
        }
        with open(self.save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def load(self):
        if not os.path.exists(self.save_path):
            return
        try:
            with open(self.save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.leads = {}
            for k, v in data.get('leads', {}).items():
                lead = LeadTracking(
                    contact_id=v['contact_id'], contact_name=v['contact_name'],
                    contact_type=v['contact_type'], country=v['country'],
                    phone=v.get('phone',''), email=v.get('email',''),
                    whatsapp=v.get('whatsapp',''), category=v.get('category',''),
                    intent=v.get('intent',''), score=v.get('score', 0),
                    tier=v.get('tier','C'),
                    match_exhibitor=v.get('match_exhibitor',''),
                    match_reason=v.get('match_reason','')
                )
                lead.status = v.get('status', ContactStatus.NEW.value)
                lead.next_follow_up = v.get('next_follow_up','')
                lead.order_value = v.get('order_value', 0)
                lead.probability = v.get('probability', 0)
                lead.created_at = v.get('created_at','')
                lead.updated_at = v.get('updated_at','')
                self.leads[k] = lead
            self.stats = data.get('stats', {})
        except Exception as e:
            print(f"加载失败: {e}")


# ====== 触达话术模板 ======
OUTREACH_TEMPLATES = {
    'buyer_whatsapp': {
        'name': '采购商-WhatsApp话术',
        'channels': ['WhatsApp'],
        'template_cn': """Hi {contact_name},

I noticed your company attended the Canton Fair and is looking for {category} suppliers.

We have direct connections with top Chinese manufacturers in this category — competitive pricing, stable quality, and reliable delivery.

Would you be interested in receiving our supplier profiles and quotations?

Best regards""",
        'template_en': """Hi {contact_name},

I noticed your company attended the Canton Fair looking for {category}.

We represent verified Chinese factories with strong production capacity. Happy to share our catalog and competitive offers.

Are you currently sourcing new suppliers? I'd love to help.

Best""",
        'variables': ['contact_name', 'category', 'country'],
    },
    'buyer_email': {
        'name': '采购商-邮件话术',
        'channels': ['Email'],
        'template_cn': """Subject: Canton Fair {category} Suppliers - Verified Factories

Hi {contact_name},

Your company was registered at the Canton Fair as a {category} buyer.

We have direct relationships with top manufacturers in this category, offering:
- Competitive FOB pricing
- Strict quality control
- Flexible MOQ options
- Fast production lead time

I'd like to send you our product catalog. Would you be interested?

Best regards""",
        'template_en': """Subject: Direct Factory Access - {category} at Canton Fair Pricing

Dear {contact_name},

We noticed your company sourcing {category} at the Canton Fair.

We work directly with verified factories — no middleman, better prices.

Can I send you our latest catalog?

Best regards""",
        'variables': ['contact_name', 'category', 'country'],
    },
    'exhibitor_cold': {
        'name': '参展商-合作引流',
        'channels': ['WeChat', 'Phone'],
        'template_cn': """老板您好，

我这边有本届广交会精准海外采购商资源，覆盖您的 {category} 主营品类，目前已有 {count} 个对应采购商在找供应商。

可以帮您精准对接意向买家，全程居间服务，可按成交收佣金，不用您出任何前期费用。

感兴趣的话可以加微信聊聊，谢谢！""",
        'variables': ['category', 'count'],
    },
    'follow_up': {
        'name': '跟进话术',
        'channels': ['WhatsApp', 'Email', 'WeChat'],
        'template_cn': """Hi {contact_name},

Just following up on my previous message about {category}.

Have you had a chance to review our supplier profiles? Happy to answer any questions.

Looking forward to hearing from you!""",
        'variables': ['contact_name', 'category'],
    },
}


def generate_personalized_message(template_key: str, variables: dict, lang: str = 'cn') -> str:
    """生成个性化消息"""
    tmpl = OUTREACH_TEMPLATES.get(template_key, {})
    raw = tmpl.get(f'template_{lang}', tmpl.get(f'template_cn', ''))
    if not raw:
        return ''
    msg = raw
    for k, v in variables.items():
        msg = msg.replace(f'{{{k}}}', str(v))
    return msg
