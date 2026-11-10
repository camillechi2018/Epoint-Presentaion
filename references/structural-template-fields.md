# 普通正文组件：完整字段结构调用

知识库中 `matching_policy=structural` 的正文组件按**图形结构和真实字段**复用，不按来源稿的行业、部门或业务名称拒绝。`pilot_verified` 已有通用 `items` 适配器；`structure_ready` 使用 `template_fields.v1`，同样能进入自动候选，但必须先把知识库登记的全部可替换字段填满。

## 调用步骤

1. 先从材料梳理信息关系、真实项数、标题与证据，选择能承载这些内容的图形结构。
2. 在固定知识库提交的 `catalog.json` 中筛选同风格的 `structure_ready` 组件，读取 `matching_contract.structure_type` 和 `required_binding_paths`；再读该组件的 `bindings.json` 和长文案容量记录。
3. 将材料中的事实映射到全部 `required_binding_paths`，构造 `content.type=template_fields`、`content.structure_type`、`content.texts`。选稿器可以通过完整字段自动匹配组件，无须写来源业务场景或组件 ID。
4. 某个槽位没有真实内容，就改选字段更少的组件或使用技能排版；不能沿用原稿示例、重复文字或推测事实来凑满。
5. 继续执行容量、编号、日期、Logo、主题色和实际 PowerPoint 渲染检查。`structure_ready` 是已试填的结构能力，真实整稿视觉仍需复核。

例如四项工作结构可提交：

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

上例字段对应 `content-blue-142`，文字仅演示输入形态；正式出稿必须使用用户材料。``template_fields`` 是编辑槽位协议，字段名保留来源路径是为了定位形状，不代表保留来源业务语义。季度、日程、指标等 `data_contract` 页面仍需校验真实数据关系；审批分支等 `semantic_strict` 页面仍需专用内容。
