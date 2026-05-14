# CantonFair Pro — 生产部署指南

本指南帮助您将 CantonFair Pro 部署到 Railway + Cloudflare R2。

---

## 第一步：准备 Cloudflare R2 存储桶

### 1.1 创建 R2 存储桶

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 **R2 Object Storage**
3. 点击 **Create bucket**
4. Bucket 名称：`cantonfair-data`（或其他名称）
5. 区域选择：自动（推荐）

### 1.2 获取 API Token

1. 进入 **R2 Manage API Token**
2. 点击 **Create API Token**
3. 选择 **Edit** 模板（或自定义权限）
4. 账户 ID：在 Cloudflare 右侧面板查看
5. 记录以下信息：
   - `Account ID`
   - `Access Key ID`
   - `Secret Access Key`

### 1.3 上传数据文件

```bash
# 安装 Cloudflare Wrangler CLI
npm install -g wrangler

# 登录
wrangler auth login

# 上传（拖拽到 R2 管理界面也可以）
wrangler r2 object put cantonfair-data/广交会数据综合整理_标准格式.xlsx \
  --file=广交会数据综合整理_标准格式.xlsx
```

> **提示**：首次上传约 27MB，R2 免费额度每月 10GB，完全够用。

---

## 第二步：部署到 Railway

### 2.1 连接 GitHub 仓库

1. 登录 [Railway](https://railway.app)
2. 点击 **New Project** → **Deploy from GitHub repo**
3. 选择包含 `cantonfair_system/` 的仓库
4. Railway 会自动检测 `Dockerfile` 和 `railway.toml`

### 2.2 配置环境变量

在 Railway 项目 **Variables** 中添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `R2_ACCOUNT_ID` | `xxxxxxxxxxxx` | Cloudflare Account ID |
| `R2_ACCESS_KEY_ID` | `xxxxxxxx` | R2 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | `xxxxxxxx` | R2 Secret Access Key |
| `R2_BUCKET_NAME` | `cantonfair-data` | 存储桶名称 |
| `R2_DATA_FILE_KEY` | `广交会数据综合整理_标准格式.xlsx` | 对象路径 |
| `SECRET_KEY` | `上一条命令生成的64位随机密钥` | Session 加密密钥 |
| `AUTH_USERS` | `admin:$2b$12$...` | 用户账户（bcrypt hash）|

生成 `SECRET_KEY`：
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

生成 `AUTH_USERS`：
```bash
# 先安装 bcrypt
pip install bcrypt

# 生成密码 hash（将 your_password 替换为实际密码）
python3 -c "import bcrypt; print('admin:' + bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())"
```

### 2.3 自定义域名（可选）

1. Railway 项目 → **Settings** → **Networking**
2. 点击 **Generate Domain** 获取免费域名
3. 或绑定自己的域名（Cloudflare Proxy 建议开启）

### 2.4 部署触发

推送到 `main` 分支会自动触发部署，或在 Railway 手动点击 **Deploy**。

---

## 第三步：验证部署

```bash
# 查看存储状态
cd cantonfair_system
python3 cloud_storage.py --status
```

访问部署后的 URL，使用配置的账号密码登录。

---

## 常见问题

### Q: 数据加载失败
```bash
# 手动测试云存储连接
python3 cloud_storage.py --force
```

### Q: 登录不进去
检查 `AUTH_USERS` 环境变量格式是否正确（bcrypt hash 不要有空格）。

### Q: 部署慢
Railway 首次构建需要拉取基础镜像约 200MB，后续构建会缓存。

---

## 架构概览

```
┌──────────────────┐    ┌─────────────────────┐
│   用户浏览器       │───▶│  Railway (Streamlit) │
│   (登录验证)       │    │  端口 8502           │
└──────────────────┘    └──────────┬──────────┘
                                   │
                         首次启动下载
                                   │
                    ┌──────────────▼──────────────┐
                    │   Cloudflare R2 (云存储)     │
                    │   27MB Excel 数据文件        │
                    │   免费额度: 10GB/月          │
                    └─────────────────────────────┘
```
