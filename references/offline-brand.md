# 知识库不可用时的内容页局部草稿

Skill 内置 `assets/brand/brand-baseline.json`、`assets/brand/logo-config.json`、SVG 与 PNG Logo。品牌配置只管蓝、红、深蓝科技风的颜色、字体、Logo 和固定品牌文案；`assets/layouts/offline-core.json` 独立管理 16:9 画布、Logo 锚点、轻量封面／封底位置及基础正文页面清单。这相当于“Brand 负责身份、Layout 负责页面结构”的分层；本地主题是新绘页面的离线底座，不是原稿对象换色清单。字体只记录名称，不分发字体文件；生成环境缺少指定字体时需改用配置的 fallback 并复核实际换行。

黑、白、浅灰、中灰、深灰与深底次要文字从所选主题的 `neutral` 读取，全部角色还须与 `brand-palette-lock.json` 完全一致。离线渲染器在写文件前检查配色锁，保存后固化页面及母版的颜色引用，再扫描 PPTX 页面、所用版式、母版和原生图表中的显式 RGB；出现锁定变量之外的颜色、变量与锁不一致或仍依赖母版颜色槽就拒绝交付。其他自由编排脚本也必须运行 `scripts/audit_new_drawn_palette.py --input <PPTX> --theme <主题> --report <报告>` 和 `scripts/audit_component_color_independence.py --input <PPTX> --report <报告>`，不因视觉上近似就允许新造灰阶。

离线模式默认采用**无阴影**的平面图形语言：卡片、流程框、指标框、分隔线、图标容器和标题装饰均不添加投影或内阴影。用留白、边框、色块和字号层级区分信息。`offline-core.json` 将 `visual_effects.shadows` 固定为 `none`；渲染脚本会清除新建图形继承的 PowerPoint 主题效果引用，并在保存后检查是否残留阴影。用户明确要求特定阴影效果时，再为该项目单独设计和验收，不改变此默认规则。

新绘正文页先在最底层放置锁定画布色的可编辑矩形，避免 PowerPoint 组装时丢失单页背景。蓝红简约随后按 `offline-core.json.content_atmosphere` 放置两枚可编辑的半透明椭圆，并以 220 pt 柔化边缘；知识库来源页不叠加。科技风的技能编排和自由编排正文固定为更深的 `#031634` 画布，卡片表面使用原 `#05193A` 保持层次，加载 `assets/layouts/tech-content-header.pptx` 的原生顶部图形组，标题保持可编辑且居中，右上角使用白色 Logo；不加弥散椭圆或简约横线。PowerPoint 组装后须确认画布和科技顶部图形仍在底层，标题及正文保持清晰。

Git 知识库获取或校验失败时，完整出稿停止。若用户只需正文局部草稿，可保留错误原因，按本次材料建立内容页计划，再用 `scripts/render_offline_brand.py` 输出基础可编辑 PPTX。命令：

```powershell
py -3 scripts/render_offline_brand.py --input <逐页计划.json> --out <结果.pptx> [--theme blue|red|deep-blue-tech]
```

输入结构：`{"theme":"blue|red|deep-blue-tech","complete_deck":false,"pages":[...]}`。每页须有 `title`；正文 `type` 可用 `bullets`、`cards`、`process`、`comparison`、`metrics` 与十种关系结构。`bullets` 支持 `balanced|compact|spacious|lead`，`metrics` 支持 `grid|hero|lead_support`，默认 `variant=auto`；主次变体用从 0 开始的 `featured_index`。`cover`、`directory`、`section`、`closing` 均被拒绝；完整演示稿也被拒绝，须恢复知识库后从源页制作。内容事实与数值只取用户材料，不把示例文本带入结果。脚本对超项数和长标题拒绝出稿，返回明确错误，需调整页计划再运行。

正文关系版式还支持 `assertion_evidence`、`priority_grid`、`evidence_matrix`、`problem_solution_outcome`、`layered_architecture`、`longform_metric`、`data_table`、`milestone_timeline`、`image_case`、`comparison_chart`。字段契约、适用关系和来源说明见[正文托底排版](body-fallback-layouts.md)。若未显式传 `type`，渲染器先识别 `categories+series` 的对比图，再识别 `series` 趋势图，随后识别主次、证据、问题、层级、长文、表格、时间轴和图文案例；均无时使用 `bullets`。数值、日期、图片和来源必须由材料提供，不能由版式规则补写。全部版式均遵守锁色、单 Logo、无阴影和可编辑性检查。

脚本会在每页放入本地 Logo：蓝色浅底使用原色，红色浅底使用黑色、深底使用白色，科技风深底使用白色；红色风格不允许蓝红彩色 Logo。文本与图形均可编辑，`.audit.json` 记录 `library_used=false`、`brand_profile`、`layout_profile`、自动补页、每页 Logo 数与可编辑文本对象数。交付前还须实际打开或渲染 PowerPoint，复核中文换行、Logo 避让、视觉节奏及事实。离线局部稿不宣称使用了模板封面、目录、章节页、封底、图库或源稿动效，状态保持 `draft_pending_review`。

如果用户指定必须使用某张远端模板页，报告中应说明该资产不可用并暂停该页出稿；知识库恢复后重新规划并选用原稿模板。不要悄悄使用不受校验的旧缓存冒充最新知识库。
