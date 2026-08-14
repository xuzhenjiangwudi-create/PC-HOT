# PC HOT

PC 行业动态聚合 · 每日精选与硬件日报  
风格参考 [AIHOT](https://aihot.virxact.com/)

## 功能

- 每天自动从公开 RSS 源抓取 PC / 硬件相关新闻
- 生成带热榜 + 时间线的静态页面
- 通过 GitHub Actions 定时更新并推送到 GitHub Pages

## 快速开始（一次性设置）

### 1. 创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名建议：`pc-hot`（或任意名称）
3. 选择 Public
4. **不要**勾选 “Add a README”
5. 点击 Create repository

### 2. 上传本项目代码

在本地打开终端，进入本文件夹，执行（把 `你的用户名` 换成你的 GitHub 用户名）：

```bash
git init
git add .
git commit -m "init: PC HOT"
git branch -M main
git remote add origin https://github.com/你的用户名/pc-hot.git
git push -u origin main
```

### 3. 开启 GitHub Pages

1. 进入仓库 → **Settings** → 左侧 **Pages**
2. Source 选择 **Deploy from a branch**
3. Branch 选 `main`，文件夹选 `/ (root)`
4. 点击 Save

几分钟后，你的网站地址会是：

```
https://你的用户名.github.io/pc-hot/
```

### 4. 开启 Actions 权限（重要）

1. 仓库 → **Settings** → **Actions** → **General**
2. 找到 **Workflow permissions**
3. 选择 **Read and write permissions**
4. 勾选 **Allow GitHub Actions to create and approve pull requests**（可选）
5. 保存

### 5. 手动触发一次更新（测试）

1. 仓库 → **Actions** 标签
2. 左侧选择 **Update PC HOT Daily**
3. 右侧点击 **Run workflow** → Run workflow

运行成功后，`index.html` 会自动更新，网站内容也会刷新。

之后每天 UTC 01:00（北京时间约 09:00）会自动运行一次。

## 本地手动生成

```bash
pip install feedparser requests beautifulsoup4
python scripts/generate_news.py
```

然后用浏览器打开 `index.html` 预览。

## 自定义

- 修改 `scripts/generate_news.py` 里的 `RSS_SOURCES` 可以增减新闻源
- 修改 `KEYWORDS` 可以调整过滤规则
- 修改 `.github/workflows/update.yml` 可以改变更新频率（cron 表达式）

## 说明

- 当前热度是简单模拟数值，不是真实传播热度
- 「推荐理由」目前是固定模板，后续可接入大模型生成更好的总结
- 部分 RSS 源可能偶尔失效或被限制，脚本会尽量容错

## 后续可改进方向

1. 接入更多高质量源（IT之家、快科技、DIGITIMES 等）
2. 用 LLM 生成真正的「推荐理由」
3. 增加搜索、分类标签、历史归档
4. 真实热度计算（结合多源提及频次）

有问题欢迎提 Issue。
