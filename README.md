# Vitala — AI Nutrition Companion（你的个性化 AI 营养管家）

> **Vitala**：一个"真正像 App"的个性化营养助手。
> 真实账号体系 · 中英双语 · 三套主题 · 首次引导 · 动态用户画像 · RAG 智能问答

---

## 一键开始（Windows）

1. 双击 **`启动营养助手.bat`**
2. 浏览器会自动打开 `http://localhost:8001`
3. 注册一个自己的账号（邮箱或手机号 + 用户名 + 密码 + 头像）
4. 看完引导动画 → 填写（或跳过）个人资料 → 进入主界面

> 也可在命令行运行：`venv\Scripts\python.exe run.py`

## 发给别人打开（公网链接）

1. 双击 **`一键公网分享.bat`**（首次会自动下载 cloudflared，约 40MB）
2. 窗口里出现 `https://xxxx.trycloudflare.com` 后，把这条链接发给任何人
3. 对方**不用安装任何东西**，浏览器打开即可注册使用
4. 手机、电脑都能打开；**可安装到桌面/主屏幕**（PWA，像 App 一样全屏使用）

> 说明：cloudflared 快速隧道无需注册账号；本窗口保持运行链接才有效。
> 局域网内也可直接访问 `http://你的IP:8001`。

## 新版本亮点（v2.0）

| 功能 | 说明 |
| --- | --- |
| 🌍 中英双语 | 顶栏/设置里一键切换，立即生效 |
| 🎨 三套主题 | 简约浅色 / 元气彩色 / 深邃暗黑，随个人账号保存 |
| 🔐 真实账号 | SQLite 存用户，注册/登录/会话/改密，每个人数据完全隔离 |
| 👤 头像与资料 | 预设头像/上传图片/首字母，个人数据**全部可编辑** |
| ✨ 首次引导 | 动态轮播介绍 → 分步资料问卷（性别/年龄/身高/体重/体脂/运动/饮食/饮水/睡眠/健康…每步可跳过） |
| 🏠 今日首页 | 热量与三大营养素进度、喝水打卡、记餐、记运动，实时保存 |
| 💬 AI 对话 | 基于你的画像回答并标注参考来源（需要配置大模型 Key） |
| 🧭 发现 | 精选食谱与营养知识浏览，一键"让 AI 展开讲讲" |
| 📱 PWA | 支持安装到桌面/手机，像 App 一样使用 |

## 常用页面入口

- **今日**：喝水 +250ml、记一餐（早/午/晚/加餐 + 热量营养）、记运动、撤销
- **AI 对话**：输入营养问题；回答下方显示参考来源
- **发现**：浏览 `data/raw/recipes.json` 菜谱与 `data/knowledge/*.md` 知识
- **我的**：分区块编辑全部个人数据（基本/身体/饮食/生活/健康），右上显示档案完成度
- **设置**：语言、主题、昵称、邮箱/手机号、修改密码、退出登录、安装应用

## 账号与数据

- 用户数据保存在 `data/app.db`（SQLite：users / sessions 两张表，密码 PBKDF2 加盐哈希）
- 首次启动自动建库；删除该文件即"清空所有用户"
- 头像：预设 emoji / 本地上传（以 dataURL 存库）/ 昵称首字母

## 项目结构

```
nutri_assistant/
├── run.py / *.bat          # 启动入口与公网分享
├── src/
│   ├── api.py              # FastAPI：账户/资料/记录/对话/目录 全套接口
│   ├── accounts.py         # 注册登录、密码哈希、会话、资料读写
│   ├── rag_service.py      # RAG 编排（索引复用、断网降级 BM25、画像注入）
│   ├── generator.py        # LLM 生成（支持用户画像上下文）
│   ├── retriever.py        # 向量 + BM25 混合检索
│   └── user_profile.py     # 营养目标计算（BMR/TDEE/三大营养素）
├── static/                 # 全新前端（无框架单页应用）
│   ├── index.html
│   ├── css/app.css         # 设计系统 + 三套主题
│   ├── js/i18n.js          # 中英文案
│   ├── js/app.js           # 页面与交互
│   ├── manifest.webmanifest / sw.js / icons/   # PWA
├── data/                   # 菜谱、知识库、user_profiles 模板、app.db
└── docs/                   # 课程文档
```

## 配置

复制 `.env.example` 为 `.env` 并填入：

```
SILICONFLOW_API_KEY=sk-xxxx        # 大模型 + Embedding（SiliconFlow）
```

- 没配 Key：启动更快；AI 对话会退回"知识库检索模式"（BM25 本地可用，离线也能聊）
- 配了 Key：对话更完整，且会结合你的用户画像个性化回答

其他可选环境变量：`EMBEDDING_MODEL`、`LLM_BASE_URL`、`VITALA_PORT`、`FORCE_REBUILD=1`（重建向量索引）。

## 常见问题

- **对话提示服务未就绪**：首次启动要构建/加载向量索引，稍等片刻再刷新。
- **想清空重来**：删除 `data/app.db` 与 `chroma_db` 后重启。
- **换端口**：设置环境变量 `VITALA_PORT=9000` 或直接改 `run.py` / `main.py`。
---

## 部署到云端（变成“一个网址所有人都能登”）

本地电脑只能自己看；要让**任何人**像豆包/DeepSeek 一样打开网址就能注册登录，需要把项目放到云端。项目已准备好 Docker / Render 配置：

- `Dockerfile`：任意支持 Docker 的平台通用
- `render.yaml`：Render 一键蓝图
- `Procfile`：Heroku/Railway 等平台通用

### 方式 A：Render（国外、上手最快）
1. 把本项目推到 GitHub 仓库
2. 注册 render.com → New + Blueprint → 选择本仓库
3. 环境变量填 `SILICONFLOW_API_KEY`
4. 部署完成后获得固定网址 `https://vitala-xxx.onrender.com`

> 免费版会在一段时间无访问后休眠，下次访问会自动唤醒（约等几十秒）；磁盘数据在重启时可能被重置，建议正式长期使用用付费实例或国内云。

### 方式 B：国内云服务器（最稳，推荐正式使用）
阿里云 / 腾讯云学生机：
1. 购买一台 Linux 云主机（有固定公网 IP）
2. 上传本项目，安装 Docker 后执行：
   ```bash
   docker build -t vitala .
   docker run -d -p 80:8000 -e SILICONFLOW_API_KEY=sk-xxx vitala
   ```
3. 浏览器访问 `http://你的公网IP`，所有人即可注册使用

### 方式 C：先临时演示
保持本机运行，双击 `一键公网分享.bat`，把 `https://xxxx.trycloudflare.com` 发给别人即可（电脑关机链接失效）。