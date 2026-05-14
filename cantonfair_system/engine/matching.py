"""
智能匹配引擎
基于 TF-IDF 文本相似度 + 品类规则匹配 + 协同过滤
"""
import re, pickle, json, os
import numpy as np
import pandas as pd
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(BASE_DIR, 'models', 'match_cache.pkl')

# ====== 品类关键词体系 ======
BUYER_CAT_TO_EXHIBITORS = {
    '个人护理用品': ['个人护理','电动牙刷','美容仪','按摩','护肤','美甲','体重秤','洁面仪','吹风机','直发器'],
    '五金制品': ['工具','五金','扳手','螺丝刀','钳子','钻头','锯','锤子','焊枪','切割','扳钳','锉刀','内六角','电钻','冲击钻','角磨机'],
    '体育及旅游休闲': ['体育','健身','瑜伽','户外','露营','登山','骑行','泳具','跑步机','球类','瑜伽垫','哑铃','帐篷','睡袋','登山包'],
    '办公文具用品': ['文具','办公','笔','文件夹','胶带','印章','纸','簿','笔记本','白板','订书机','计算器','投影','文具套装'],
    '化工产品': ['化工','涂料','油漆','油墨','树脂','塑料','橡胶','颜料','染料','胶粘','化肥','农药','溶剂','固化剂'],
    '医疗器械及保健品': ['医疗','保健','医用','器械','轮椅','拐杖','口罩','防护','眼镜','维生素','体温计','血压计','创可贴','消毒液'],
    '卫浴产品': ['卫浴','马桶','花洒','龙头','浴室柜','洗手盆','淋浴','浴缸','地漏','浴室挂件','浴室柜','水龙头','淋浴房','浴霸'],
    '园林园艺产品': ['园林','园艺','花园','花盆','割草','绿篱','浇水','栅栏','草坪','园林工具','花架','防腐木','园艺剪刀','喷灌'],
    '大型机械及设备': ['大型机械','重型','工程','建筑机械','起重','挖掘','装载','混凝土','盾构','压路机','摊铺机','塔吊','升降机','龙门吊'],
    '家具': ['家具','沙发','床','衣柜','橱柜','桌椅','定制家具','办公家具','户外家具','儿童家具','板式家具','实木家具','软体家具'],
    '家居日用品': ['收纳','清洁','衣架','挂钩','梯子','雨具','整理箱','除湿','驱蚊','垃圾桶','拖把','扫帚','抹布','保鲜膜','保鲜袋'],
    '家居装饰品': ['装饰品','装饰画','摆件','干花','仿真花','烛台','香薰','挂钟','地毯','抱枕','墙贴','相框','花瓶','窗帘配件','灯罩'],
    '家用纺织品': ['床品','被子','枕','毯','毛巾','家纺','面料','法兰绒','四件套','被芯','枕芯','毛毯','浴巾','床笠','窗帘','沙发布'],
    '小型机械产品': ['机械','机床','通用机械','设备','切割','焊接','数控','激光','包装机','食品机械','纺织机械','通用设备','小型机械'],
    '工程机械': ['施工','建筑机械','起重','挖掘','装载','路面','混凝土','盾构','压路机','平地机','摊铺机','钻机','混凝土泵'],
    '摩托车产品': ['摩托','电动车','电动自行车','卡丁','沙滩车','摩托配件','头盔','骑行服','摩托艇','沙滩车'],
    '服装': ['女装','男装','服装','裙子','裤子','衬衫','外套','大衣','毛衣','卫衣','T恤','西装','针织','梭织','童装','运动服'],
    '汽车配件': ['汽车配件','汽配','轮胎','轮毂','发动机','底盘','刹车','车灯','车载','机油','火花塞','雨刮','座垫','脚垫','香水'],
    '浴室用品': ['防滑','浴帘','浴室垫','浴室收纳','地漏','防滑垫','浴室置物架','浴室镜','浴室挂件','马桶垫','浴球','搓澡巾'],
    '照明灯具产品': ['照明','灯具','灯饰','LED','吊灯','吸顶灯','台灯','壁灯','落地灯','路灯','灯带','灯泡','射灯','筒灯','灯箱'],
    '玩具产品': ['玩具','玩偶','积木','遥控','益智','毛绒','儿童骑','充气','户外玩具','电动玩具','模型','拼图','魔方','玩具枪','玩具车'],
    '玻璃工艺品': ['玻璃','水晶','玻璃杯','玻璃瓶','玻璃器皿','钢化玻璃','艺术玻璃','玻璃摆件','玻璃烛台','玻璃花瓶','玻璃展示柜'],
    '电子消费品': ['手机','平板','耳机','音箱','智能手环','相机','游戏机','无人机','平衡车','数码','智能手表','充电宝','数据线','蓝牙音箱'],
    '电子电气产品': ['电气','电线','电缆','开关','插座','LED','电机','发电机','电池','变压器','传感器','变频器','断路器','继电器','PLC'],
    '礼品及赠品': ['礼品','赠品','马克杯','钥匙扣','纪念品','奖杯','工艺礼品','文具礼品','皮具礼品','家居礼品','电子礼品','广告礼品'],
    '箱包及皮具': ['包','箱','背包','旅行包','行李','皮具','钱包','书包','帆布','手提包','单肩包','双肩包','电脑包','旅行箱','公文包'],
    '自行车产品': ['自行车','单车','公路车','山地车','折叠车','骑行装备','骑行服','骑行头盔','骑行手套','车灯','码表','打气筒','车锁'],
    '节日用品': ['圣诞','万圣节','复活节','春节','中秋','情人节','节日','节庆','派对','婚庆','气球','灯笼','春联','红包','彩带','圣诞装饰'],
    '车辆产品': ['汽车','轿车','客车','卡车','商用车','三轮车','车辆','电动车','校车','冷藏车','消防车','环卫车','房车'],
    '钟表产品': ['手表','怀表','座钟','挂钟','闹钟','电子表','机械表','石英表','智能手表','表带','钟表配件'],
    '陶瓷制品': ['陶瓷','瓷器','日用陶瓷','瓷砖','卫生陶瓷','陶瓷餐具','陶瓷摆件','陶瓷花瓶','瓷砖','马赛克','陶瓷模具'],
    '鞋子': ['鞋','靴','拖鞋','凉鞋','运动鞋','休闲鞋','皮鞋','帆布鞋','板鞋','童鞋','工作鞋','安全鞋','雪地靴','豆豆鞋'],
    '食品及保健品': ['食品','零食','饮料','茶叶','咖啡','保健品','营养品','糖果','饼干','坚果','调味品','蜂蜜','方便食品','罐头','冷冻食品'],
    '家用电器': ['家电','电器','冰箱','空调','洗衣机','净化器','清扫','厨房电器','小家电','电视','音响','微波炉','电饭煲','电磁炉','榨汁机'],
    '工具': ['工具','五金','扳手','螺丝刀','钳子','钻头','锯','锤子','焊枪','扳钳','锉刀','内六角','电钻','冲击钻','角磨机','工具箱'],
    '建筑材料产品': ['建材','建筑材料','装饰材料','瓷砖','地板','门窗','石材','橱柜','管材','保温材料','防水材料','油漆','涂料','五金件','玻璃幕墙'],
    '餐厨餐具': ['餐具','餐厨','锅','刀叉','杯子','马克杯','玻璃杯','茶具','咖啡具','厨房','炊具','炒锅','煎锅','汤锅','蒸锅','碗碟'],
    '婴童产品': ['婴童','婴儿','儿童车','安全座椅','腰凳','背带','妈咪','孕妇','儿童餐椅','奶瓶','纸尿裤','婴儿护肤','儿童玩具','儿童服装'],
    '服装饰品配件': ['领带','围巾','丝巾','帽子','手套','腰带','袜子','发饰','服装辅料','拉链','纽扣','花边','织带','烫画','刺绣'],
}


def build_exhibitor_text(row):
    """构建参展商文本向量"""
    parts = [
        str(row.get('展商名称', '')),
        str(row.get('主营产品', '')),
        str(row.get('省份', '')),
        str(row.get('企业类型', '')),
        str(row.get('贸易形式', '')),
        str(row.get('核心优势', '')),
    ]
    return ' '.join(p for p in parts if p and p != 'nan')


def build_buyer_text(row):
    """构建采购商文本向量"""
    parts = [
        str(row.get('采购商企业全称', '')),
        str(row.get('主营品类', '')),
        str(row.get('国家/地区', '')),
        str(row.get('采购商类型_final', '')),
    ]
    return ' '.join(p for p in parts if p and p != 'nan')


class SmartMatcher:
    """智能撮合匹配引擎"""

    def __init__(self):
        self.exhibitors_df = None
        self.buyers_df = None
        self.ex_vectorizer = TfidfVectorizer(max_features=3000, ngram_range=(1,2), min_df=1)
        self.buyer_vectorizer = TfidfVectorizer(max_features=3000, ngram_range=(1,2), min_df=1)
        self.ex_matrix = None
        self.buyer_matrix = None
        self._cat_cache = {}
        self.fitted = False

    def fit(self, exhibitors_df, buyers_df):
        """训练TF-IDF模型"""
        print("正在训练匹配模型...")
        self.exhibitors_df = exhibitors_df.copy()
        self.buyers_df = buyers_df.copy()

        # 构建文本
        ex_texts = [build_exhibitor_text(r) for _, r in self.exhibitors_df.iterrows()]
        buyer_texts = [build_buyer_text(r) for _, r in self.buyers_df.iterrows()]

        # TF-IDF向量化
        all_texts = ex_texts + buyer_texts
        tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1,2), min_df=1, max_df=0.9)
        tfidf.fit(all_texts)

        self.ex_matrix = tfidf.transform(ex_texts)
        self.buyer_matrix = tfidf.transform(buyer_texts)
        self.tfidf = tfidf
        self.fitted = True
        print(f"模型训练完成: {self.ex_matrix.shape[0]}展商 x {self.ex_matrix.shape[1]}词特征")
        return self

    def match_exhibitor_to_buyers(self, exhibitor_idx, top_k=20, min_score=0.1):
        """给定展商，匹配最相关的采购商"""
        if not self.fitted: raise RuntimeError("请先调用fit()")
        ex_vec = self.ex_matrix[exhibitor_idx]
        scores = cosine_similarity(ex_vec, self.buyer_matrix)[0]
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score: break
            buyer = self.buyers_df.iloc[idx]
            results.append({
                'buyer': buyer.to_dict(),
                'score': score,
                'exhibitor_idx': exhibitor_idx,
            })
        return results

    def match_buyer_to_exhibitors(self, buyer_idx, top_k=20, min_score=0.1):
        """给定采购商，匹配最相关的展商"""
        if not self.fitted: raise RuntimeError("请先调用fit()")
        buyer_vec = self.buyer_matrix[buyer_idx]
        scores = cosine_similarity(buyer_vec, self.ex_matrix)[0]
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score: break
            ex = self.exhibitors_df.iloc[idx]
            results.append({
                'exhibitor': ex.to_dict(),
                'score': score,
                'buyer_idx': buyer_idx,
            })
        return results

    def batch_match_by_category(self, category, top_ex=15, top_buyer=20):
        """按品类批量匹配"""
        # 找品类关键词
        keywords = BUYER_CAT_TO_EXHIBITORS.get(category, [])
        if not keywords:
            return pd.DataFrame()

        # 筛选展商
        mask_ex = pd.Series([False] * len(self.exhibitors_df))
        for kw in keywords:
            mask_ex |= self.exhibitors_df['主营产品'].fillna('').str.contains(kw, na=False)

        # 筛选采购商（按品类文件名匹配）
        mask_buyer = self.buyers_df['主营品类'].fillna('').str.contains(category[:4], na=False)

        matched_ex = self.exhibitors_df[mask_ex].head(top_ex)
        matched_buyer = self.buyers_df[mask_buyer].head(top_buyer)

        rows = []
        for _, ex in matched_ex.iterrows():
            tags = []
            for col in ['海关认证展商','高新展商','品牌展商','创新奖','CF奖']:
                if str(ex.get(col,'')).strip() == 'Y': tags.append(col.replace('展商',''))
            for _, buyer in matched_buyer.iterrows():
                rows.append({
                    '品类': category,
                    '展商名称': ex.get('展商名称',''),
                    '展商省份': ex.get('省份',''),
                    '展商城市': ex.get('城市',''),
                    '展商类型': ex.get('企业类型_final', ex.get('企业类型','')),
                    '展商贸易形式': str(ex.get('贸易形式','')).replace(',',';'),
                    '展商亮点标签': '; '.join(tags),
                    '展商主营产品': str(ex.get('主营产品',''))[:80],
                    '展商联系方式': ex.get('手机',''),
                    '采购商名称': buyer.get('采购商企业全称',''),
                    '采购商联系人': buyer.get('联系人',''),
                    '采购商国家': buyer.get('国家/地区',''),
                    '采购商大洲': buyer.get('大洲',''),
                    '采购商市场层级': buyer.get('市场层级',''),
                    '采购商类型': buyer.get('采购商类型_final',''),
                    '采购商合作意向': buyer.get('合作意向_final',''),
                    '采购商合作模式': buyer.get('合作模式_final',''),
                    '采购商电话': buyer.get('联系方式-电话',''),
                    '采购商邮箱': buyer.get('联系方式-邮箱',''),
                    '采购商WhatsApp': buyer.get('联系方式-WhatsApp',''),
                    '参展届次': buyer.get('参展届次',''),
                })
        return pd.DataFrame(rows)

    def get_ai_recommendation(self, query_text, query_type='buyer', top_k=10):
        """
        AI推荐：输入任意描述，智能匹配
        query_type: 'buyer' 找展商, 'exhibitor' 找采购商
        """
        if not self.fitted: raise RuntimeError("请先调用fit()")
        vec = self.tfidf.transform([query_text])
        if query_type == 'buyer':
            scores = cosine_similarity(vec, self.ex_matrix)[0]
            top_idx = np.argsort(scores)[::-1][:top_k]
            return [{'type':'展商', 'data': self.exhibitors_df.iloc[i].to_dict(), 'score': float(scores[i])} for i in top_idx]
        else:
            scores = cosine_similarity(vec, self.buyer_matrix)[0]
            top_idx = np.argsort(scores)[::-1][:top_k]
            return [{'type':'采购商', 'data': self.buyers_df.iloc[i].to_dict(), 'score': float(scores[i])} for i in top_idx]


# ====== 轻量级快速匹配（无ML依赖）======
class FastMatcher:
    """轻量级快速匹配，无需训练，直接基于规则+关键词打分"""

    def __init__(self):
        self.exhibitors = []
        self.buyers = []
        self.ex_texts = []
        self.buyer_texts = []

    def build_index(self, exhibitors_df, buyers_df):
        self.exhibitors = exhibitors_df.to_dict('records')
        self.buyers = buyers_df.to_dict('records')
        self.ex_texts = [build_exhibitor_text(r) for r in self.exhibitors]
        self.buyer_texts = [build_buyer_text(r) for r in self.buyers]
        print(f"索引构建: {len(self.exhibitors)}展商, {len(self.buyers)}采购商")

    def _score(self, text1, text2):
        """简单关键词重叠评分"""
        if not text1 or not text2: return 0
        t1 = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z]{2,}', text1.lower()))
        t2 = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z]{2,}', text2.lower()))
        if not t1 or not t2: return 0
        inter = len(t1 & t2)
        union = len(t1 | t2)
        return inter / union if union > 0 else 0

    def match_exhibitor(self, exhibitor_idx, top_k=20):
        target = self.ex_texts[exhibitor_idx]
        scores = [self._score(target, bt) for bt in self.buyer_texts]
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [{'buyer': self.buyers[i], 'score': float(scores[i])} for i in top_idx if scores[i] > 0]

    def match_buyer(self, buyer_idx, top_k=20):
        target = self.buyer_texts[buyer_idx]
        scores = [self._score(target, et) for et in self.ex_texts]
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [{'exhibitor': self.exhibitors[i], 'score': float(scores[i])} for i in top_idx if scores[i] > 0]

    def batch_match_by_category_static(self, exhibitors_df, buyers_df, category, top_ex=15, top_buyer=20):
        """按品类批量匹配（静态方法，直接传入df）"""
        keywords = BUYER_CAT_TO_EXHIBITORS.get(category, [])
        if not keywords:
            return pd.DataFrame()

        mask_ex = pd.Series([False] * len(exhibitors_df))
        for kw in keywords:
            mask_ex |= exhibitors_df['主营产品'].fillna('').str.contains(kw, na=False)

        mask_buyer = buyers_df['主营品类'].fillna('').str.contains(category[:4], na=False)

        matched_ex = exhibitors_df[mask_ex].head(top_ex)
        matched_buyer = buyers_df[mask_buyer].head(top_buyer)

        rows = []
        for _, ex in matched_ex.iterrows():
            tags = []
            for col in ['海关认证展商','高新展商','品牌展商','创新奖','CF奖']:
                if str(ex.get(col,'')).strip() == 'Y': tags.append(col.replace('展商',''))
            for _, buyer in matched_buyer.iterrows():
                rows.append({
                    '品类': category,
                    '展商名称': ex.get('展商名称',''),
                    '展商省份': ex.get('省份',''),
                    '展商城市': ex.get('城市',''),
                    '展商类型': ex.get('企业类型_final', ex.get('企业类型','')),
                    '展商贸易形式': str(ex.get('贸易形式','')).replace(',',';'),
                    '展商亮点标签': '; '.join(tags),
                    '展商主营产品': str(ex.get('主营产品',''))[:80],
                    '展商联系方式': ex.get('手机',''),
                    '采购商名称': buyer.get('采购商企业全称',''),
                    '采购商联系人': buyer.get('联系人',''),
                    '采购商国家': buyer.get('国家/地区',''),
                    '采购商大洲': buyer.get('大洲',''),
                    '采购商市场层级': buyer.get('市场层级',''),
                    '采购商类型': buyer.get('采购商类型_final',''),
                    '采购商合作意向': buyer.get('合作意向_final',''),
                    '采购商合作模式': buyer.get('合作模式_final',''),
                    '采购商电话': buyer.get('联系方式-电话',''),
                    '采购商邮箱': buyer.get('联系方式-邮箱',''),
                    '采购商WhatsApp': buyer.get('联系方式-WhatsApp',''),
                    '参展届次': buyer.get('参展届次',''),
                })
        return pd.DataFrame(rows)

    def ai_search(self, query, role='采购商', top_k=20):
        """自然语言搜索"""
        if role == '采购商':
            scores = [self._score(query, et) for et in self.ex_texts]
            top_idx = np.argsort(scores)[::-1][:top_k]
            return [{'type':'展商', 'data': self.exhibitors[i], 'score': float(scores[i])} for i in top_idx if scores[i] > 0]
        else:
            scores = [self._score(query, bt) for bt in self.buyer_texts]
            top_idx = np.argsort(scores)[::-1][:top_k]
            return [{'type':'采购商', 'data': self.buyers[i], 'score': float(scores[i])} for i in top_idx if scores[i] > 0]


# ====== 缓存管理器 ======
_cache = {}


def get_matcher(data_file=None):
    """获取单例Matcher实例（优先TF-IDF，回退到FastMatcher）"""
    key = data_file or 'default'
    if key not in _cache:
        try:
            from .data_loader import get_loader
            loader = get_loader(data_file)
            m = SmartMatcher()
            m.fit(loader.load_exhibitors(), loader.load_buyers())
        except Exception:
            from .data_loader import get_loader
            loader = get_loader(data_file)
            m = FastMatcher()
            m.build_index(loader.load_exhibitors(), loader.load_buyers())
        _cache[key] = m
    return _cache[key]


def get_fast_matcher(data_file=None):
    key = f'fast_{data_file or "default"}'
    if key not in _cache:
        from .data_loader import get_loader
        loader = get_loader(data_file)
        m = FastMatcher()
        m.build_index(loader.load_exhibitors(), loader.load_buyers())
        _cache[key] = m
    return _cache[key]
