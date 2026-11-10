---
name: epoint-presentation
description: 制作新点品牌可编辑 PPTX；Skill 自带 Logo、锁定色系、字体、三风格资料包和已校验结构页最小包。优先读取 Git 知识库，断网时使用本地已校验模板；正文可灵活编排。
metadata:
  version: "1.0.29"
---

# 新点企业演示文稿：新模板方案

## 跨平台统一入口

**整稿章节页版式锁定。** 同一份演示稿的所有 `section` 页使用同一个知识库 `layout_id`，只替换章节编号、标题与该版式允许的文字字段。第一张章节页实际填充成功后锁定其版式；后续章节页不得因换封面、随机种子、相邻去重或候选排序而改用另一款。若该版式容纳不了后续章节文字，应调整该章节文案或重新为整稿选择一款能容纳全部章节的版式；不得只把这一页换版。最终检查全部章节页的实际 `layout_id` 一致。

整套出稿先调用 `scripts/run_presentation.py --request <逐页请求.json> --out <预检报告.json> --plan-out <逐页计划.json>`；具备每页 `content` 时再加 `--execute-out <成稿.pptx>`。在无网络环境加 `--offline`。入口统一返回 `ready`、`partial_draft` 或 `blocked`、错误代码、知识库来源与提交号、三风格本地样本状态、逐页选版和未复用原因。只在 `ready` 时组装完整 PPTX；组装后核对结构页来源及颜色独立性。`library_used` 只按实际填充源模板页记录。

实际执行时，按已排序候选默认最多尝试 6 张单页模板，可用 `max_template_trials` 在 1–8 之间调整；字段缺失或容量不合格会记入 `trial_results` 并换下一张。候选均不合格时，正文记录 `NO_FIT_AFTER_TRIAL`，再按锁定风格编排；封面、目录、章节和封底则停止完整出稿。每页需在请求的 `content` 中提供真实可填字段；不把模板示例文字当作内容。

**正文匹配输入规则。** 正文页可用 `role=body`，并尽量给出 `information_relation`、真实项数与结构化 `content`。普通组件只要具备知识库 `matching_policy=structural`、`matching_activation=pilot_verified` 或 `structure_ready` 及完整 `matching_contract`，就可按图形关系跨原稿业务场景复用；原稿业务场景名不作为普通组件的拒绝条件；SMART、风险应对、四象限等 `semantic_strict` 组件仍须符合登记的不变量；指标和图表仍核对数据契约。通用 `items` 输入先按结构发现 `pilot_verified` 与 `structure_ready` 候选；目标字段缺口单独标记为 `awaiting_mapping`。执行器优先把真实标题、说明、摘要与有序条目映射到 `required_binding_paths`；材料确有额外分组、短标签、中心论点等信息时再显式提供。缺必填事实或文字超容量的候选继续试下一项，不得重复原稿示例、编造事实或把候选召回记为已使用。完整 `template_fields` 输入仍可作为兼容接口。固定图标只有明确承载审批等专用含义时才转为严格语义例外。实际可用组件以当次知识库清单、适配器及真实试填结果为准。`content-blue-142` 的通用四卡与真实中心标题现可自动映射；中心标题过宽时仍须合理换行并实际试填，单页映射不等于整稿视觉签收。缺标题、说明或超出容量即拒绝。环形箭头页 `content-blue-076` 仅用于材料确有四段闭环且中心标题与短标签均真实提供的情况，不把普通四项并列伪装为循环。旧请求中的 `layout_id=no-verified-template-for-this-relation` 仅是历史占位，入口会移除后重新检索。候选仍须通过原生项数、容量、字段试填；候选命中不代表组件可用。其他组件若缺少 `bindings.json` 所需字段，逐一试填并记录 `MISSING_REQUIRED_FIELD` 等原因，最终回到同风格技能排版。不得拆分或编造业务事实来提高模板复用率。用 `scripts/audit_matching.py --library <固定知识库> --request <逐页请求> --out <审计.json> --trial` 可复核正文尝试率、候选率与单页实填率；审计中的实填成功仍须经过整稿 PowerPoint 渲染和视觉复核。

完整字段结构调用的输入形态和缺字段回退见[普通正文组件结构调用](references/structural-template-fields.md)。

结构候选试填还须检查输入事实是否全部有对应槽位。若材料提供了条目正文，而候选仅能显示标题，记录 `INPUT_FACTS_UNMAPPED` 和具体字段，继续尝试其他候选；不得通过丢弃正文提高模板使用率。日程等嵌套组件仅在材料真实提供阶段与子任务时逐项映射，不能编造子任务填满槽位。

**容量与试填顺序。** 对当前知识库候选读取 `bindings.json` 的字符数、行数和视觉宽度硬限制、`layout_rules.json` 的专用标题/编号规则，以及 `review/body-longcopy-capacity.json` 的已测正文建议值和对应预检政策。建议值只用于风险排序，不覆盖原生绑定硬限制；单段自动换行的建议值不能冒充手动换行验收。字段完整且容量宽裕的候选优先试填；仅宽度超限而原槽允许两行时可插入不改变文字的一次换行，并在试填记录中标注视觉复核。超出硬限制或内容事实无法完整承载时换候选；最终以原生填充和 PowerPoint 渲染为准。逐候选记录容量文件与绑定哈希、风险、换行、试填结果及换版原因。

`assets/style-kits/` 保存蓝白简约、红白简约、深蓝科技三套本地规则及各 7 张不同页面职责的视觉样本。先通过 `scripts/read_style_kit.py --theme <blue|red|deep-blue-tech>` 获取清单，再实际打开相应预览图；读取路径本身不算已看过视觉。生成正文只允许同主题的锁定颜色、字体、Logo 与构图规则，不复制样本图里的业务文字。

**字体硬规则，适用于三种风格和所有出稿路径。**可编辑中文（标题、正文、图表标签、表格、页码及照片说明）统一使用 `Microsoft YaHei`；拉丁字母及数字统一使用 `Arial`。标题与正文只通过字号、字重和间距区分层级，不再用 `DengXian` 等其他中文正文字体。知识库模板填充页和 Skill 新绘页均须在单页保存后归一字体；最终组装后的 PPTX 再运行 `scripts/audit_fonts.py` 检查实际文字的中文／拉丁字体，失败则不得交付。Logo、图片内文字和专用图标字体保留原素材，不按正文改字；统一字体后仍须重新渲染并检查换行与文字边界。

正文编排读取 `assets/style-kits/composition-rules.json`。这份规则从已验收知识库正文页归纳并附来源 ID：先辨认并列、流程、对比、数据、时间线或主次关系，再按文字密度选择尺寸。2–3 项同权并列使用一行开放分栏；四项用 2×2，五项用 3＋2，六项用 3×2。卡片高度按最窄列预计正文行数计算；短内容不得用高空卡片撑满页面。短流程用开放轨道、长说明用阶段卡；四条短支撑信息可用上主下辅，其余用左主右辅；5–6 个里程碑用纵向时间线避免横排拥挤。短对比也要收紧内容区，不改变事实或字号下限。绘制器按相同规则计算实际几何，PowerPoint 导出后仍需检查视觉平衡。

`assets/minimal-template-pack/` 保存三种风格各一套封面、目录、章节、封底可编辑源页，共 12 页，并记录原仓库提交、原页号与文件哈希。远端获取失败时，仅在包内所有文件通过哈希校验后使用它，并标记 `library_source=local_verified_template`。远端成功后，先验证新提交再更新本地包；无合格来源时完整稿阻断。蓝色封面现为 `cover-01`（P001 蓝色星球图），已完成短文案试填及本机 PowerPoint 渲染检查，仍为待审阅草稿；实际标题和辅助文字须通过组件绑定容量与成稿视觉检查。构建本地包时仅从蓝色封面离线副本移除源稿嵌入字体及其引用，保留远端原稿、形状和可编辑文本；跨机器使用时仍须确认 Microsoft YaHei 和 Arial 可用，并复核版面。HTML 模板出稿仍需单独验收。

本 Skill 基于旧版 `epoint-presentation-legacy` 迭代。Skill 内置用户提供的 Logo、基础蓝／红／深蓝色系、字体角色和离线基础出稿器；`knowledge-base.json` 指向现有仓库的 `main` 分支，提供《01蓝色系》《02红色系》《20页封面（比例16-9）》《03深蓝-科技风》等原稿模板和图库。深蓝科技风用独立 `style_family=deep-blue-tech`，默认不与简约蓝红混排。旧 Skill 改读独立的旧版知识库仓库。当前品牌及模板资产为 `draft_pending_review`，不能称为正式批准 VI。

## 出稿前选择视觉风格

制作整套 PPTX 或 HTML 时，先执行[风格选择](references/style-selection.md)：用户未指定整套风格，就展示 Skill 自带的[三种风格预览](assets/style-previews/index.html)，让用户在**蓝色系、红色系、科技风格**中选一项；用户已指定或已在本项目确认时直接沿用，不重复提问。选定值写入逐页计划，并贯穿封面、正文、封底、主题变量和离线出稿。预览是知识库真实页面的本地快照，仅说明视觉方向，不等于指定使用该版式。

## 离线品牌底座与知识库分工

**正文页眉按风格锁定。** 知识库模板保留已验收来源页。蓝红简约的新绘正文页仍使用 `assets/layouts/offline-core.json.content_header`：左上角 24 pt 标题、同起点的细分隔线、右上角 Logo。科技风的技能排版与自由编排正文页使用 `offline-core.json.tech_content_header` 和技能自带的 `assets/layouts/tech-content-header.pptx`：复用科技知识库 `content-tech-021` 的原生顶部图形组，28 pt 白色可编辑标题居中，白色 Logo 位于右上角，不画简约版横线。正文排版仍依原有内容关系规则。红色浅底 Logo 固定黑色，红色来源页已有灰色单色标识可保留。组装后分别核对三种风格的页眉和实际渲染。

**新绘正文画布与衬底。** 三种风格均先铺锁定画布色的可编辑矩形，保证 PowerPoint 合并后底色不丢。蓝红简约的新绘正文页继续使用 `offline-core.json.content_atmosphere` 的两枚 220 pt 柔边椭圆。科技风新绘正文页固定使用 `#05193A` 画布和本地原稿顶部图形组，不叠加弥散椭圆。知识库来源页保持原背景与图形；新绘页不得自造 RGB 或阴影。渲染后检查顶部图形、画布和正文对比度。

**先按内容编排，再决定模板是否适用。** Skill 本地 `assets/brand/` 保存 Logo、颜色、字体等品牌身份；独立的 `assets/layouts/offline-core.json` 保存基础页面结构及历史封面／封底位置（后两类不再用于完整出稿），品牌身份不强制使用某张原稿。完整演示稿的封面、目录、章节页和封底必须从已校验的 Git 知识库或本地最小模板包选版并填充；四类页面不可用自由绘制或 Skill 本地离线版代替。正文可按信息关系复用模板，也可在锁定品牌变量下自主编排。远端和本地最小模板包均不可用时停止完整出稿；仅可用[离线品牌出稿](references/offline-brand.md)制作 `complete_deck:false` 的内容页局部草稿，并注明 `library_used=false`。不要把离线新绘页面说成复用了原稿模板；最小模板包以外的指定原稿、完整封面图库、源页动效和现有 HTML 原型仍需要远端知识库。离线品牌稿使用本地主题快照，保留草稿状态与人工视觉复核。Logo 默认加到每页，按所选风格选用现成彩色、黑色或白色资产；红色风格只使用黑白灰单色标识。

**离线视觉规则：默认不加阴影。** 卡片、流程框、指标框、图标容器和装饰图形使用留白、边框与色块建立层级；离线渲染器会清除 PowerPoint 新建图形继承的主题阴影。具体约束和验收见[离线品牌出稿](references/offline-brand.md)。

**正文模板匹配失败时，按内容关系使用 Skill 内置托底排版。** 基础正文有要点、卡片、流程、对比、指标 5 类；`assets/layouts/fallback-layouts.json` 另沉淀 13 类可编辑 PPTX 关系结构，包括目标与实际偏差、决策矩阵、职责泳道、数据表格、时间轴、图文案例和对比型数据图表。合计 18 类正文结构。要点、指标、对比、表格与图文案例在原有版式 ID 下按内容选择子布局，不为疏密或局部变化新增版式 ID。选版条件、输入字段、容量边界和视觉验收见[正文托底排版](references/body-fallback-layouts.md)。仅在正文无合格知识库候选或设定数量的候选实际试填均失败后使用，并记录 `fallback_layout_id`、`variant` 与未复用原因。不得用托底结构代替封面、目录、章节或封底；所有业务事实、数字和案例图片均来自用户材料。

**整稿正文避免同构重复。** 同一稿件若有多张技能排版页，先比较相邻页和已用的 `fallback_layout_id/variant`；三项同权卡片用开放三列，六项内容首次可用开放两行分组，再次出现则用边框网格。选版日志记录变体，保持信息关系和真实项数。对其他关系先比较信息密度和主次，再选择合适结构；不随机改页型，也不为了多样性编造数字、图片或重点。生成后并排复核整稿节奏，而不只逐页查越界。

基础正文的 `process` 流程卡片与 `comparison` 双列对比衬底使用直角矩形；绘制器和本地预览均按此规则生成。

**技能排版仍不适用时，进入受约束的正文自由编排。** 模型先说明既有结构不适用的具体原因，再提供逐元素 `free_layout`；执行器按[自由编排协议](references/free-composition.md)绘制可编辑文本和图形，只使用所选风格的品牌变量、字体与默认 Logo。逐页 `selection_mode` 与 `selection_label` 明确区分“知识库模板／技能排版／自由编排”；自由编排不计入知识库复用。正文容量校验失败且无 `free_layout` 时停止该页，不强行压缩。四类结构页仍必须使用已校验模板。完整稿在 PowerPoint 中复核文字边界和视觉节奏。

**颜色只从锁定变量或来源组件取值。** 先固定 `blue`、`red` 或 `deep-blue-tech`，新绘页面的全部 RGB 只能取自 `assets/brand/brand-baseline.json` 与 `assets/brand/brand-palette-lock.json` 相同主题下已登记的角色；不得由模型另造 RGB、灰阶、透明白或暗色文字，也不得从封面图片临时抽色。绿系实验主题不进入常规出稿。蓝色内容页浅底使用 `F6F9FF`；来源封面的 `E7E6E6` 不作为蓝色内容页通用灰底。`audit_brand_palette_source.py` 可对照知识库原稿验证锁定值的来源；新绘 PPTX 用 `scripts/audit_new_drawn_palette.py --input <PPTX> --theme <主题> --report <报告>` 拦截锁外颜色或擅改变量，内置离线出稿器自动执行。复用原稿时，`fill_layout.py` 先对照知识库来源页核验全部 12 个主题色槽，再将所选单页及其版式、母版、原生图表的主题色引用固化到组件对象中；原始来源 PPTX 保留作对照。模板里原有的显式色、渐变及非 Logo 图片保留来源视觉，不能因此开放给新绘页面任意取用。PPTX 格式仍保留主题部件，但可见组件不得依赖母版颜色槽。红色来源页的彩色 Logo 在原锚点替换为黑／白资产，整稿运行 `audit_logo.py --theme red --require-every-slide` 拦截彩色标识。

蓝红补充模板与其他新模板统一由当前 Git 知识库登记。补充模板的来源、支持主题、角色、目录项数和正文容量均从 `catalog.json`、`source-pages.json`、各组件的 `bindings.json`／`layout_rules.json` 实时读取；不要使用 Skill 中的历史版式数量判断当前可调用范围。红色独有页面仍只按该组件登记的 `themes` 调用，跨色系换色、动效与 HTML 也只按当前能力字段判断。

## 按任务读取

| 任务 | 规则 |
| --- | --- |
| 出稿前选蓝色／红色／科技风格 | [风格选择与预览](references/style-selection.md) |
| 从材料制作整套 | [内容规划与选版](references/deck-planning.md)、[数据契约](references/library-contract.md) |
| 选封面、封底 | [封面图库](references/cover-selection.md) |
| 换色或加 Logo | [主题与品牌](references/theme-and-brand.md) |
| 知识库不可用时出内容页局部草稿 | [离线品牌出稿](references/offline-brand.md) |
| 正文模板不匹配时选择其他可编辑排版 | [正文托底排版](references/body-fallback-layouts.md) |
| 技能排版也不适用时设计正文新布局 | [自由编排协议](references/free-composition.md) |
| 增加动效 | [动效](references/motion.md) |
| 输出 HTML | [HTML 输出](references/html-output.md) |
| 提炼新模板 | [来源与质量](references/source-and-qa.md) |

同一任务只读所需规则；先用 `--brief --limit` 查询候选，再读入选组件的 `spec.md`、`bindings.json`、`layout_rules.json` 和预览。不要把来源页、主题色变体或参数化项数重复计算为不同版式。

## 使用知识库模板制作整套

用户提供的文档、网页或演示文件默认作为内容来源，除非明确指定为视觉参考。先确认整套风格，再规划每页结论、证据和信息关系。用户明确要求复用模板且知识库可用时，在已选 `theme` 和 `style_family` 内筛选封面、正文与封底；逐页先按图形结构匹配，再按字段位置和容量试填。正文模板不适合内容时，可使用同风格的本地品牌底座灵活编排；四类结构页若无合格知识库候选，应调整标题、拆分目录或暂停完整出稿，并明确说明采用了 `skill_offline_brand`、模板复用情况及仍需人工复核的页面。不得把业务事实强行塞入不匹配的固定槽位。

整套出稿开始时先检查 Git 知识库是否可获取，并记录成功时的 commit 或失败原因；Skill 自带风格预览不代表知识库已连接。知识库可用时逐页记录 `source_template`、`guided_composition` 或 `free_composition`，以及候选数和未复用原因；只有实际抽取并填充源页才计入模板复用率。交付前核对整套所选主题与实际颜色：新绘图形使用 `brand-baseline.json` 的语义颜色，原稿保留的其他颜色须说明来源或做逐对象映射，不得仅凭 Logo 或单一蓝色装饰宣称使用了整套模板。

完整稿必须使用逐页来源验收。四类结构页的填充输入带 `library_commit`，组装清单逐页登记 `role`、`layout_id` 和填充报告的 `source_stamp`；仅当所有页面都复用原稿时设置 `require_template_source: true`，混合自由编排正文时保持按角色验收，四类结构页仍强制核对来源。由 `assemble_deck.ps1` 核对输入、来源主题及组件颜色独立性，再以同一份清单运行 `audit_deck.py --plan <清单> --input <成稿> --out <报告>`，检查最终文件的逐页来源。**最终保存的 PPTX**还须运行 `scripts/audit_component_color_independence.py --input <成稿> --report <报告>`，确保页面、版式和母版没有可见的主题色引用；即使 WPS 等软件重绑母版，也不能重新出现橙、黄、绿。`audit_theme_integrity.py` 仍可用于诊断母版引用差异，但固化后的组件以颜色独立检查及 PowerPoint 渲染为交付门槛。原生图表样式若含 `phClr` 占位符，须单页目视复核。视觉验收还需对照实际原稿预览。用户要求整套同色时，可在保留模板结构与品牌标志的前提下调整已核对的强调色。

## 核心工作流

1. 从用户材料建立逐页计划：每页一句结论、证据来源、信息关系、项数、文字长度、图表数据、图片来源和输出格式。业务事实仅来自本次材料，不引用模板示例数字或标题。
2. 先按风格、角色、图形关系、已验证项数、格式和基础容量筛选；知识库 `relation-taxonomy.json` 将具体关系归入统一类型。已验收普通正文在 `matching_policy=structural` 且 `matching_activation=pilot_verified` 或 `structure_ready` 时允许跨原稿业务名称复用；两者均可由通用内容进入候选，实际试填前须映射并填满登记的必填字段，`semantic_strict` 仍需符合专用关系；图表和指标另核对数据契约。四类结构页仍按角色精确匹配，未验收组件不因别名进入自动选版。`items` 自动推导项数，显式项数矛盾时拒绝；旧固定组件只有具备原生项数或静态验收记录才可按该项数检索。随后按结构吻合、可映射字段缺口、容量、原生项数和结构重复度排序；普通组件不按来源业务标签排序，默认对最多 6 张合格候选实填，允许设定 1–8 张，并记录字段缺失、容量与图片槽等失败原因。标签和初筛候选均不等于实填成功；不能为求变化选错结构。候选不足时说明 `diversity_gap`，固定 seed 仅用于同档候选的可复现打散。
3. 将用户已选风格映射为 `blue`／`red`／`deep-blue-tech` 主题；科技风必须显式设置 `style_family=deep-blue-tech`，封面、目录、内容和封底在同风格内匹配；旧三源默认选版不会进入科技风。原生形状、图表、表格和 SVG 只按登记的语义颜色角色变更；JPG／PNG 按色系与风格选择。品牌 Logo 内部颜色锁定。
4. 默认添加独立 Logo。原 20 张封面默认保留源稿股票代码 `688232`；其中含 Slogan 的 P03、P04、P14、P15、P16、P20 保留完整“成为行业数字化领航者”。科技风源稿没有股票代码或该 Slogan，不得从旧封面规则自动复制。科技风已有源 Logo 的页保留原件，缺失页按背景补白色／彩色 Logo。红色来源模板中已为黑白灰单色的组内 Logo 必须保留原图片及组变换，不能按子图的组内尺寸重新插入；若确需换图，先验证最终渲染的实际尺寸。Logo 审计必须同时检查图片存在和可见尺寸，封面与封底需目视复核。Logo、股票代码和 Slogan 在动效中保持静态。
5. 已实现可编辑 PPTX 的按页提取与填充。每次任务从固定 Git commit 的 `catalog.json`、`relation-taxonomy.json` 和对应 `layout_rules.json` 读取当前候选、`classification_status`、`pptx_support`、`verified_counts`、字段容量与媒体状态；目录也按各组件登记的 `directory_item_fields` 和长文案容量判断。不得把来源盘点、原型项数、示例预览或历史批次说明当作当前验收状态。只有字段完整且实填通过的候选才能用于组装；资产仍为 `draft_pending_review` 时显式允许草稿并保留人工复核。填充时清除源稿自动翻页，动效按新的讲述规则单独添加；静态最终画面须完整。填充后渲染、检查碰撞、字体、Logo、媒体引用和实际放映。

使用脚本时，默认由 `scripts/library_location.py` 同步并读取专属 Git checkout。同一次任务记录 Git commit，后续传同一个 checkout 的 `--library`，避免生成途中远端版本变化。生成结果说明来源 commit、实际候选、待评审状态及未完成的视觉验收。

## 自动选稿池与知识库能力边界

**知识库是版式能力的唯一实时来源。** 每次出稿先同步并校验 `knowledge-base.json` 指向的 Git 知识库，在同一任务内固定 commit。组件数量、组件 ID、蓝红科技覆盖、固定或可变项数、长文案容量、动效和 HTML 支持均从该 commit 的 `catalog.json`、`relation-taxonomy.json`、`bindings.json`、`layout_rules.json`、`motion.json` 及相关审阅记录读取。Skill 不保存累计组件数或逐批白名单；历史验收证据留在知识库 `review/` 和项目验收报告中。更新知识库的元数据并通过清单校验后，下一次调用自动使用新候选。

**进入自动候选须同时满足当前记录。** 检查所选风格和主题、正文或结构角色、具体／通用信息关系、`classification_status=verified`、可用 PPTX 状态、可用媒体、`verified_counts` 与真实项数。对短文、长文和标题逐字段检查 `semantic_path`、`max_chars`、`max_lines`、`max_width_units`；`structure_ready` 先按结构进入候选，由程序尝试真实字段映射；仍缺字段时才依据材料补齐，随后检查容量和步骤／日期等原生规则；某组件的长正文已验收，不代表它的中心标题、顶部总结或其他字段也可加长。固定项数组件不得删空文字伪装为少项；变项数仅按该组件的 `verified_counts` 开放。图表、进度百分比、日期等必须来自本次材料，并执行该组件登记的数据一致性规则。

**正文长文案参考值。** 在当前知识库 `review/body-longcopy-capacity.json` 中按组件 ID 和 `semantic_path` 读取逐字段的 `recommended_max_cjk_chars`、`registered_min_max_chars` 与 `use_for_planning_cjk_chars`。内容规划以 `use_for_planning_cjk_chars` 为参考，实际填充仍须通过 `bindings.json` 的字符数、行数、行宽及 PowerPoint 边界验收。长正文自动选稿还须检查该组件的 `long_copy_review_status=长文案已验收`；`视觉复核未通过`、填充失败和标题溢出状态不可用于长正文自动选稿。参考值由蓝红科技版本逐字段测量，蓝红共用较小值；适用于中文单段自动换行。短标签与标题不能当作正文槽，`preparation_methods` 含 `source_fallback` 的组件还需正常填充路径复核。**结构复用新增的短文案跨业务试填只验证新字段映射，不会重置该组件既有的长文案验收；报告中分别记录结构映射验收、逐字段长文案验收和整稿视觉复核。**每次从固定知识库 commit 读取，不在 Skill 中复制组件数值。

**结构页容量按页面职责读取。** 封面、目录、章节、封底从当前固定知识库提交的 `review/structure-page-capacity.json` 读取主题、项数和逐字段已测容量；实际选版仍执行各组件 `bindings.json` 的字符、行数、行宽限制与 PowerPoint 渲染检查。目录按支持项数和每项标题／副标题分别校验；封面核对标题、副标题、署名与日期；章节页核对编号、标题和辅助文字，并保持整稿同一 `layout_id`；封底核对结束语与署名。已测字数只是对应压力样例的规划参考，不保证任意同长度文字均适配。封面、章节、封底的全部可编辑文字字段必须提供真实非空内容，缺失则改选版式或停止完整出稿，不保留来源示例文案。`visual_review=pending_final_deck_review` 的目录须在成稿中逐页目视复核。

**验收状态逐能力读取，不从批次推断。** `draft_pending_review` 仍须显式 `allow_draft` 和人工审阅；`visual_initial`、`pending_render`、`not_verified` 或内部原型不进入默认自动选稿。PPTX 静态可用不意味着 HTML、跨色系换色或动效可用；只有对应能力状态为已验证时才开放。来源结构页必须继续遵守封面、目录、章节、封底的模板要求；正文若无适配模板，按技能排版和受约束自由编排两层托底。最终以实际填充、PowerPoint 渲染和整稿审计为交付依据。

**特殊版式由知识库规则驱动。** 需要修整版源页时按 `ready_source_by_theme` 取用；普通正文的字重按组件 `normal_body_weight` 执行，标题、指标和刻意强调文字不套用。目录重排、步骤次序、日期连续性、图表合计、百分比联动、Logo 替换与背景覆盖依各组件的规则和脚本检查；不得把某一页的例外复制给整套稿。新增或修订普通组件只更新知识库的目录、绑定、规则和审阅证据；若引入脚本尚不支持的新形状、图表、动效或输出格式，需先扩展执行器并通过专项验收。
