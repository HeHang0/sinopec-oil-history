# 全国油价历史

把中国石化“历史油价”公开页面上的各省调价记录采集下来，按省份保存为 JSON，自动合并旧数据，并通过容器定时提交、推送到 Git 仓库。仓库里的 `site/` 是一套纯静态页面，由 GitHub Actions 直接发布到 GitHub Pages。

## 数据格式

每个省份一个文件，例如 `site/data/shanghai.json`：

```json
[
  {
    "date": "2026-10-16",
    "92": 8.53,
    "95": 8.99,
    "0": 8.2
  }
]
```

- `date` 是调价周期起始日。
- `92`、`95`、`98`、`0`、`-10`、`-20`、`-35` 对应汽油和柴油标号。
- 上游返回 `0.00` 表示该省不销售该油品，这类字段会被省略。
- 页面只展示实际存在的油品，因此各省列可能不同。
- 云南、四川这类多价区省份会在每条记录里增加 `zone` 字段，例如 `"zone": "一价区"`，前端用价区标签切换。

`site/data/index.json` 是省份索引，供页面选择省份、显示统计信息。

## 取数方式

历史页本身只调用 `GET /yjkqiantai/data/initOilPrice`，但省份保存在服务端 `SESSION` 中。采集器会：

1. 向 `/yjkqiantai/data/switchProvince` POST `{"provinceId":"31"}` 切换省份；
2. 保持同一个 Cookie 会话请求 `initOilPrice`；
3. 把返回的调价周期转换成上面的 JSON 结构；
4. 按 `date + zone` 与已有文件合并，新数据覆盖同期旧数据。

## 本地运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements.txt

# 只拉一次，写到当前目录的 site/data
python -m app.main --once --repo-dir .

# 本地预览
python -m http.server 8080 --directory site
```

只拉部分省份：

```bash
python -m app.main --once --repo-dir . --provinces 31,44,yunnan
```

运行测试：

```bash
python -m unittest discover -s tests -t .
```

## Docker

```bash
cp .env.example .env
# 编辑 .env，填入 GIT_REPO_URL 和私钥
docker compose up -d --build
docker logs -f sinopec-oil-history
```

镜像内置 `git`、`openssh-client` 和时区数据。容器启动后会立即拉取一次（`RUN_ON_START=true`），之后按 `FETCH_INTERVAL_DAYS` + `FETCH_HOUR`/`FETCH_MINUTE` 定时执行。

### 调度规则

- `FETCH_INTERVAL_DAYS=1`、`FETCH_HOUR=6`：每天 06:00 拉取。
- `FETCH_INTERVAL_DAYS=7`、`FETCH_HOUR=6`：每 7 天 06:00 拉取。
- 首次启动会立即执行一次，然后以这次执行日期为锚点排下一次。
- 进程重启后如果设置了 `RUN_ON_START=true`，会重新立即执行；状态文件在 `/state/fetch_state.json`。
- 时区由 `TZ` 控制，默认 `Asia/Shanghai`。

### 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GIT_REPO_URL` | 空 | SSH 仓库地址，如 `git@github.com:you/repo.git`；留空则只写本地文件 |
| `GIT_BRANCH` | `main` | 推送分支 |
| `GIT_SSH_PRIVATE_KEY` | 空 | 私钥内容，支持真实换行或 `\n` |
| `GIT_SSH_PRIVATE_KEY_B64` | 空 | 私钥的 base64，二选一 |
| `GIT_SSH_HOST` | `github.com` | 用于 `ssh-keyscan` 的主机 |
| `GIT_USER_NAME` / `GIT_USER_EMAIL` | bot | 提交身份 |
| `FETCH_INTERVAL_DAYS` | `1` | 间隔天数，最小 1 |
| `FETCH_HOUR` / `FETCH_MINUTE` | `6` / `0` | 每天几点执行 |
| `TZ` | `Asia/Shanghai` | 调度时区 |
| `RUN_ON_START` | `true` | 启动时是否立即拉取 |
| `RUN_ONCE` | `false` | 执行一次后退出 |
| `PROVINCES` | 空 | 逗号分隔的省份代码/名称/拼音；空表示全部 |
| `REQUEST_DELAY_SECONDS` | `0.4` | 省份之间的礼貌间隔 |
| `GIT_PUSH_RETRIES` | `3` | 推送失败重试次数 |
| `DRY_RUN` | `false` | 只写文件，不提交/推送 |
| `WORK_DIR` | `/repo` | 容器内仓库目录 |
| `STATE_DIR` | `/state` | 状态与 SSH 临时文件目录 |
| `DATA_SUBDIR` | `site/data` | 数据相对路径 |

## 配置 Git 推送

1. 生成专用部署密钥：

   ```bash
   ssh-keygen -t ed25519 -C "oil-price-bot" -f ~/.ssh/oil_price_deploy -N ""
   ```

2. 在 GitHub 仓库的 **Settings → Deploy keys** 添加 `oil_price_deploy.pub`，勾选 **Allow write access**。

3. 把私钥放进环境变量：

   ```bash
   export GIT_SSH_PRIVATE_KEY="$(cat ~/.ssh/oil_price_deploy)"
   ```

   或用 base64：

   ```bash
   base64 -w0 ~/.ssh/oil_price_deploy
   ```

   Windows PowerShell：

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:USERPROFILE\.ssh\oil_price_deploy"))
   ```

容器会把私钥写到 `/state/git_key`（权限 600），用 `ssh-keyscan` 写入 known_hosts，并在每次数据变化后 `git commit` + `git push`。

## 发布 GitHub Pages

1. 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
2. 推送仓库到 `main` 分支：

   ```bash
   git remote add origin git@github.com:<user>/<repo>.git
   git push -u origin main
   ```

3. `.github/workflows/pages.yml` 会在 `site/**` 变化时上传 `site/` 并发布。
4. 页面地址通常是 `https://<user>.github.io/<repo>/`。

容器推送新的 `site/data/*.json` 会触发 Pages 自动重建，因此不需要单独部署前端。

> 如果远端默认分支叫 `master`，请把 `.env` 里的 `GIT_BRANCH` 改成 `master`，
> 并把 `.github/workflows/pages.yml` 的 `branches` 一起改掉。

## 用 GitHub Actions 定时抓取（不需要自建服务）

`.github/workflows/fetch.yml` 提供了一条完全托管在 GitHub 上的采集链路：

1. 每天 06:00（北京时间）由 schedule 触发；
2. 在 Actions runner 里执行 `python -m app.main --once --repo-dir .`；
3. 用 `GITHUB_TOKEN` 把变化的 `site/` 提交回仓库；
4. 同一 workflow 直接部署 GitHub Pages。

不需要配置 SSH 私钥，也不需要运行 Docker 容器。也可以在 Actions 页面手动
`Run workflow` 立即执行一次。

默认 cron 是：

```yaml
- cron: "0 22 * * *"   # UTC 22:00 = 北京 06:00
```

- 想改成其他时间，修改这一行；cron 使用的是 UTC。
- 想每 N 天执行一次，可以改成 `0 22 */N * *`（按月内日期触发，跨月边界不严格）。
- GitHub 的定时任务可能有几分钟到更久的延迟；它保证的是“按计划触发”，不是精确到秒。
- 公开仓库连续 60 天没有任何活动时，GitHub 可能自动停用 schedule；重新提交或手动运行即可恢复。
- 使用 `GITHUB_TOKEN` 推送不会再次触发 `pages.yml`，所以 `fetch.yml` 自己完成了 Pages 部署。
- 如果仓库启用了分支保护，需要允许 GitHub Actions 向默认分支推送，或在分支规则里放行该 workflow。

## 镜像

本地构建：

```bash
docker build -t sinopec-oil-history:latest .
```

推送到 GitHub 后，`.github/workflows/docker.yml` 会构建 `linux/amd64` 和 `linux/arm64` 镜像并发布到：

```text
ghcr.io/<owner>/<repo>:latest
```

## 说明

- 仓库已包含 2026-10-17 拉取的 31 个省份、共 1115 条初始记录；之后由容器持续合并。
- 历史接口通常只返回最近约 24 个调价周期；本项目的合并逻辑会长期累积，已有日期不会被新请求截断。
- 页面与采集器都不依赖第三方 CDN；图表是手写 SVG。
- 上游页面结构或接口变化时，采集器会在日志中报告具体省份和错误。
