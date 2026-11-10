# HTML 输出边界

HTML 需要复现同一信息关系，文字须可选择，图形／图表采用 DOM、SVG 或浏览器原生绘制。整页 PNG 截图只能作为预览，不能冒充可编辑或结构化 HTML 组件。要求离线资源、16:9 缩放、全屏、动效关闭后终态完整。

`scripts/render_html.py` 已实现 `cover-01` 与 `content-blue-060` 的离线内部原型，支持可选择文字、内嵌 Logo、16:9 缩放；P060 只支持来源蓝／红模板和 2／3／4 步，浏览器点击可逐步出现。HTML 原型在写文件前核对 CSS 色值是否存在于对应源 PPTX 或来源页预览，拒绝模型自行补色；实验绿主题不进入常规调用。整套 HTML 的可用性须逐页读取当前知识库的 `html_support` 和所选布局的实际 HTML 执行器支持；任一页未验证时不能承诺整稿 HTML。只有对应组件通过与 PPTX 的视觉和交互验收，且执行器可生成该组件时，才可加入默认规划候选。

# 深蓝科技风状态

科技风 P001 封面已有单文件离线 HTML 内部原型：复用两张独立视觉图层，标题、英文副题、汇报人、日期和完整白色 Logo 独立呈现。浏览器已检查图片加载、文字可选择及标题和副题不重叠，预览见知识库 `review/tech-cover-001-html-prototype.png`。该页 `html_support=prototype_requires_cross_format_review`，还需与 PPTX 对照和其他浏览器检查。其他科技页是否支持 HTML，逐页以当前 `catalog.json` 的 `html_support` 和执行器能力为准；不得直接把预览 PNG 视作已支持的 HTML 页面。
