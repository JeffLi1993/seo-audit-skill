# seo-audit-skill

[English](README.md) · **中文**

可复用的单页面 SEO 审计与优化工具。给一个 URL，可输出结构化 HTML 审计报告；运行优化 CLI 后，还会生成可直接使用的 Title、Meta Description、H1、Canonical、JSON-LD、robots.txt、sitemap.xml 和内容优化简报。

基于 **Script + LLM 双层架构**：Python 脚本处理确定性检查（HTTP 状态码、XML 解析、字符串匹配），LLM 处理语义判断（关键词意图、内容质量、页面类型推断）。支持 Claude Code、Cursor 及任何兼容 SKILL.md 的 Agent 运行时。

## 最佳实践

1. 运行 `npx skills add JeffLi1993/seo-audit-skill`，然后发起审计，例如：`audit this page: https://example.com`。根据生成的报告（`reports/<hostname>-audit.html`），自行过一遍：哪些问题与你的业务目标相关、哪些可以忽略。
2. 需要直接生成优化产物时，运行优化 CLI：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --keyword "ai workflow automation" \
  --brand "Acme"
```

3. 如果你有本地 HTML 文件，可以让工具直接写入低风险基础优化：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --html-file ./index.html \
  --keyword "ai workflow automation" \
  --brand "Acme" \
  --apply
```

`--apply` 会更新 `<title>`、`<meta name="description">`、canonical 和首个 H1，并保存带时间戳的备份文件。

---

## 报告产出

每次审计生成独立 HTML 报告，保存至 `reports/<hostname>-audit.html`。

| 报告章节 | 内容 |
|---|---|
| **Audit Summary** | 一句话总结 + 关键问题 / 警告 / 通过项一览 |
| **Site Checks** | 可抓取性 · URL 规范化 · i18n · Schema · E-E-A-T |
| **Page Checks** | TDK · H1 · 标题层级 · 字数 · 内链 |
| **Priority Actions** | 影响最大的 3 项修复，按优先级排序 |
| **Insight Walkthrough** | 每个重要发现的 Evidence → Impact → Fix |

```
audit this page: https://openclaw.ai
→ ✅ Report saved → reports/openclaw-ai-audit.html
```

| 站点 | Audit Summary | Site Checks | Page Checks & insights |
|---|---|---|---|
| colaos.ai <br><small><code>reports/colaos-ai-audit.html</code></small> | <img src="assets/0-0.png" alt="审计摘要" width="240" /> | <img src="assets/0-1.png" alt="站点检查" width="240" /> | <img src="assets/0-2.png" alt="页面检查与洞察" width="240" /> |

---

## 直接 SEO 优化 CLI

`seo-audit/scripts/seo-optimize.py` 会把审计结果整理成优化包，默认保存到 `reports/<site>-seo-optimization.md`。

详细 Skill 文档：[seo-optimize README](seo-optimize/README.zh.md) · [English](seo-optimize/README.md)

每次运行优化器都会先写入一个必出的 HTML 审计报告，并通过本地报告服务访问：

```text
Audit report -> http://127.0.0.1:8766/moshuopc-com-audit.html
Comparison report -> http://127.0.0.1:8766/moshuopc-com-comparison.html
```

流程：先生成优化前审计报告，再生成或应用优化结果，最后生成优化前后对比报告。
对比报告沿用原审计报告样式，桌面端左侧展示完整原始审计，右侧展示完整 SEO 优化后目标审计。

![SEO 优化对比报告](assets/seo-optimize-comparison-split.png)

| 输出 | 内容 |
|---|---|
| 推荐 head 标签 | 优化后的 Title、Meta Description、Canonical、OG、Twitter Card |
| H1 | 与主关键词匹配的页面主题 H1 |
| JSON-LD | 按页面类型生成 homepage、article、product、FAQ 或通用 Schema 片段 |
| robots.txt / sitemap.xml | 基于目标 URL 生成抓取与站点地图片段 |
| 内容简报 | 推荐 H2、关键词位置、内链目标 |
| 优先级动作 | 根据审计结果生成 P1/P2/P3 修复清单 |

常用命令：

```bash
# Markdown 优化报告
python seo-audit/scripts/seo-optimize.py https://example.com -k "primary keyword" --brand "Brand"

# 输出 JSON，适合流水线集成
python seo-audit/scripts/seo-optimize.py https://example.com -k "primary keyword" --format json

# 修改本地 HTML 文件
python seo-audit/scripts/seo-optimize.py https://example.com --html-file ./index.html -k "primary keyword" --apply
```

建议显式提供 `--keyword` 和 `--brand`。缺省时，工具会根据 Title、H1 和域名推断。

报告相关选项：

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  -k "primary keyword" \
  --reports-dir reports \
  --report-port 8766
```

只有在只需要文件、不启动本地服务时，才使用 `--no-report-server`。

---

## 架构：Script + LLM 双层设计

```
URL
 │
 ▼
┌──────────────────────────────────────────────────┐
│  Layer 1 · Python 脚本                            │
│  确定性检查 → 结构化 JSON                          │
│                                                  │
│  check-site.py      robots.txt、sitemap (RFC 9309)│
│  check-page.py      H1 / title / meta / canonical│
│  check-schema.py    JSON-LD @type + 字段校验       │
│  fetch-page.py      原始 HTML + SSRF 防护          │
└───────────────────────┬──────────────────────────┘
                        │ JSON + llm_review_required 标志
                        ▼
┌──────────────────────────────────────────────────┐
│  Layer 2 · LLM Agent                             │
│  仅对标记字段进行语义判断                           │
│                                                  │
│  · 关键词意图对齐（H1 / Title）                     │
│  · Meta Description 质量与具体性评分                │
│  · 页面类型 → 期望 Schema @type 映射               │
│  · E-E-A-T 信任页面可达性（footer/nav 链接）         │
│  · 内容分析（字数、标题层级、内链）                   │
└───────────────────────┬──────────────────────────┘
                        │
                        ▼
              report-template.html
              → reports/<hostname>-audit.html
```

**为什么分两层？** 脚本处理 80% 的确定性检查——robots.txt 是否存在？Title 是否 55 个字符？LLM 处理 20% 需要理解力的判断——这个 H1 在语义上是否覆盖了"AI workflow automation"的搜索意图？`llm_review_required` 标志确保 LLM 仅在脚本明确无法判断时才介入——事实性检查不会产生幻觉，语义性检查不会有盲区。

---

## Skill 说明

| Skill | 层级 | 适用场景 |
|---|---|---|
| `seo-audit` | Basic | 默认入口 — 给一个 URL，输出结构化首轮检查 |
| `seo-optimize` | Optimization | 生成优化标签、Schema、robots/sitemap 片段、内容简报，并可选修改本地 HTML |
| `seo-audit-full` | Full | 深度审计：Core Web Vitals、内容质量评分、GSC 数据、竞品差距分析 |

---

## 审计覆盖范围

### 站点级检查

| 检查项 | 检查内容 | Basic | Full |
|---|---|:---:|:---:|
| robots.txt | RFC 9309 指令组解析、Allow/Disallow 逻辑、Googlebot 状态、Sitemap 指令 | ✅ | ✅ |
| sitemap.xml | 有效 XML、URL 数量、追踪 robots.txt 声明的 Sitemap 路径 | ✅ | ✅ |
| 404 处理 | 真 404 vs 软 404（200）vs 跳转首页（301） | ✅ | ✅ |
| URL 规范化 | HTTP→HTTPS 重定向、www 一致性、尾斜杠、Canonical 标签匹配 | ✅ | ✅ |
| i18n / hreflang | 互相引用对称、BCP 47 语言码、x-default、URL 路径结构 | ✅ | ✅ |
| Schema（JSON-LD） | @type 检测、必填字段校验、@graph 展平、类型冲突检查 | ✅ | ✅ |
| E-E-A-T 信任页面 | About / Contact / Privacy / Terms — 页面存在（HTTP 200）+ footer/nav 可达 | ✅ | ✅ |
| GSC 抓取状态 | 索引覆盖、抓取错误、被屏蔽资源 | — | ✅ |
| Core Web Vitals | CrUX 字段数据：LCP、CLS、INP | — | ✅ |

### 页面级检查

| 检查项 | 检查内容 | Basic | Full |
|---|---|:---:|:---:|
| URL Slug | 小写、连字符、含关键词、停用词 & 关键词堆砌检测 | ✅ | ✅ |
| Title 标题 | 50–60 字符、关键词位置、首页 vs 内页差异化规则 | ✅ | ✅ |
| Meta Description | 120–160 字符、关键词匹配、具体价值主张（非空泛描述） | ✅ | ✅ |
| H1 标签 | 唯一 H1、关键词匹配（full / partial / none）、语义意图复审 | ✅ | ✅ |
| Canonical 标签 | 自引用、与重定向后最终 URL 一致 | ✅ | ✅ |
| 图片 Alt 文本 | 所有 `<img>` 的 alt 属性检查、JS 渲染检测 | ✅ | ✅ |
| 字数统计 | 正文 ≥ 500 词、薄内容标记 | ✅ | ✅ |
| 关键词位置 | 主关键词出现在正文前 100 词内 | ✅ | ✅ |
| 标题层级结构 | H2 数量（目标 5–7）、H3/H2 比例、关键词在 H2 中的分布 | ✅ | ✅ |
| 内部链接 | 同源链接数（排除 nav/footer）、权重分配 | ✅ | ✅ |
| OG / 社交标签 | og:image、twitter:card、社交预览完整性 | — | ✅ |
| 内容质量 | E-E-A-T 深度、可读性、与竞品的具体程度对比 | — | ✅ |
| Robots Meta | noindex、nofollow、max-snippet 指令 | — | ✅ |

---

## 目录结构

```
seo-audit-skill/
├── seo-audit/
│   ├── SKILL.md                       # Skill 定义 + Agent 工作流
│   ├── references/REFERENCE.md        # 字段定义、边界情况
│   ├── assets/report-template.html    # HTML 报告模板
│   └── scripts/
│       ├── check-site.py              # robots.txt + sitemap → JSON
│       ├── check-page.py              # TDK + H1 + canonical + slug → JSON
│       ├── check-schema.py            # JSON-LD 提取 + 校验 → JSON
│       ├── fetch-page.py              # 原始 HTML 抓取，SSRF 防护
│       └── seo-optimize.py            # 优化包生成 + 本地 HTML 基础写入
├── seo-audit-full/
│   ├── SKILL.md
│   ├── references/REFERENCE.md
│   ├── assets/report-template.html
│   └── scripts/
│       └── check-social.py            # OG + Twitter Card 校验 → JSON
└── seo-optimize/
    ├── SKILL.md                       # 直接优化工作流
    ├── README.md                      # 详细英文说明
    └── README.zh.md                   # 详细中文说明
```

---

## 安装

**方式一：CLI 安装（推荐）**

```bash
npx skills add JeffLi1993/seo-audit-skill

# 安装指定 Skill
npx skills add JeffLi1993/seo-audit-skill --skill seo-audit
npx skills add JeffLi1993/seo-audit-skill --skill seo-optimize
npx skills add JeffLi1993/seo-audit-skill --skill seo-audit-full
```

**方式二：Claude Code Plugin**

```bash
/plugin marketplace add JeffLi1993/seo-audit-skill
/plugin install seo-audit-skill
```

## 使用

```
audit this page: https://example.com
```

```
deep audit: https://example.com
```

---

## 内置脚本

所有脚本均输出结构化 JSON 到 stdout。退出码 `0` = 通过/警告，`1` = 存在失败项。

| 脚本 | 功能 |
|---|---|
| `check-site.py` | robots.txt + sitemap — RFC 9309 指令组解析、Allow 覆盖、多 Sitemap 路径追踪 |
| `check-page.py` | H1 / title / meta / canonical / URL slug — 停用词感知的关键词匹配 |
| `check-schema.py` | JSON-LD 提取、@graph 展平、@type + 必填字段校验 |
| `fetch-page.py` | 原始 HTML 抓取 — SSRF 防护、重定向链追踪、Googlebot UA 选项 |
| `seo-optimize.py` | 生成优化标签、Schema、robots/sitemap 片段、内容简报，并可选修改本地 HTML |

`seo-optimize.py` 每次都会写入 `*-audit.html` 和 `*-comparison.html` 两个 HTML 报告，默认通过 `http://127.0.0.1:8766/` 访问。

**依赖：** `pip install requests`

---

## License

MIT
