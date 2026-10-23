# ⚡ YmlManage - Clash / Mihomo 母本节点维护与分发中心

> **解决代理配置维护痛点**：专门用于维护你的 Master Clash / Mihomo YAML 母本配置文件。支持一键抓取第三方订阅链接中的节点，原汁原味提取节点名称，在 Web 界面中勾选需要的节点和目标策略组，一键无损导入母本并分发给所有客户端！

---

## 🌟 核心特性

- 📂 **多母本管理**：
  - 支持直接输入现有订阅链接自动下载并保存为母本。
  - 支持上传本地 `.yaml` 配置文件，或一键生成内置常用标准策略组的模板母本。
  - 支持多套母本自由切换（如：`master.yaml`、`phone.yaml`、`router.yaml`）。
- 🔍 **智能提取与原名保留**：
  - 支持提取标准 Clash YAML 订阅、Base64 订阅及 `vmess://`、`vless://`、`ss://`、`trojan://`、`hysteria2://` 等多种单节点链接。
  - **100% 保持节点原名**，不擅自更改。
  - 自动与当前母本比对已有状态（🟢 待导入新节点 / 🟡 母本已存在）。
  - 支持按节点名或协议快速搜索，支持【全选】、【取消】、【仅选新节点】。
- 🎯 **手动指定策略组（proxy-groups）智能注入**：
  - 导入节点时，系统自动读取母本中的所有策略组（如 `🔰 节点选择`、`⚡ 自动选择`、`🇭🇰 香港节点` 等）。
  - 用户可**手动勾选**要加入哪些策略组，一键批量关联，告别手动改 YAML 策略组列表。
  - 支持同名节点“覆盖配置”或“跳过”。
- 🛡️ **无损注入与快照备份**：
  - 基于 `ruamel.yaml` 引擎，**严格保留原母本中的注释、DNS、TUN、规则（rules）与字段顺序**。
  - 每次导入前自动生成带时间戳的 `.bak` 快照备份，支持在 Web 端一键回滚。
- 🚀 **自带客户端外部订阅分发**：
  - 工具内置 HTTP 订阅服务：`http://<IP>:<PORT>/sub/<profile_name>.yaml`。
  - 点击顶栏“复制客户端订阅直链”即可粘贴至 Clash Verge / Mihomo / 软路由客户端，全端自动同步。
- 🐳 **双运行模式与 Docker 安全隔离**：
  - 本地端（Windows/Mac/Linux 桌面）：一键直开，免密访问，开箱即用。
  - Docker 端（NAS/VPS/软路由）：默认强制开启网页访问密码防护。首次部署访问自动引导进入初始化界面设置访问密码，密码持久化存储于 `data/auth.json`。后续每次访问需密码解锁，有效防范公网未授权访问。

---

## 🚀 快速开始

### 方式一：本地 Python 启动（推荐日常使用）

1. **安装依赖**：
   ```bash
   pip install -r backend/requirements.txt
   ```
2. **启动服务**：
   - Windows 用户双击 `start.bat` 或运行：
     ```bash
     python run.py
     ```
3. 打开浏览器访问：`http://127.0.0.1:8080`

---

### 方式二：Docker / Docker Compose 部署（适合 NAS / VPS）

使用提供的 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  yml-manage:
    image: yml-manage:latest
    build: .
    container_name: yml-manage
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - RUN_ENV=docker # 启用 Docker 运行模式（默认强制开启网页访问密码保护）
      - DATA_DIR=/app/data
      # 可选：如果希望订阅链接加密码保护，取消下面注释
      # - SUB_TOKEN=mysecret123
    volumes:
      - ./data:/app/data
```

启动命令：
```bash
docker compose up -d --build
```

---

## 📖 使用操作步骤

1. **选择或准备母本**：
   - 首次启动系统会自动为您生成一份包含常用策略组的标准模板 `master.yaml`。
   - 点击右上角 **【母本管理】**，可以输入您现有的订阅链接直接下载保存为母本，或者上传您本地的 YAML。
2. **提取外部订阅节点**：
   - 在输入框粘贴其他机场或订阅链接，点击 **【提取节点】**。
   - 也可在 **【常用订阅源】** 中保存常用订阅，以后下拉即可一键提取。
3. **勾选节点**：
   - 在表格中可看到提取出来的所有节点，未导入的会显示 🟢 待导入。
   - 点击【仅选新节点】或按需勾选节点。
4. **选择策略组并导入**：
   - 点击 **【导入所选节点】**，弹出配置抽屉。
   - 手动勾选要加入的策略组（如 `🔰 节点选择`、`⚡ 自动选择`、`🇭🇰 香港节点` 等）。
   - 选择同名节点是否覆盖，点击 **【确认执行导入】**。
5. **在客户端配置订阅**：
   - 点击顶栏 **【复制客户端订阅直链】**。
   - 打开 Clash Verge、Mihomo 或手机客户端，新建订阅并粘贴该链接，开启定时自动刷新即可！

---

## 📁 目录结构

```
YmlManage/
├── backend/
│   ├── app/
│   │   ├── config.py             # 配置项 (路径、Token等)
│   │   ├── main.py               # FastAPI 启动入口与静态托管
│   │   ├── yaml_manager.py       # ruamel.yaml 无损注入与备份引擎
│   │   ├── sub_fetcher.py        # 订阅抓取与单节点协议解析
│   │   ├── routes/               # 路由模块 (profiles, sources, nodes, sub)
│   │   └── static/               # 前端打包后的生产静态文件
│   └── requirements.txt
├── frontend/                     # Vue 3 + Element Plus 前端源码
│   ├── src/
│   │   ├── App.vue               # 核心交互页面
│   │   ├── api/index.js          # 后端 API 请求封装
│   │   └── main.js
│   ├── package.json
│   └── vite.config.js
├── data/                         # 持久化数据目录 (可挂载到宿主机)
│   ├── profiles/                 # 存放各母本 .yaml 文件
│   ├── backups/                  # 历史快照备份
│   └── sources.json              # 保存的常用订阅源列表
├── Dockerfile                    # 多阶段构建 Docker 镜像
├── docker-compose.yml            # Docker Compose 编排文件
├── run.py                        # 本地启动入口
└── start.bat                     # Windows 双击启动批处理
```
