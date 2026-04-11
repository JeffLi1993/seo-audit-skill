# seo-audit-skill

[English](README.md) · **中文**

可复用的单页面 SEO 审计 Agent Skill。给一个 URL，输出结构化 HTML 审计报告，包含可执行的修复建议。

基于 **Script + LLM 双层架构**：Python 脚本处理确定性检查（HTTP 状态码、XML 解析、字符串匹配），LLM 处理语义判断（关键词意图、内容质量、页面类型推断）。支持 Claude Code、Cursor 及任何兼容 SKILL.md 的 Agent 运行时。

---

## 报告产出

每次审计生成独立 HTML 报告，保存至 `reports/<hostname>-audit.html`。

| 报告章节 | 内容 |
|---|---|
| **Audit Summary** | 一句话总结 + 关键问题 / 警告 / 通过项一览 |
| **Site Checks** | 可抓取性 · URL 规范化 · i18n · Schema · E-E-A-T |
| **Page Checks** | PageSpeed · TDK · H1 · 标题层级 · 字数 · 内链 |
| **Priority Actions** | 影响最大的 3 项修复，按优先级排序 |
| **Insight Walkthrough** | 每个重要发现的 Evidence → Impact → Fix |

```
audit this page: https://openclaw.ai
→ ✅ Report saved → reports/openclaw-ai-audit.html
```

**示例 — colaos.ai**（报告：`reports/colaos-ai-audit.html`）

| # | 对应区块 | 效果图 |
|---|----------|--------|
| 1 | **Audit Summary** | <img src="assets/0-0.png" alt="审计摘要" width="720" /> |
| 2 | **Site Checks** | <img src="assets/0-1.png" alt="站点检查" width="720" /> |
| 3 | **Page Checks & 洞察** | <img src="assets/0-2.png" alt="页面检查" width="720" /> |

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
│  check-pagespeed.py PSI API（移动端 + 桌面端）      │
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
| `seo-audit` | Basic | 默认入口 — 给一个 URL，20+ 项结构化检查 |
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
| PageSpeed Insights | Performance / Accessibility / Best Practices / SEO 评分（移动端 + 桌面端） | ✅ | ✅ |
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
│       ├── check-pagespeed.py         # PageSpeed Insights API → JSON
│       └── fetch-page.py              # 原始 HTML 抓取，SSRF 防护
└── seo-audit-full/
    ├── SKILL.md
    ├── references/REFERENCE.md
    └── assets/report-template.html
```

---

## 安装

**方式一：CLI 安装（推荐）**

```bash
npx skills add JeffLi1993/seo-audit-skill

# 安装指定 Skill
npx skills add JeffLi1993/seo-audit-skill --skill seo-audit
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
| `check-pagespeed.py` | PageSpeed Insights API 评分 — 移动端 + 桌面端，4 个类别 |
| `fetch-page.py` | 原始 HTML 抓取 — SSRF 防护、重定向链追踪、Googlebot UA 选项 |

**依赖：** `pip install requests`

---

## License

MIT
