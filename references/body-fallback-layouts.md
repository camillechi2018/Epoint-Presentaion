# 正文模板未匹配时的排版托底

## 位置与边界

先按知识库目录筛选与试填正文模板。只有无合格候选（`NO_ELIGIBLE_TEMPLATE`），或最多三张候选试填均不合格（`NO_FIT_AFTER_TRIAL`），才使用 Skill 内置的正文排版规则。封面、目录、章节页、封底始终从已校验知识库或最小模板包获取，不能使用此处的自由排版代替。

本规则是知识库的**结构补充**。借鉴花叔 Design 的信息组织方法，用新点锁定主题颜色、字体和 Logo 在 PowerPoint 中重绘为可编辑对象。不开阴影，不使用参考样例里的业务文字或数据。各版式的适用关系和来源见 `assets/layouts/fallback-layouts.json`。

蓝红简约托底正文共用 `assets/layouts/offline-core.json.content_header`：标题、横线和 Logo 的尺寸与位置按知识库简约正文页实测锁定。科技风使用 `tech_content_header` 和技能自带的原生科技标题栏图形组：居中可编辑白色标题、右上角白色 Logo、`#05193A` 画布。自由编排也按风格使用对应页眉；正文信息关系排版保持不变。

蓝红简约托底正文继续使用 `offline-core.json.content_atmosphere` 中的可编辑弥散衬底。科技风不叠加椭圆，仅保留锁定深蓝画布及原稿科技标题栏；知识库原页不追加衬底。

## 每页选版顺序

1. 先写本页要让听众得出的**一句结论**，再识别实际关系：连续数值、主次信息、多维证据、问题到结果、上下层级、段落叙事、精确表格、日期里程碑、来源图片或分类数值对比。
2. 根据真实内容选择下表十三种关系结构；普通文字或基础关系再用 `bullets`、`cards`、`process`、`comparison`、`metrics`。字段不满足安全容量时拆页或换结构；不能生成空数据、空卡片、空图片或编造事实凑版式。
3. 同一份稿件避免连续三页使用同一 `type`。六项卡片首次可用开放式两行分组，再遇到六项则改用边框网格；三项同权短内容使用无衬底三列。只改变构图和层级，不改变原文的项数、事实或关系。若信息确实属于同一关系，优先调整叙事角色和信息拆分，不为了多样性篡改事实。
4. 在逐页计划记录 `selection_mode=guided_composition`、`reason_code`、`fallback_layout_id`，`library_used=false`。实际组装和验收仍走原流程。

## 五种基础结构与内部变体

`bullets`、`cards`、`process`、`comparison`、`metrics` 是基础正文类型。要点、卡片、流程、指标和对比的视觉变化保留原有 ID，可显式给 `variant`。`featured_index` 是从 0 开始的项序号，必须指向材料中的真实重点。`assets/style-kits/composition-rules.json` 记录选择门槛。

`process` 的步骤衬底和 `comparison` 的左右两栏衬底统一用直角矩形。两种结构的强调顶条、文字位置及配色仍按所选主题变量绘制。

| type | 变体 | 自动选择规则 |
| --- | --- | --- |
| `cards` | `grid`、`columns`、`stat_rows` | 2–3 项同权内容使用无衬底开放分栏；六项首次用两行开放分组，再次出现用边框网格；其他项数沿用容量自适应网格。`grid` 按最窄卡片的预计正文行数计算整行高度，短文案不得画成大空卡；卡片左边缘只用短竖线点缀，标题与正文保持统一缩进。`columns` 接受 2 或 3 项，`stat_rows` 只接受六项 |
| `process` | `cards`、`rail` | 3–5 步且每步短说明用连接线与节点组成的开放轨道；说明较长则用带衬底的阶段卡。`rail` 至少 3 步，连接线与步骤同步增减 |
| `bullets` | `balanced`、`compact`、`spacious`、`lead` | 2–3 项短内容宽松排；5–6 项或有长项紧凑排；其余均衡排；指定 `featured_index` 时突出一项主结论 |
| `metrics` | `grid`、`hero`、`lead_support` | 只有一项指标时用单个大数字；多项且指定 `featured_index` 时用一主多辅；其余并列呈现 |
| `comparison` | `standard`、`before_after` | 同一对象确有改造前后状态和材料中的变化说明时，底部增加 `change_summary`；两侧 `left`、`right` 仍按来源填入 |
| `data_table` | `standard`、`action_tracker` | 行动跟踪使用 `actions:[{issue,action,owner,due,status}]`，2–6 行；不借用普通精确数值表的字段 |
| `image_case` | `standard`、`annotated` | 截图标注使用 1–3 个 `annotations:[{x,y,label}]`；坐标为图片相对位置 0–1，右侧逐点解释，截图仍是可替换的来源图片 |

`priority_grid` 在 4 条短支撑信息时自动使用 `top`（上主下辅），其余用 `side`（左主右辅）；`milestone_timeline` 在 3–4 个里程碑时用 `horizontal`，5–6 个时用 `vertical`。这两类也可显式给 `variant`，但超出容量边界须重排或拆页。

`lead` 和 `lead_support` 不得由模型凭空判定业务优先级。指标数值、单位、时期和来源按材料保留；不要为了大数字样式抽掉必要口径。

## 十三种关系结构与输入

| type | 内容条件 | 输入字段 | 布局重点 |
| --- | --- | --- | --- |
| `assertion_evidence` | 一句结论与 3–6 个按时间或顺序排列的非负数值 | `title`、`series:[{label,value}]`、`data_source`；可选 `unit`、`summary` | 上方完整结论，左侧大折线，右侧首末变化量；源数据必须可追溯 |
| `priority_grid` | 一个主结论与 2–4 个辅助要点 | `title`、`lead:{title,body}`、`support:[{title,body}]` | 主信息占左侧大区，辅助信息占右侧；避免全部画成等权卡片 |
| `evidence_matrix` | 3–4 个证据维度支撑一个结论 | `title`、`sections:[{title,body}]`；可选 `data_source` | 左侧主证据，右侧分层辅助证据；每区必须有真实内容 |
| `problem_solution_outcome` | 问题、对应方案和有依据的预期或已实现结果 | `title`、`problem:{title,body}`、`solution:{title,body}`、`outcome:{title,body}` | 固定三栏因果顺序；不得将预期结果写成已实现成效 |
| `layered_architecture` | 原文确有 2–4 个上下层级 | `title`、`layers:[{title,items:[文字]}]`；每层 1–4 项 | 层级自上而下，层内对象同级；不能把并列事项画成上下级 |
| `longform_metric` | 2–3 段完整论述配一项关键数字 | `title`、`paragraphs:[文字]`、`metric:{value,label,source}` | 左侧保留连贯叙事，右侧突出有来源的数字和口径 |
| `data_table` | 1–8 行、2–6 列精确数据 | `title`、`columns:[文字]`、`rows:[[单元格]]`；可选 `data_source` | 原生可编辑单元格图形，逐格保留原值；必要时标出来源 |
| `milestone_timeline` | 3–6 个有真实日期或时期的事件 | `title`、`milestones:[{date,title,body}]` | 节点等距重排，日期与事件一一对应；纯步骤不用时间轴 |
| `image_case` | 来源图片本身支撑案例说明 | `title`、绝对路径 `image_path`、`case_title`、`body`、`takeaway`；可选 `image_caption` | 左图右文；图片必须存在且与主题相关；文字可编辑，嵌入图片可替换 |
| `comparison_chart` | 2–5 类同口径数值比较 | `title`、`categories:[文字]`、`series:[{name,values}]`、`data_source`；可选 `unit` | 原生可编辑条形、文字和标注；1–2 个系列，不能补造缺失值 |
| `target_actual_gap` | 同一指标存在目标值与实际值 | `title`、数值 `target`、`actual`、`unit`、`period`、`gap_reason`、`data_source` | 显示两个数值，差额自动计算；原因来自材料，不按正负擅自判定好坏 |
| `decision_matrix` | 2–4 个方案按相同 2–4 项标准评分 | `title`、`criteria:[文字]`、`options:[{name,scores:[1–5整数]}]`、`data_source`；可选 `recommended_index` 与 `decision_reason` | 各列同一评分口径，总分自动计算；推荐项仅在材料明确支持时标注 |
| `responsibility_swimlane` | 2–4 个角色跨 2–5 个有序阶段协作 | `title`、`phases:[文字]`、`lanes:[{role,tasks:[文字或空字符串]}]` | 行为角色、列为阶段；没有任务的交叉位置留白，各阶段与角色至少有一项真实任务 |

`type` 可以显式指定；未指定时渲染器根据专有字段识别，均无时使用现有 `bullets`。`data_table` 的行动跟踪和 `image_case` 的截图标注需显式写 `variant`。不能根据题目名称猜出数据、层级或结果。上述字段容量由脚本校验，超出会拒绝出稿。

## 验收

每页检查主题锁色、无隐式阴影、单 Logo、可编辑文本与图形。趋势和对比图核对数值、单位、时期及来源；分层页核对实际层级；结果页区分预期和已实现；长文页核对数字来源；表格逐格核对，时间轴核对日期，图文页核对图片来源及相关性。所有页面在 PowerPoint 中查看文字换行、区块高度与前后页节奏。新增四种关系结构与六张基础变体已分别生成蓝、红、科技风各 10 页短文案样稿，三套 PowerPoint 文字边界检查均为 0 溢出，Logo、锁色和无阴影检查通过。真实长文案、实际业务内容、图片授权及整稿视觉节奏仍需逐稿复核。此规则保持待审阅草稿，不计入知识库原稿组件验收数量。

本轮新增 3 类关系结构及 3 个现有版式的变体。蓝、红、科技风各制作短、长两组，共 36 张 PPTX 页面；PowerPoint 导出文字边界 0 溢出。决策矩阵评分、目标偏差及其他示例数字均为虚构内容，仅用于排版验收。实际调用时需逐页核对数据依据、业务状态、截图标注坐标和相邻页视觉节奏。
