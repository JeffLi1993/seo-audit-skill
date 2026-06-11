# seo-optimize

[English](README.md) · **中文**

`seo-optimize` 是 `seo-audit-skill` 的直接优化层。它复用审计脚本产生的结构化证据，然后生成可以直接落地的 SEO 优化产物：Title、Meta Description、H1、Canonical、OG/Twitter 标签、JSON-LD、robots.txt、sitemap.xml 和内容简报。

当用户希望“帮网站做 SEO 优化”、需要可复制的标签和 Schema、或希望对本地 HTML 做一轮安全基础写入时，使用这个 skill。

## 报告示意

优化器每次都会先生成审计报告，再生成优化前后对比报告。对比报告沿用原审计模板，桌面端左侧展示完整原始审计，右侧展示完整 SEO 优化后目标审计。

![SEO 优化对比报告](../assets/seo-optimize-comparison-split.png)

## 产出内容

| 输出 | 文件 / 位置 | 用途 |
|---|---|---|
| 优化前审计报告 | `reports/<site>-audit.html` | 优化前必出的基线报告 |
| SEO 优化包 | `reports/<site>-seo-optimization.md` 或 JSON | 可复制的推荐值和代码片段 |
| 对比报告 | `reports/<site>-comparison.html` | 完整原始审计 vs 优化后目标审计 |
| 可选本地 HTML 修改 | 通过 `--html-file` 传入的文件 | 对 title、meta description、canonical、首个 H1 做低风险写入 |
| 备份文件 | `<file>.<timestamp>.bak` | `--apply` 写入前自动保存 |

默认 HTML 报告通过本地服务访问：

```text
http://127.0.0.1:8766/
```

示例输出：

```text
Audit report -> http://127.0.0.1:8766/example-com-audit.html
SEO optimization kit saved -> /path/to/reports/example-com-seo-optimization.md
Comparison report -> http://127.0.0.1:8766/example-com-comparison.html
```

## 快速开始

在仓库根目录运行：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --keyword "ai workflow automation" \
  --brand "Acme"
```

输出 JSON，方便流水线使用：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --keyword "ai workflow automation" \
  --brand "Acme" \
  --format json
```

对本地 HTML 做安全基础写入：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --html-file ./index.html \
  --keyword "ai workflow automation" \
  --brand "Acme" \
  --apply
```

## 推荐 Agent 工作流

1. 获取并分析 URL 或本地 HTML 文件。
2. 从 Title、H1、页面正文和域名推断缺失的关键词、品牌和页面类型。
3. 运行站点、页面、Schema 和社交标签检查。
4. 写入必出的优化前 HTML 审计报告。
5. 生成 SEO 优化包。
6. 如果启用 `--apply`，只修改本地 HTML 的低风险字段，并自动保存备份。
7. 写入左右分屏对比报告。
8. 返回本地报告 URL 和优化包路径。

## 输入参数

| 输入 | 必填 | 说明 |
|---|---:|---|
| URL | 是，本地 HTML 分析场景可省略 | 用于 canonical、robots.txt、sitemap.xml 和报告命名 |
| `--keyword` | 推荐 | 用于 Title、Meta Description、H1、标题简报和关键词位置建议 |
| `--brand` | 推荐 | 用于标题、Schema、社交标签和 H1 |
| `--audience` | 可选 | 让 Meta Description 和内容简报更具体 |
| `--business-goal` | 可选 | 用于生成更明确的价值主张或转化目标 |
| `--page-type` | 可选 | `auto`、`homepage`、`article`、`product`、`faq`、`howto`、`generic` |
| `--html-file` | 可选 | 开启本地静态分析和可选本地写入 |

如果关键词或品牌缺省，脚本会自动推断。最终回复应说明哪些值来自推断。

## CLI 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `url` | 无 | 公开页面 URL |
| `--html-file` | 无 | 要分析或修改的本地 HTML 文件 |
| `--keyword`, `-k` | 自动推断 | 主关键词 |
| `--brand` | 自动推断 | 品牌或站点名称 |
| `--audience` | 空 | 目标受众 |
| `--business-goal` | 空 | 具体价值主张或转化目标 |
| `--page-type` | `auto` | 用于 Schema 和标题逻辑的页面类型 |
| `--timeout` | `20` | HTTP 超时时间，单位秒 |
| `--output`, `-o` | `reports/<site>-seo-optimization.md` | 优化包输出路径 |
| `--format` | `markdown` | `markdown` 或 `json` |
| `--reports-dir` | `reports` | HTML 报告输出目录 |
| `--report-port` | `8766` | 本地报告服务端口 |
| `--no-report-server` | 关闭 | 只写入报告文件，不启动本地服务 |
| `--apply` | 关闭 | 修改本地 HTML 字段，需要 `--html-file` |
| `--encoding` | `utf-8` | 本地 HTML 文件编码 |

## 优化包内容

Markdown 优化包包含：

- 按优先级排序的 P1/P2/P3 修复建议
- 优化后的 `<title>`
- 优化后的 `<meta name="description">`
- canonical 标签
- OG 和 Twitter Card 标签
- 推荐 H1
- JSON-LD Schema 片段
- robots.txt 片段
- sitemap.xml 片段
- 内容简报：推荐 H2、关键词位置、内链目标

## 对比报告

对比报告使用 `seo-audit` 原有的 HTML 模板生成，包含：

- 原始审计与优化后目标审计的汇总计数
- 左侧完整原始审计报告
- 右侧完整 SEO 优化后目标审计报告
- 页面字段级对比表
- 优化后的 head 标签片段
- JSON-LD 片段
- 原始与优化后的优先级动作
- 原始与优化后的洞察说明

优化后报告表示工具建议的目标状态。未使用 `--apply` 时，它不会改动线上站点。

## `--apply` 安全边界

`--apply` 只会修改通过 `--html-file` 传入的本地文件。

它可以更新：

- `<title>`
- `<meta name="description">`
- `<link rel="canonical">`
- 首个 `<h1>`

它不会修改框架组件、路由 metadata API、CMS 数据、图片 alt、正文内容、robots.txt、sitemap.xml 或生产部署。这些变更应根据优化包继续实施。

## 推荐值生成逻辑

优化器综合以下信息：

- HTML 解析得到的静态页面事实
- `check-page.py`、`check-site.py`、`check-schema.py`、`check-social.py` 的确定性审计 JSON
- 关键词、品牌、受众、业务目标和推断页面类型
- 保守的 Title / Meta 长度控制
- 按页面类型生成的 Schema 模板
- 面向标题层级、关键词位置、内链的内容简报规则

它不会编造客户、价格、认证、奖项、数据指标或集成能力等事实。

## 示例

首页：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  -k "ai workflow automation" \
  --brand "Acme" \
  --audience "operations teams" \
  --business-goal "automate recurring workflows"
```

文章页：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com/blog/seo-checklist \
  -k "seo checklist" \
  --brand "Acme" \
  --page-type article
```

本地 HTML 写入：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --html-file ./public/index.html \
  -k "ai workflow automation" \
  --brand "Acme" \
  --apply
```

## 测试

运行：

```bash
python3 -m unittest tests.test_seo_optimize -v
```

测试覆盖：

- 静态页面事实提取
- 可执行标签生成
- 本地 HTML 安全写入
- 必出的审计和对比报告渲染
- 左右分屏对比报告结构

## 维护说明

- 生成报告保存在 `reports/`，并已被 Git 忽略。
- 本地报告服务只绑定 `127.0.0.1`。
- 优化器依赖 `requests`，与现有审计脚本保持一致。
- 对比报告只向原审计模板注入对比页专用 CSS。
