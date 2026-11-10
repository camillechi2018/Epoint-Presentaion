# 整套内容规划与选版

先按[风格选择](style-selection.md)确定整套 `style_choice`、`theme` 与 `style_family`；用户已指定则直接沿用，未指定则展示预览并收集选择。随后确定每页结论、证据、信息关系、项数、字段字数、图片来源、图表数据和交付格式，再检索组件。信息关系优先于视觉喜好；数量超出已验收范围就换版或拆页。

开始选版前实际运行知识库解析并记录 commit；解析失败时记录错误并停止完整出稿；只允许制作不含封面、目录、章节页、封底的内容页局部草稿，不能因为看到了 Skill 本地预览图就标记 `library_used=true`。逐页计划记录候选数、淘汰理由和实现路径；整套报告分别统计原稿模板复用页、借用模板视觉语言重新编排页、自主编排页。模板复用页必须有知识库来源 ID 与最终成稿来源核验；其余两类不可计入模板匹配率。简约蓝红知识库旧记录未显式写 `style_family` 时，脚本将其视为 `legacy-blue-red`，但仍按 `theme=blue` 或 `theme=red` 严格筛色。

正文页无合格候选或前三张试填均失败时，使用 Skill 本地[正文托底排版](body-fallback-layouts.md)按信息关系选结构。基础结构 5 类、关系结构 10 类；要点与指标在原 ID 下根据内容疏密和主次选择 `variant`。新增精确表格、日期里程碑、来源图片案例和分类数据对比。记录 `fallback_layout_id`、`variant` 与未复用原因。不得为了套用结构伪造数值、日期、来源、图片或辅助要点；字段不匹配时换结构或拆页。托底页保持 `library_used=false`，仍需与前后页面共同做视觉节奏复核。

若技能排版也不适用，按[自由编排协议](free-composition.md)让模型设计正文元素的位置与主次，并提交 `layout_assessment.reason`、`free_layout.rationale` 和元素几何。模型可自由安排信息，绘制器仍锁定整稿主题色、字体、Logo、安全边距与无阴影规则。逐页 `selection_label` 使用“知识库模板／技能排版／自由编排”；执行后以最终成功方式为准，不把计划候选误算为模板复用。自由编排输入缺失或验收失败时拆页、精简或报告阻断，不静默回退成通用要点页。

硬筛：状态、页面职责、信息关系、字段容量、图片／图表／表格槽、主题、输出格式、媒体完备性、动效能力。未分类组件不进入自动候选，仅能人工指定并记录理由。信息关系先查知识库 `relation-taxonomy.json`：原始 `information_relation` 是具体结构，`canonical_relation` 是统一类型，同义词仅在统一类型内扩展；指定具体结构名时仍精确匹配。封面、目录、章节、封底的角色严格一致。正文页如果提供可识别的信息关系，可在已验收的 `content`、`process`、`framework`、`timeline` 等正文角色中检索；未提供关系时仍按原角色，不做宽泛放行。若页面给出 `items`，规划器直接以数组长度验证项数；同时传 `needs.item_count` 时两者必须一致。旧版固定组件缺 `verified_counts` 时，只接受已验收、来源 `supported_counts=[source_count]` 的固定版，或 `semantic-review.json` 已标记静态 PPTX 验收的原生项数。软排序先优先原始关系及原角色精确匹配，再用知识库 `search_label` 与页面目的／标题的字词重合及原生项数加分，最后考虑结构家族多样性和相邻重复；标签只用于排序，不能代替语义字段实填或视觉验收。随机 seed 仅打散同分候选，不能越过硬筛。使用 `select_layout.py --verified-only --allow-draft --brief --purpose "页面目的" --item-count N` 查看短名单，不能把临时分类页当作可用组件。

按整套选版而非逐页随机。记录每页入选组件、候选数、淘汰原因、结构家族和 `diversity_gap`。同一组件的蓝红色系和不同项数不算新结构。对连续重复可换候选；没有合格候选时保留正确结构并明确重复原因。

当前多数提取组件为 `provisional`，不能以它作为无人值守生成全套 PPT 的依据。首批 14 页视觉初审条目标为 `visual_reviewed`；内部试排可显式传 `allow_draft=true`、`allow_visual_reviewed=true`，结果仍有 `manual_review_required=true`。先补字段语义、容量和实际渲染 QA，才能升为 `verified`。

蓝红补充稿的 `supp-*` 版式已完成 38 个主题变体的短文案静态 PPTX 验收，其中目录已扩展为变项数，可在 `allow_draft=true` 下参与自动选版。蓝红六款目录均支持 2–8 项自动重排，按信息关系、可读容量及相邻页多样性选择；科技风五款目录支持 2–6 项。章节、封面和封底均按源结构字段填充。红色独有封面与章节仅在 `theme=red` 时入选。补充版式共 28 条记录，和原蓝红内容池合计 94 条简约版静态草稿记录；同一家族不同色系不算新结构。目录项长文案按[目录项长文案容量](directory-longcopy.md)和 `directory_long_copy_profile` 及各字段 `max_chars`、`max_width_units` 选版；其他字段按已实填的安全上限；超限时换版或拆页。


## 四类结构页的强制来源

完整 PPTX／HTML 中，封面、目录、章节页、封底每页都要选择知识库对应角色的原稿组件，记录 `layout_id`、`library_commit`、`source_stamp`，并在最终 PPTX 逐页核验。不得用自由编排、离线基础稿或封面图库快照冒充。正文仍可选择 `source_template`、`guided_composition` 或 `free_composition`。目录项数以知识库 `verified_counts` 为准：蓝红简约六款目录支持 2–8 项，科技风五款支持 2–6 项。逐项输入 `items`，按所选版式的 `directory_item_fields` 提供 `title`、必要的 `subtitle` 等字段；脚本连同编号整体增减、自动重排。选择前比较内容关系、各版式长文案容量、密度与相邻页差异，不固定优先某一款。超过上限或字段超限时拆分目录或调整章节结构。知识库不可用或四类结构页无合格候选时，完整出稿应停止并报告原因。
