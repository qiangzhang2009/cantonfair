"""
数据加载与预处理层
支持本地文件 / Cloudflare R2 / AWS S3 云存储
"""
import os, re, pickle, json
import pandas as pd
import numpy as np
from collections import Counter
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 延迟导入 cloud_storage，避免循环依赖
_storage_instance = None


def _get_storage():
    """获取云存储实例"""
    global _storage_instance
    if _storage_instance is None:
        from cloud_storage import CloudStorage
        _storage_instance = CloudStorage()
    return _storage_instance


def _get_data_file_path() -> str:
    """获取数据文件路径（优先环境变量 > 云存储 > 本地默认）"""
    # 1. 环境变量指定
    env_path = os.environ.get('DATA_FILE_PATH', '')
    if env_path and os.path.exists(env_path):
        return env_path

    # 2. 云存储下载
    env_r2 = os.environ.get('R2_ACCOUNT_ID', '')
    if env_r2:
        storage = _get_storage()
        path = storage.download()
        if path:
            return path

    # 3. 本地默认路径
    default_path = os.path.join(BASE_DIR, '..', '广交会数据综合整理_标准格式.xlsx')
    if os.path.exists(default_path):
        return default_path

    return env_path or default_path


# 初始化数据文件路径
DATA_FILE = _get_data_file_path()

# ======= 国家/地区标准化映射 =======
COUNTRY_NORMALIZE = {
    '中 国 香 港 .':'中国香港','中 国 香 港':'中国香港','香港':'中国香港',
    '中 国 澳 门 .':'中国澳门','中 国 澳 门':'中国澳门','澳门':'中国澳门',
    '中 国 台 湾 .':'中国台湾','中 国 台 湾':'中国台湾','台湾':'中国台湾',
    '台湾省':'中国台湾','中 国':'中国','中        国.':'中国',
    '美        国.':'美国','美 国':'美国',
    '英        国.':'英国','英 国':'英国',
    '德        国.':'德国','德 国':'德国',
    '法        国.':'法国','法 国':'法国',
    '意大利':'意大利','意   大   利.':'意大利','意 大 利':'意大利',
    '澳 大  利  亚.':'澳大利亚','澳大利亚':'澳大利亚',
    '荷        兰.':'荷兰','荷 兰':'荷兰',
    '日        本.':'日本','日本':'日本',
    '韩        国.':'韩国','韩国':'韩国',
    '印        度.':'印度','印度':'印度',
    '泰        国.':'泰国','泰国':'泰国',
    '西   班   牙.':'西班牙','西 班 牙':'西班牙',
    '挪        威.':'挪威','挪 威':'挪威',
    '瑞        典.':'瑞典','瑞典':'瑞典',
    '丹        麦.':'丹麦','丹麦':'丹麦',
    '芬        兰.':'芬兰','芬 兰':'芬兰',
    '俄   罗   斯.':'俄罗斯','俄 罗 斯':'俄罗斯','俄罗斯联邦':'俄罗斯',
    '奥   地   泊.':'奥地利','奥地利':'奥地利',
    '希        腊.':'希腊','希 腊':'希腊',
    '巴   拿   马.':'巴拿马','巴 拿 马':'巴拿马',
    '阿拉伯联合酋长国':'阿联酋','阿联酋':'阿联酋',
    '沙特阿拉伯':'沙特阿拉伯','伊朗':'伊朗',
    '冰岛':'欧洲','波斯尼亚黑塞哥维那共和国':'波斯尼亚和黑塞哥维那',
    '博茨瓦那':'博茨瓦纳',
}

CONTINENT_MAP = {
    '中国香港':'亚洲','中国澳门':'亚洲','中国台湾':'亚洲',
    '中国':'亚洲','日本':'亚洲','韩国':'亚洲','印度':'亚洲','印度尼西亚':'亚洲','马来西亚':'亚洲',
    '新加坡':'亚洲','泰国':'亚洲','越南':'亚洲','菲律宾':'亚洲',
    '美国':'北美洲','加拿大':'北美洲','墨西哥':'北美洲',
    '巴西':'南美洲','阿根廷':'南美洲','智利':'南美洲','哥伦比亚':'南美洲','秘鲁':'南美洲',
    '英国':'欧洲','德国':'欧洲','法国':'欧洲','意大利':'欧洲','荷兰':'欧洲',
    '比利时':'欧洲','西班牙':'欧洲','波兰':'欧洲','俄罗斯':'欧洲',
    '瑞典':'欧洲','丹麦':'欧洲','挪威':'欧洲','芬兰':'欧洲','奥地利':'欧洲','瑞士':'欧洲',
    '澳大利亚':'大洋洲','新西兰':'大洋洲',
    '埃及':'非洲','南非':'非洲','尼日利亚':'非洲','肯尼亚':'非洲','摩洛哥':'非洲',
}

MARKET_LEVEL_MAP = {'北美洲':'发达市场','欧洲':'发达市场','大洋洲':'发达市场'}

BUYER_TYPE_PATTERNS = {
    '跨国进口商': [r'IMPORT',r'TRADING',r'TRADE',r'GROUP',r'CORP',r'HOLDING'],
    '品牌代理商': [r'BRAND',r'AGENCY',r'DISTRIBUTOR'],
    '连锁商超采购': [r'SUPERMARKET',r'CHAIN',r'MART',r'RETAIL'],
    '工程采购方': [r'CONSTRUCTION',r'ENGINEERING',r'PROJECTS'],
    '跨境电商大卖': [r'AMAZON',r'EBAY',r'SHOPEE',r'LAZADA'],
    '区域批发商': [r'WHOLESALE',r'WHOLESALER'],
}

TRADE_MODE_PATTERNS = {
    'OEM/ODM代工': [r'OEM',r'ODM',r'MANUFACTUR'],
    '批量采购': [r'WHOLESALE',r'BULK'],
    '代理经销': [r'DISTRIBUTOR',r'AGENT'],
}

BUYER_CAT_KEYWORDS = {
    '个人护理用品': ['个人护理','电动牙刷','美容仪','按摩','护肤','体重秤'],
    '五金制品': ['工具','五金','扳手','螺丝刀','钳子','钻头','锯','锤子','焊枪','切割'],
    '体育及旅游休闲': ['体育','健身','瑜伽','户外','露营','登山','骑行','跑步机','球类'],
    '办公文具用品': ['文具','办公','笔','文件夹','胶带','印章'],
    '化工产品': ['化工','涂料','油漆','油墨','树脂','塑料','橡胶','颜料','染料'],
    '医疗器械及保健品': ['医疗','保健','医用','器械','轮椅','拐杖','口罩','眼镜','维生素'],
    '卫浴产品': ['卫浴','马桶','花洒','龙头','浴室柜','洗手盆','淋浴','浴缸'],
    '园林园艺产品': ['园林','园艺','花园','花盆','割草','绿篱','栅栏','草坪'],
    '大型机械及设备': ['大型机械','重型','工程','建筑机械','起重','挖掘','装载','混凝土'],
    '家具': ['家具','沙发','床','衣柜','橱柜','桌椅','定制家具'],
    '家居日用品': ['收纳','清洁','衣架','挂钩','梯子','雨具','整理箱'],
    '家居装饰品': ['装饰品','装饰画','摆件','干花','仿真花','烛台','香薰','挂钟','地毯','抱枕'],
    '家用纺织品': ['床品','被子','枕','毯','毛巾','家纺','面料'],
    '小型机械产品': ['机械','机床','通用机械','设备','切割','焊接','数控','激光','包装机'],
    '工程机械': ['施工','建筑机械','起重','挖掘','装载','路面','混凝土','盾构'],
    '摩托车产品': ['摩托','电动车','电动自行车','卡丁','沙滩车'],
    '服装': ['女装','男装','服装','裙子','裤子','衬衫','外套','大衣','毛衣','卫衣','T恤'],
    '汽车配件': ['汽车配件','汽配','轮胎','轮毂','发动机','底盘','刹车','车灯'],
    '浴室用品': ['防滑','浴帘','浴室垫','浴室收纳','地漏'],
    '照明灯具产品': ['照明','灯具','灯饰','LED','吊灯','吸顶灯','台灯','壁灯','落地灯','路灯','灯带'],
    '玩具产品': ['玩具','玩偶','积木','遥控','益智','毛绒','充气','电动玩具','模型'],
    '玻璃工艺品': ['玻璃','水晶','玻璃杯','玻璃瓶','玻璃器皿'],
    '电子消费品': ['手机','平板','耳机','音箱','智能手环','相机','游戏机','无人机','平衡车','数码'],
    '电子电气产品': ['电气','电线','电缆','开关','插座','LED','电机','发电机','电池','变压器','传感器'],
    '礼品及赠品': ['礼品','赠品','马克杯','钥匙扣','纪念品','奖杯','工艺礼品'],
    '箱包及皮具': ['包','箱','背包','旅行包','行李','皮具','钱包','书包'],
    '自行车产品': ['自行车','单车','公路车','山地车','折叠车','骑行装备'],
    '节日用品': ['圣诞','万圣节','复活节','春节','中秋','情人节','节日','节庆','派对','婚庆','气球','灯笼'],
    '车辆产品': ['汽车','轿车','客车','卡车','商用车','三轮车'],
    '钟表产品': ['手表','怀表','座钟','挂钟'],
    '陶瓷制品': ['陶瓷','瓷器','日用陶瓷','瓷砖','卫生陶瓷'],
    '鞋子': ['鞋','靴','拖鞋','凉鞋','运动鞋','休闲鞋','皮鞋','帆布鞋','童鞋'],
    '食品及保健品': ['食品','零食','饮料','茶叶','咖啡','保健品','营养品','糖果','饼干','坚果','调味品'],
    '家用电器': ['家电','电器','冰箱','空调','洗衣机','净化器','清扫','厨房电器','小家电'],
    '工具': ['工具','五金','扳手','螺丝刀','钳子','钻头','锯','锤子'],
    '建筑材料产品': ['建材','建筑材料','装饰材料','瓷砖','地板','门窗','石材','橱柜'],
    '餐厨餐具': ['餐具','餐厨','锅','刀叉','杯子','马克杯','玻璃杯','茶具','咖啡具','厨房','炊具'],
    '婴童产品': ['婴童','婴儿','儿童车','安全座椅','腰凳','背带','妈咪','孕妇','儿童餐椅','奶瓶'],
    '服装饰品配件': ['领带','围巾','丝巾','帽子','手套','腰带','袜子','发饰','服装辅料'],
}


def normalize_country(raw):
    if not raw or pd.isna(raw): return '其他国家'
    t = str(raw).strip().rstrip('.').replace(' ', '')
    t = re.sub(r'数据由.*$', '', t)
    if not t: return '其他国家'
    if t in COUNTRY_NORMALIZE: return COUNTRY_NORMALIZE[t]
    for k, v in COUNTRY_NORMALIZE.items():
        if k in t or t in k: return v
    if t in CONTINENT_MAP: return t
    for k, v in CONTINENT_MAP.items():
        if k in t or t in k: return k
    return t


def get_continent(country):
    return CONTINENT_MAP.get(str(country).strip(), '其他')


def get_market_level(continent):
    return MARKET_LEVEL_MAP.get(continent, '新兴市场')


def infer_buyer_type(company, country):
    text = f"{company} {country}".upper()
    for btype, patterns in BUYER_TYPE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE): return btype
    return ''


def infer_trade_mode(company):
    text = str(company).upper()
    for mode, patterns in TRADE_MODE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE): return mode
    return ''


def infer_intent(sessions):
    if not sessions: return '中意向（选品备货）'
    s = str(sessions)
    return '高意向（紧急找货）' if ';' in s else '中意向（选品备货）'


class DataLoader:
    def __init__(self, data_file=None):
        self.data_file = data_file or DATA_FILE
        self._buyers = None
        self._exhibitors = None
        self._stats = None

    def _resolve_path(self) -> str:
        """解析数据文件路径（支持云存储）"""
        if self.data_file and os.path.exists(self.data_file):
            return self.data_file
        # 尝试云存储
        if os.environ.get('R2_ACCOUNT_ID'):
            storage = _get_storage()
            path = storage.download()
            if path:
                self.data_file = path
                return path
        # 回退到默认路径
        default = os.path.join(BASE_DIR, '..', '广交会数据综合整理_标准格式.xlsx')
        if os.path.exists(default):
            self.data_file = default
            return default
        return self.data_file

    def load_buyers(self, force=False):
        if self._buyers is not None and not force:
            return self._buyers
        path = self._resolve_path()
        if not path or not os.path.exists(path):
            print(f"警告: 数据文件不存在: {path}")
            self._buyers = pd.DataFrame()
            return self._buyers
        try:
            df = pd.read_excel(path, sheet_name='采购商数据')
        except Exception as e:
            print(f"读取采购商数据失败: {e}")
            self._buyers = pd.DataFrame()
            return self._buyers

        df['国家_标准化'] = df['国家/地区'].apply(normalize_country)
        df['大洲'] = df['国家_标准化'].apply(get_continent)
        df['市场层级'] = df['大洲'].apply(get_market_level)

        if df['采购商类型'].isna().all():
            df['采购商类型_推断'] = df.apply(
                lambda r: infer_buyer_type(str(r.get('采购商企业全称','')), str(r.get('国家_标准化',''))), axis=1)
        else:
            df['采购商类型_推断'] = ''

        if df['合作模式'].isna().all():
            df['合作模式_推断'] = df['采购商企业全称'].apply(infer_trade_mode)
        else:
            df['合作模式_推断'] = ''

        btype = df['采购商类型'].fillna('')
        btype_inf = df['采购商类型_推断'].fillna('')
        df['采购商类型_final'] = btype.where(btype != '', btype_inf)

        df['合作意向_final'] = df['合作意向'].fillna('').where(
            df['合作意向'].fillna('') != '', df['参展届次'].apply(infer_intent))

        tmode = df['合作模式'].fillna('')
        tmode_inf = df['合作模式_推断'].fillna('')
        df['合作模式_final'] = tmode.where(tmode != '', tmode_inf)

        self._buyers = df
        return df

    def load_exhibitors(self, force=False):
        if self._exhibitors is not None and not force:
            return self._exhibitors
        path = self._resolve_path()
        if not path or not os.path.exists(path):
            print(f"警告: 数据文件不存在: {path}")
            self._exhibitors = pd.DataFrame()
            return self._exhibitors
        try:
            df = pd.read_excel(path, sheet_name='参展商数据')
        except Exception as e:
            print(f"读取参展商数据失败: {e}")
            self._exhibitors = pd.DataFrame()
            return self._exhibitors

        etype = df['企业类型*'].fillna('') if '企业类型*' in df.columns else ''
        df['企业类型_final'] = etype

        def get_ex_advantages(row):
            advs = []
            for col in ['海关认证','高新展商','品牌展商','创新奖','CF奖']:
                if str(row.get(col,'')).strip() == 'Y': advs.append(col)
            return '; '.join(advs) if advs else ''

        df['核心优势'] = df.apply(get_ex_advantages, axis=1)
        self._exhibitors = df
        return df

    def load_pairing_data(self):
        path = self._resolve_path()
        if not path or not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_excel(path, sheet_name='品类撮合配对表')
        except:
            return pd.DataFrame()

    def load_analysis_data(self):
        path = self._resolve_path()
        if not path or not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_excel(path, sheet_name='品类撮合分析')
        except:
            return pd.DataFrame()

    def load_country_stats(self):
        path = self._resolve_path()
        if not path or not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_excel(path, sheet_name='采购商来源分析')
        except:
            return pd.DataFrame()

    def load_high_value_exhibitors(self):
        path = self._resolve_path()
        if not path or not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_excel(path, sheet_name='高价值展商速查')
        except:
            return pd.DataFrame()

    def get_stats(self):
        if self._stats is not None: return self._stats
        buyers = self.load_buyers()
        exhibitors = self.load_exhibitors()
        if buyers.empty:
            self._stats = {
                'buyer_count': 0, 'exhibitor_count': 0,
                'buyer_with_email': 0, 'buyer_with_phone': 0,
                'buyer_with_wa': 0, 'high_intent_buyers': 0,
                'two_session_buyers': 0, 'exhibitors_two_session': 0,
                'continents': {},
            }
            return self._stats
        self._stats = {
            'buyer_count': len(buyers),
            'exhibitor_count': len(exhibitors),
            'buyer_with_email': int((buyers['联系方式-邮箱'].notna() & (buyers['联系方式-邮箱'] != '')).sum()),
            'buyer_with_phone': int((buyers['联系方式-电话'].notna() & (buyers['联系方式-电话'] != '')).sum()),
            'buyer_with_wa': int((buyers['联系方式-WhatsApp'].notna() & (buyers['联系方式-WhatsApp'] != '')).sum()),
            'high_intent_buyers': int((buyers['合作意向_final'].str.contains('高意向', na=False)).sum()),
            'two_session_buyers': int((buyers['参展届次'].str.contains(';', na=False)).sum()),
            'exhibitors_two_session': int((exhibitors['参展届次'].str.contains(';', na=False)).sum()),
            'continents': buyers['大洲'].value_counts().to_dict(),
        }
        return self._stats


_loader = None


def get_loader(data_file=None):
    global _loader
    if _loader is None:
        _loader = DataLoader(data_file)
    return _loader
