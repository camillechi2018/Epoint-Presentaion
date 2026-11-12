# 正文自由编排协议

当知识库无合格正文模板或前三个候选试填失败，且技能排版库的字段、项数或信息关系无法妥善表达内容时，使用 `free_composition`。封面、目录、章节页、封底仍必须来自已校验的知识库或本地最小模板包。

## 三层选版记录

逐页计划的 `selection_mode` 与 `selection_label` 分别取：

| selection_mode | selection_label | 含义 |
| --- | --- | --- |
| `source_template` | 知识库模板 | 已校验来源页，成功填充后才计入模板复用 |
| `guided_composition` | 技能排版 | Skill 内置正文结构及子布局 |
| `free_composition` | 自由编排 | 模型安排正文元素几何，绘制器使用锁定风格变量 |

规划阶段若模型判断技能排版不适用，应在 `content.layout_assessment` 写 `skill_suitable:false` 及具体 `reason`，并提供 `free_layout`。如果技能结构在执行时因容量或字段验证失败，而 `free_layout` 已提供，执行器也会自动进入自由编排。未提供 `free_layout` 时明确报错，不把复杂内容强塞成要点页。知识库候选仍先试用，不能仅凭模型选择跳过合格模板。

## 输入示例

```json
{
  "role": "body",
  "purpose": "呈现三项行动和一个最终决策",
  "content": {
    "title": "下一步行动与决策",
    "layout_assessment": {
      "skill_suitable": false,
      "reason": "三项行动需按时间并列，最终决策需跨三栏置于底部；现有流程结构无法表达汇合关系"
    },
    "free_layout": {
      "rationale": "上方三列行动，下方一条汇合决策；用空间关系表达信息主次",
      "elements": [
        {"kind":"rect","x":0.80,"y":1.70,"w":3.60,"h":2.90,"color_role":"surface","border_role":"border"},
        {"kind":"text","x":1.05,"y":2.00,"w":3.05,"h":0.70,"text":"确认范围","size_pt":24,"color_role":"primary","font_role":"heading","bold":true},
        {"kind":"text","x":1.05,"y":2.90,"w":3.05,"h":1.10,"text":"明确边界和责任人","size_pt":18,"color_role":"text"},
        {"kind":"line","x":0.80,"y":5.35,"w":11.70,"h":0.04,"color_role":"primary"},
        {"kind":"text","x":1.10,"y":5.65,"w":10.90,"h":0.80,"text":"最终决策：按统一验收口径推进","size_pt":25,"color_role":"text","font_role":"heading","bold":true}
      ]
    }
  }
}
```

元素坐标为英寸，16:9 画布上的正文安全区为 `x=0.65–12.70`、`y=1.32–6.90`。支持可编辑的 `text`、`rect`、`ellipse`、`line`，以及有真实来源的 `image`。图片必须提供本地 `source_path`，仅接受 PNG/JPEG；没有来源时不得画图片占位框。文本字体用 `font_role=body|heading|latin_numeric`：前两者对应任务 `font_profile.east_asian`，拉丁字母与数字对应 `font_profile.latin`；字体层级由字号和字重建立。颜色只用品牌变量角色，如 `primary`、`text`、`muted`、`surface`、`border`、`neutral.white`。不得写 RGB 或新增颜色。文本字号限 14–32 pt；至少保留一段可编辑正文。文字框不得互相重叠。每页最多 30 个元素；超出安全容量时拆页。

绘制器统一添加所选风格的背景、标题、Logo 和页码。蓝红简约读取 `offline-core.json.content_header` 与 `content_atmosphere`；科技风读取 `tech_content_header`，使用本地原生科技顶部图形组、居中白色标题、右上白色 Logo 和 `#031634` 画布，卡片表面使用 `#05193A`，不加简约横线或弥散椭圆。模型只编排正文安全区，不改页眉。绘制器清除阴影，校验主题色与母版颜色独立性。最终仍须用 PowerPoint 复核实际文字边界、视觉节奏和内容依据。自由编排的 `library_used=false`，并在计划与验收报告中保留 `rationale`、进入该层的原因和图片来源。
