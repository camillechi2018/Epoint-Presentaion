# 知识库数据契约

`relation-taxonomy.json` 汇总已验收组件的统一信息关系与同义词；`catalog.json` 同时保留具体 `information_relation` 和统一 `canonical_relation`。部分已验收组件还登记经审定的中文 `search_label`，供内容目的与版式的轻量排序。普通正文检索在明确关系时可跨相容正文角色；指定具体结构名仍精确匹配。四类结构页角色不放宽。该索引不改变 `classification_status`，也不放宽主题、项数、字段容量和媒体门槛。

自动选稿池不在 Skill 中维护固定数量。每次从当前 Git commit 的 `catalog.json` 读取 `classification_status`、`pptx_support`、`status` 和主题范围；再读 `layout_rules.json.verified_counts`、字段容量及媒体状态。来源审计与对象颜色清单只供追溯，不等于能力验收。

组件的静态 PPTX、长文案、变项数、动效、HTML、扩展色系各有独立验收边界。`semantic-review.json` 与 `review/` 保存专项证据；不能因为某组件曾在代表样张中通过短文案测试，就推断其他能力已开放。

`knowledge-base.json` 唯一指向 GitHub 现有仓库的 `main` 分支。每次任务固定一次 Git commit；用 `scripts/library_location.py` 拉取后记录 commit，后续脚本传同一 checkout 的 `--library`。远端不可用、manifest 校验失败时停止，禁止回退旧版知识库。

来源 PPTX 保留原始母版，便于追溯与再次提取。填充器把选中页面、版式和母版中的主题色引用固化到单页组件；知识库 `themes/*.json` 中的中性色令牌与 Skill 本地 `brand-baseline.json` 对齐。装配与最终保存后检查组件颜色独立性。这个操作只固定原生配色，不等于已验收任意跨色系换色。

`catalog.json` 提供组件候选；`source-pages.json` 记录当前已入库的物理来源页；数量以本次 Git commit 为准。`sources/{blue,red,cover,tech}.pptx` 是四份可编辑原稿，`source_page` 标记页号；调用时只将选中的页提取成单页空版，避免每页重复存储整套母版与媒体。科技风使用 `style_family=deep-blue-tech` 与 `*-tech-*` 独立 ID；`select_cover.py` 和 `select_closing.py` 按角色分选，`plan_deck.py` 未显式指定风格时排除科技风。`bindings.json` 登记字段和对象，科技风另有递归 `shape-tree.json` 和初步 `item-groups.json`；`layout_rules.json` 登记**已验证**可用项数，`motion.json` 登记动效能力。`classification_status=visual_initial`、`html_support=not_implemented`、`cardinality_mode=fixed_until_validated` 按字面理解，不代表已支持。 目录若支持重排，读取当前组件的 `verified_counts`、`directory_item_fields`、`directory_long_copy_profile` 和字段长度约束；超过实测上限时换版或拆分目录。目录项测试不自动开放其他页面的长文案、HTML 或动效；各能力按对应组件当前记录独立判定。

科技风及其他风格的组件若有 `semantic-review.json`，读取其中的结构、适用关系和数据限制。各页面的可变项数只按当前 `layout_rules.json.verified_counts` 和执行器能力开放；内部原型须显式启用并逐页渲染审核，不能当作常规生产能力。

蓝红配对只是顶层形状签名的首轮候选。使用红版时选 `red_source`，不能假设蓝版改色后与红稿完全等价。对缺图、媒体关系异常、未复核占位的页，先排除自动选版。

填充输入只使用本次用户材料；图表必须提供类别、系列、数值、单位、时间和出处。模板示例文本和数据不得作为项目事实。未明确字段语义的页仅用于人工指定、审阅，自动规划不得选择。

