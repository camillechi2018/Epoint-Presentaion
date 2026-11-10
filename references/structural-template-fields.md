# 普通正文组件：结构候选与字段映射

知识库中 `matching_policy=structural` 的正文组件按**图形结构和真实字段**复用，不按来源稿的行业、部门或业务名称拒绝。`pilot_verified` 和 `structure_ready` 均可接受结构化正文请求。候选发现、字段映射、原生试填和整稿视觉复核是四个不同状态；只有实际填充成功的组件才计入知识库使用。

## 调用步骤

1. 先从材料梳理信息关系、真实项数、标题与证据，选择能承载这些内容的图形结构。
2. 用 `content.type`、真实 `items` 和项数检索同风格候选。`candidate_summaries` 返回结构、项数、字段角色、容量、媒体与验收状态、来源预览；`awaiting_mapping` 仅表示缺目标字段，并非已套版。
3. 执行器逐候选尝试把标题、条目标题与说明、中心标题、摘要等真实字段映射到 `required_binding_paths`。复杂组件需要的分组、短标签、日期或其他字段必须由材料明确提供。完整 `template_fields.v1` 仍是兼容输入，但不再是普通组件进入候选的前提。
4. 某个槽位没有真实内容，就试下一候选、改用字段更少的组件或使用技能排版；不能沿用原稿示例、重复文字或推测事实来凑满。
   已提供的条目说明也不能因目标版式只展示标题而静默丢弃；该候选应视为字段不适配。
5. 继续执行容量、编号、日期、Logo、主题色和实际 PowerPoint 渲染检查。`structure_ready` 是已试填的结构能力，真实整稿视觉仍需复核。

例如四项结构可先提交通用输入。只有材料确有中心论点时才填写 `center.title`：

```json
{
  "role": "body",
  "title": "四项协同工作",
  "theme": "blue",
  "content": {
    "type": "cards",
    "center": {"title": "协同推进"},
    "items": [
      {"title": "需求确认", "body": "核对范围与交付口径。"},
      {"title": "资源准备", "body": "落实人员与所需资料。"},
      {"title": "执行跟踪", "body": "记录进度与待处理事项。"},
      {"title": "结果复核", "body": "按约定标准确认交付结果。"}
    ]
  }
}
```

若调用者已经准备了全部内部字段，也可继续使用完整字段协议：

```json
{
  "role": "body",
  "title": "四项协同工作",
  "theme": "blue",
  "content": {
    "type": "template_fields",
    "structure_type": "framework",
    "texts": {
      "page.title": "四项协同工作",
      "center.title": "协同推进",
      "items[0].heading": "需求确认",
      "items[0].body": "核对范围与交付口径。",
      "items[1].heading": "资源准备",
      "items[1].body": "落实人员与所需资料。",
      "items[2].heading": "执行跟踪",
      "items[2].body": "记录进度与待处理事项。",
      "items[3].heading": "结果复核",
      "items[3].body": "按约定标准确认交付结果。"
    }
  }
}
```

上例字段对应 `content-blue-142`，文字仅演示输入形态；正式出稿必须使用用户材料。`template_fields` 是编辑槽位协议，字段名保留来源路径是为了定位形状，不代表保留来源业务语义。季度、日程、指标等 `data_contract` 页面仍需校验真实数据关系；审批分支等 `semantic_strict` 页面仍需专用内容。

### 嵌套结构的真实字段

日程类页面如果每个阶段下确有任务，可以提供 `phases[].tasks[]`。适配器会按组件声明把每项的 `heading` 和 `body` 逐一映射到原生文字槽；少一项任务说明即拒绝该候选。`content-blue-071` 需要三个阶段、每阶段两项任务，不能把普通三项并列材料改写成虚构的六项任务。其他组件的具体必填槽仍以当次知识库的 `matching_contract.required_binding_paths` 为准。
