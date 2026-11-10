# Epoint Presentation

把材料整理成符合新点品牌风格、可继续编辑的企业演示文稿。先选 **蓝色系、红色系或科技风格**，再由 Agent 梳理内容与信息关系，优先试用知识库组件；正文不适配时使用技能内的排版规则，仍保持同一套色彩、字体和 Logo。

**当前技能版本：1.0.28。** [查看技能入口](SKILL.md) · [查看完整模板知识库](https://github.com/camillechi2018/Epoint-Presentaion-KnowledgeBase)

## 先看三种风格

| 页面 | 蓝色系 · 蓝白简约 | 红色系 · 红白简约 | 科技风格 · 深蓝科技 |
| --- | --- | --- | --- |
| 封面 | ![蓝色系 P001 封面样张](assets/style-previews/blue-cover-P001.png) | ![红色系封面样张](assets/style-kits/red/cover-supp-cover-red-06.png) | ![科技风格封面样张](assets/style-kits/deep-blue-tech/cover-cover-tech-001.png) |
| 目录 | ![蓝色系目录预览](assets/style-previews/blue.png) | ![红色系目录预览](assets/style-previews/red.png) | ![科技风格目录预览](assets/style-previews/tech.png) |
| 正文 | ![蓝色系流程正文样张](assets/style-kits/blue/process-content-blue-060.png) | ![红色系对比正文样张](assets/style-kits/red/comparison-content-blue-133.png) | ![科技风格并列正文样张](assets/style-kits/deep-blue-tech/parallel-content-tech-021.png) |

图片取自技能包内的模板样张，文字是演示内容，实际出稿会按用户材料替换。预览用于选择整稿视觉方向，不表示最终一定使用图中的页面。实际封面、目录、章节页和封底从适配的知识库模板或已校验的本地最小包中选择。

## 正文组件预览

每种风格各选取 **16 张已验收正文组件**，拼成一张预览图，展示流程、对比、时间线、指标、表格等不同信息结构。蓝红两组对应相同组件的不同色系；实际选版仍以当次知识库的验收状态、字段和内容容量为准。图片中的文字与数字来自模板示例，不作为出稿事实。[查看组件 ID、来源与知识库提交](assets/style-previews/component-gallery-sources.json)。

### 蓝色系 · 蓝白简约

![蓝色系 16 张正文组件拼图](assets/style-previews/component-gallery-blue-16.png)

### 红色系 · 红白简约

![红色系 16 张正文组件拼图](assets/style-previews/component-gallery-red-16.png)

### 科技风格 · 深蓝科技

![科技风格 16 张正文组件拼图](assets/style-previews/component-gallery-tech-16.png)

## 简要说明

把文档、旧 PPT 或一段汇报思路整理成可编辑的 PPTX 初稿。用户可先看预览，再选择蓝色系、红色系或科技风格。版式从数百页源模板中提炼，按当前验收状态匹配可用组件；正文没有合适模板时，继续使用技能内的排版规则。默认加入企业 Logo，文字和适用的原生图形可在 PowerPoint 中继续修改；图表等对象的可编辑范围取决于所选组件。

## 使用优势

- **品牌规范：** 每页默认放置独立 Logo。浅色背景按风格使用适合的彩色或单色版本，深色背景使用白色版本；Logo 的品牌颜色不跟随正文主题色任意改变。
- **字体统一：** 中文采用微软雅黑，英文和数字采用 Arial；正文、表格、图表及母版都纳入字体检查。跨设备打开仍需确认字体可用，并复核实际换行。
- **整稿协调：** 根据封面、目录、章节、流程、对比、数据等页面职责，以及内容关系和容量选择版式；封面配图优先匹配所选主题色。章节页在同一整稿中保持统一。
- **先规划再组装：** 先梳理每页讲什么、适合什么版式，再逐页填充和组装，方便发现内容与模板不匹配的问题。
- **交付前检查：** 逐页核对压字、溢出、图片裁切、Logo 位置和 PowerPoint 渲染；数据与案例以用户提供的材料为准，不编造。

## 适用场景

- 周报、月度汇报、项目方案、售前材料等常规企业演示文稿。
- 从一句话思路生成 PPT 大纲；补充事实材料后，再制作可自行编辑的 PPTX。
- 将旧 PPT 作为内容来源重新编排，并切换到所选风格；具体版式和动画需按新稿复核。

最省事的试用方式：提供一份现有材料或旧 PPT，先看逐页计划是否符合你的表达思路，再检查生成的初稿。欢迎反馈实际案例、问题与建议。

## 快速开始

将本仓库完整克隆到所用 Agent 的技能目录，确保 `SKILL.md`、`assets/`、`references/` 和 `scripts/` 都在同一目录。以 Codex 的用户技能目录为例：

```powershell
git clone https://github.com/camillechi2018/Epoint-Presentaion.git "$HOME/.codex/skills/epoint-presentation"
```

然后在支持技能的 Agent 中附上材料，例如：

> 调用 epoint-presentation，用这份报告制作一套可编辑 PPTX。先给我蓝色系、红色系、科技风格的预览供选择；保留材料中的事实和数字。

如果已指定风格，可直接说“用蓝色系制作”，不需要再次选择。完整模板知识库由 [`knowledge-base.json`](knowledge-base.json) 指向独立 Git 仓库；首次使用远端模板需要能够访问 GitHub。字体使用 Microsoft YaHei 和 Arial，实际文字换行仍需在生成环境中检查。

## 它怎样组织一份 PPT

1. **理解材料。** 先提炼结论、证据、信息关系和页次，不把模板示例文字当成业务事实。
2. **锁定风格。** 整稿使用所选色系、字体、Logo 和页面规则；红色系使用单色 Logo。
3. **优先匹配知识库。** 按页面职责、信息关系、字段和容量试填组件。封面、目录、章节页、封底必须使用合格的模板；同一整稿的章节页保持同一版式。
4. **补足正文。** 没有合适组件时，先使用技能内的正文排版规则；仍不适用时，在所选风格约束下自由编排，并记录页面来源。
5. **检查成稿。** 核对文字边界、字体、颜色、Logo、图片及实际 PowerPoint 渲染；保留需要人工审阅的状态。

详细规则见[选版与知识库契约](references/library-contract.md)、[正文托底排版](references/body-fallback-layouts.md)和[质量检查](references/source-and-qa.md)。

## 能力与边界

| 场景 | 当前处理方式 |
| --- | --- |
| 可编辑 PPTX | 保留可编辑文字和适用的原生图形；知识库组件按当前验收状态开放。 |
| 三种风格 | 技能自带颜色、字体、Logo 规则和预览；科技风格独立于简约蓝红版。 |
| 目录变项数 | 依据具体目录组件的已验证项数和文字容量选版。 |
| 知识库暂不可达 | 可检查已校验的本地结构页最小包；无合格结构页时停止完整出稿。仅制作正文局部草稿可使用离线品牌排版。 |
| HTML 与动效 | 按具体组件的独立验收状态判断，不能从静态 PPTX 可用推断其已可用。 |

技能默认添加 Logo，并锁定主题变量；具体页面仍须用本次材料试填。模板和品牌素材目前标记为 `draft_pending_review`，这是审阅状态，不是正式品牌授权或交付质量保证。

## 仓库结构

```text
Epoint-Presentaion/
├── SKILL.md                 Agent 的调用规则
├── knowledge-base.json      完整知识库的 Git 地址与本地回退配置
├── assets/
│   ├── brand/               Logo、颜色与字体变量
│   ├── style-kits/          蓝、红、科技三套风格资料
│   ├── style-previews/      三张风格预览
│   ├── layouts/             正文托底排版规则
│   └── minimal-template-pack/  离线结构页最小包
├── references/              按任务读取的细则
├── scripts/                 选版、填充、组装及审计工具
└── tests/                   局部回归测试
```

完整模板、组件目录和专项验收记录位于[独立知识库仓库](https://github.com/camillechi2018/Epoint-Presentaion-KnowledgeBase)，不随本技能仓库重复分发。历史本地备份 `assets/minimal-template-pack.previous/` 不进入 Git 仓库。

## 授权状态

本仓库代码及所含的新点品牌 Logo、原稿模板、图片等内容，其使用、复制、改编、再分发和商用授权由**国泰新点软件股份有限公司**管理。本仓库目前没有 `LICENSE` 文件，也未公开授予上述内容的再分发或商用许可；仓库公开可读不代表获得开放授权。对外复用前，请向国泰新点软件股份有限公司确认具体授权范围；涉及第三方素材时，还须取得相应权利人的许可。
