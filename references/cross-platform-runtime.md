# 跨系统运行：S5 候选实现

本轮已完成发布字节校验、隔离依赖安装、独立自检、知识库缓存迁移和 S2/S3 代表性验收。S4 已完成 Windows/Linux 字体与渲染定点验证。用户确认 macOS 实机使用技能 `23e32c5` 与知识库 `58d4977` 测试，安装及效果通过；目标应用版本和逐页证据尚未归档，不单独宣称 Mac PowerPoint 正式签收。安装成功或自检通过不等于整稿交付通过。

## 安装与运行

需要可执行的 Python 3.10 或更高版本。Windows 在技能根目录执行 `powershell -File .\install.ps1`；macOS/Linux 执行 `sh ./install.sh`。启动器会实际运行候选 Python，不要求用户机械替换 python/python3。WorkBuddy 用户技能目录可为 `~/.workbuddy/skills/epoint-presentation`；安装后新开会话或刷新技能列表，再确认技能被发现。

安装器先核对 `runtime.json` 指向的已有虚拟环境、依赖版本、材料读取与模板包；合格时直接复用，即使 PATH 首位是 Agent 自带的其他 Python，也不新建环境。首次安装或旧环境失效时，在用户状态目录创建版本化虚拟环境；完成依赖和本地模板包校验后才原子更新 `runtime.json`。失败保留先前的活动解释器，也保留半成品目录供诊断，不自动删除个人文件。`VENV_CREATE_FAILED` 会返回脱敏后的原始子进程错误、选中的解释器和半成品路径；该代码本身不等于系统缺少 venv/ensurepip。安装器使用系统文件锁，崩溃退出后锁可自动释放。核心直接依赖记录于 `requirements-core.txt`，实际安装的直接和间接依赖版本记录在 `runtime.json`。不同 OS/架构仍需实测，不因依赖能安装就声明完整支持。

安装到指定位置：两个安装脚本都支持 `--state-dir <目录>`。后续设置 `EPOINT_STATE_DIR` 为同一目录，再用启动器选中的 Python 执行 `scripts/run.py`。该入口读取活动解释器，转调原有统一工作流并原样传递参数。旧入口仍可使用，但须自行指定正确解释器。

离线依赖安装支持 `--wheelhouse <目录>`，仅从提供的兼容 wheel 目录安装。模板离线包不包含 Python/Office/字体安装包；首次断网且没有兼容 wheels 时，应报告依赖安装失败，不伪报就绪。安装器不修改全局 Python 或系统代理。

离线 wheel 必须与实际选中的 Python 主次版本、操作系统和处理器架构一致。例如 Linux Python 3.12 不能复用仅含 `cp310` 的 Pillow/lxml wheel；此时安装器返回 `OFFLINE_WHEEL_INCOMPATIBLE`，应提供匹配的 wheelhouse 后重试。

回退时先验证记录中的 `previous_python` 存在，再使用该解释器直接调用统一入口；旧环境不会被安装器删除。本轮未提供自动卸载或一键回退命令。

若要绕过 PATH 中的 Agent 内嵌 Python 并使用指定解释器首次安装，可设置 `EPOINT_PYTHON` 后使用安装脚本。macOS 实例：`EPOINT_PYTHON="$HOME/.local/bin/python3" sh ./install.sh`；也可直接运行 `<指定的 Python 3.10+> scripts/install_runtime.py`。先检查安装输出中的 `candidate_python` 与 `detail`，不要仅凭 `VENV_CREATE_FAILED` 安装额外的系统组件。`scripts/run.py` 始终调用已登记的解释器。

## 自检

`<Python> scripts/run_presentation.py --doctor --out runtime-report.json`

也可直接执行 `<Python> scripts/doctor.py`。自检只用标准库启动；依赖导入放在有超时限制的子进程内，缺少 pptx/Pillow 时仍输出 JSON。`--library` 指定待校验知识库，默认校验安装包内最小模板包。

- `--goal inspect`：校验环境和模板包。可选依赖缺失会报告，但不阻断检查本身。
- `--goal fill`：另外要求核心 Python 包能导入；不代表已经完成实际单页或视觉验收。
- `--goal read`：要求 Excel/Word 只读提取所需的 openpyxl、xlrd 和 python-docx 能导入；不代表已完成内容规划或整稿。
- `--goal assemble`：要求已验证的整稿后端。本轮尚未实现深度后端冒烟测试，Windows 检出 COM 也标记 `untested`，不会据此宣称整稿验收通过。
- `--goal native-assemble`：单独检查显式实验原生组装模块能否导入；通过只表示候选后端及必要依赖可加载。实际 PPTX 的组装、渲染和目标应用视觉复核仍需按真实任务检查。macOS 的 `--goal assemble` 被阻断不等于安装失败。

显式添加 `--deep` 时，在指定用户状态目录及缓存目录写入并读取临时文件，并用当前 Python 创建一页含中文可编辑文本的 PPTX，保存后重开核对。`--state-dir` 与 `EPOINT_CACHE_DIR` 可指定这些检查使用的目录；检查报告的 `deep_checks` 记录结果。此检查验证写入与 PPTX 基础往返，不代表已有模板的合并、目标 Office 打开、导出或视觉验收。

结果区分 available、unavailable、untested，stdout 仅输出 ASCII 安全的机器 JSON；报告文件为 UTF-8。基础自检不会启动 Office、自动上传材料、安装依赖或调整网络设置。S4 起 `--font-profile windows|macos|linux` 探测任务字体是否安装；`fill`/`assemble` 缺字体现为 `FONT_PROFILE_RESOURCE_MISSING`。macOS 优先通过 CoreText 查询已注册字体族，覆盖系统动态字体资产；仅在系统 API 查询失败时使用字体枚举和文件路径兜底，报告 `fonts.detection` 说明检测路径。字体文件存在、资源探测通过均不证明字体在目标渲染器内的字形、换行或版面正确；应用打开与导出仍需校准。`PingFang SC`／`Helvetica Neue` 是本技能的 macOS 排版配置，不表示两者都是 macOS 系统界面的默认字体。

## 分发与校验

源码文本采用 `.gitattributes` 定义的 LF 规范；Windows PowerShell 脚本保留 UTF-8 BOM；二进制不转换。发布者在隔离工作区先暂存拟分发的新文件，再执行：

```text
<Python> scripts/prepare_distribution.py --root <技能根目录> --manifest-root <技能根目录>/assets/minimal-template-pack --write
<Python> scripts/prepare_distribution.py --root <知识库根目录> --write
```

不带 `--write` 时只校验。重建清单只包含 Git 已跟踪/已暂存文件，防止把验证产物或工作区杂项混入发布包。`update_knowledge_manifest.py` 同样采用该规则；不再自动吸收未跟踪文件。

运行时校验只计算原始文件字节哈希，不自动修复、改写或忽略换行差异。跨平台修复应发布新版本，不覆盖旧标签；仓库 `main` 与已发布标签是不同快照。

## 知识库缓存与升级

知识库默认缓存位于用户状态目录下的 `cache/libraries/<来源标识>/`，可以通过 `EPOINT_CACHE_DIR` 指定其他可写目录。来源标识区分仓库 URL、分支、库内路径和知识库版本；不依赖当前工作目录。状态目录由 `EPOINT_STATE_DIR` 或系统用户目录决定。

在线解析先查询远端提交，再下载到候选目录；完整校验原始文件哈希、来源及提交后，将目录保存为 `snapshots/<commit>/`，原子更新 `last-good.json`。下载采用包含当前提交全部文件的浅克隆，不使用延迟下载 blob 的部分克隆。并发更新使用系统文件锁；进程异常退出会释放锁，不以锁文件存在判断占用。

更新失败保留上次有效快照及记录。显式 `--offline` 不连接远端；优先复验当前完整快照，损坏时尝试记录中的上一有效快照，然后尝试旧版完整缓存，最后使用技能自带最小包。每次回退保留原因，不把坏缓存标为有效。`knowledge-base.json` 中带 `legacy_` 前缀的相对路径仅用于只读兼容旧缓存；新下载只写入用户状态目录，不在 WorkBuddy 技能目录旁创建知识库或缓存。

在线成功不再重建安装目录内的最小包；新的完整快照本身支持离线调用。最小包仅在发布构建时更新，继续作为首次离线的补救措施，不扩充模板数量。旧快照当前不会自动删除，避免删除正在被其他出稿任务引用的版本。

错误区分代理 `git_proxy`、TLS `git_tls`、认证权限 `git_permission`、网络 `git_network`、超时 `git_timeout`、Git 缺失及清单/缓存异常；不改变系统代理或关闭证书校验。在线失败不代表所有离线能力不可用，报告以实际采用的来源和提交为准。

## 本轮边界

已抽取公共路径与进程模块并用于新自检和安装器；知识库更新已迁入用户缓存，缓存子流程完成 Windows 与 WSL Linux 的更新、回退、并发和故障验证。Linux 已实测只读安装目录，Windows 已检查安装文件无变更；尚未据此宣称完整出稿工作流均支持只读安装。离线依赖安装矩阵、失败运行环境升级、深度环境自检、原生模板组装和系统字体配置仍按计划推进。macOS 仍待用户实机验证。

## S2 原生组装试点

安装后用 `<Python> scripts/run.py --read-material --input <材料> --out <提取.json>` 调用已登记解释器中的材料入口，避免误用 Agent 自带 Python。`.xlsx` 逐个有效单元格读取，保留合并区域、公式表达式和缓存值状态；`.xls` 保留有效行和合并区域，但 BIFF 读取器不能可靠恢复公式来源或内嵌图片；`.docx` 保留正文段落、表格、媒体引用与文件清单。`.txt`、`.md` 按行读取；`.pptx` 读取逐页可编辑文字、表格与图片引用；`.html`／`.htm` 读取源码文本与图片地址，不执行浏览器脚本。PDF 与 PNG/JPEG 的文字通过当前 Agent 平台工具提取，再按[多格式材料接入](material-ingestion.md)交接。提取结果是事实清单，不自动生成逐页计划，也不意味着所有内容已入稿；缺失公式缓存、图片内文字和 OCR 错漏不得猜测。

`scripts/assemble_native.py --experimental --pages <已填充单页1.pptx> <已填充单页2.pptx> ... --out <输出.pptx>` 是至少接收两张单页的隔离试点；原有 `--first/--second` 两页参数仍可用。它复制源部件及关系，只登记实际使用的母版，并统一备注母版及重新分配复制版式 ID。Linux 原生组装的蓝、红、科技风目录＋章节＋代表正文三页包，以及蓝色原生图表/表格和科技风流程/对比/指标混合正文包，均由 Windows PowerPoint 16.0 打开导出；已比对的正文页与单页源稿像素一致。蓝色 8/16/24 页重复组件压力包亦能打开导出。S5 的显式实验整稿入口复用这一组装器，保留正式完整稿的来源与交付门禁。

`scripts/audit_native_package.py --input <组装包> --sources <对应源页1> <对应源页2> ... --out <JSON>` 检查包内 XML、关系、内容类型、实际使用母版、母版及版式全局 ID、逐页源 XML、同风格及同知识库提交。它拒绝多余母版、重复版式 ID、缺失版式、混合提交和源页被改动的负例。来源标记及源文件仍须先受可信知识库清单校验；仅凭此审计不能证明源仓库可信。**静态检查不等于 PowerPoint 兼容性验收**，每一类新对象组合仍须执行目标 Office 打开、逐页导出和视觉复核。未测图文素材和对象组合、真实材料整稿及高风险长文案不在 S2 代表性验收范围内，不能将此原型作为正式整稿后端。

S2 代表性签收另覆盖四图表与表格混合包、含 PNG/SVG/WDP 和嵌入字体的封面包，以及删除图表工作簿、SVG 后必拒绝的负例。样本在 Windows PowerPoint 16.0 打开导出，组装页与源单页逐像素相同。该结论只覆盖已测对象组合；`content-blue-196` 的单页文字叠压另行修复，未分类来源图片的图文页不进入正例。原生入口继续标记实验性，S3 完成正式入口、可信来源与交付门禁后才可用于正式整稿。

## S3 必要交付门槛

正式完整稿要求封面、目录、至少一张章节页和封底，且章节使用同一 `layout_id`。目录条目数可读取时，必须与章节页数一致；目录四项只生成一张章节页会报 `DIRECTORY_SECTION_COUNT_MISMATCH`。组装前 `delivery_gate.py` 复验固定知识库清单、源文件哈希、组件来源页、填充单页哈希与标记；组装后检查包关系、页数和最终页关联。正常样本及缺目录、章节混用、伪造来源、坏包反例各跑一次即可，不重新验收知识库全部组件。`run_presentation.py` 的 `status=ready` 只表示候选生成；成稿另报告 `delivery_status`，未做人工视觉复核时保持 `pending_visual_review`。Mac PowerPoint 与真实材料三风格整稿仍待验证。

## S4 字体配置与渲染校准

完整出稿请求可设置 `font_profile` 为 `windows`、`macos` 或 `linux`。省略时按当前系统选择；整个任务的填充、技能新绘、组装归一、字体审计和报告使用同一配置。当前配置为 Windows 微软雅黑／Arial、macOS 苹方／Helvetica Neue、Linux Noto Sans CJK SC／Noto Sans。缺少字体时完整出稿阻断并指出缺失字体，不静默回退。不同系统原生字体须分别生成和验收 PPTX，不能期待同一文件自动切换字体。源知识库不改写；仅处理任务副本。对已通过 Windows 字体容量验收的组件，换字体后仍须复核窄槽、表格及接近容量上限的文案。

`scripts/font_profile.py --profile <配置> --out <诊断.json>` 只检查字体资源。`scripts/calibrate_renderer.py --profile <配置> --fixture <已知正常样本.pptx> --out-dir <目录>` 先复制样本、归一与审计字体，再用本机 PowerPoint 或 Linux LibreOffice 导出逐页图，并记录源文件哈希、渲染应用版本、页数、用时和失败页。每次可重复指定 `--fixture`。报告的 `rendered_pending_visual_review` 只代表导出完成；需打开生成的 PNG 做文字边界、缺字、重叠、Logo、背景、图表及透明素材的人工检查。LibreOffice 的图形效果结果不能替代 PowerPoint 的打开或渲染结论，Quick Look 只能作预览。

Linux 任务副本中，LibreOffice 不能正确显示的可编辑文字渐变会转换成其最亮可见色标的纯色；转换次数写入 `font_normalization.gradient_text_fallbacks`。此适配只处理 Linux 输出，不修改知识库原稿，也不改变 Windows/Mac 文件。其视觉颜色仍须与目标应用逐页复核；渐变效果本身不会在 Linux 版本中保留。

Mac 实机已在字体检测修复后完成安装和 `doctor --goal fill`，早期 22 页候选 PPTX 可由 Keynote 打开；随后用户确认最新技能 `23e32c5` 与知识库 `58d4977` 的 macOS 测试效果通过。安装适配和代表性出稿可按用户反馈记为通过。目标应用、版本和逐页导出证据尚未归档时，不将该反馈扩大为 PowerPoint 全量视觉验收。复测应使用安装器记录的解释器，不手写运行时记录或改用系统默认 Python 绕过门禁。

旧 Mac 候选文件为 96.84 MiB，压缩后的嵌入字体部件占 78.86 MiB，是体积的主要来源。知识库 `sources/cover.pptx` 已移除旧字体部件并更新哈希；任务副本归一字体时也会清除旧嵌入，避免历史缓存继续放大成稿。旧 22 页稿的副本实测降至 17.98 MiB，字体审计 195 个文本运行项通过，在本机 Windows PowerPoint 导出的 22 页逐像素一致。此结果不替代 Mac 目标应用复核，仍须检查字形、换行、柔边和可编辑性。旧源稿 SHA-256 保留在知识库 `source-manifest.json`，运行时不得绕过当前清单校验。

## S5 显式实验整稿入口

Linux 安装并自检后，可在已校验的知识库快照上运行：

```sh
<Python> scripts/run_presentation.py --request <逐页请求.json> --library <知识库目录> --out <报告.json> --plan-out <计划.json> --execute-out <成稿.pptx> --native-experimental
```

此参数只切换组装后端；候选筛选、真实字段试填、结构页完整性、来源校验、任务字体归一和最终审计仍执行。输出报告中的 `assembly_backend=native_experimental`、`execution.assembly_status`、`execution.static_audit_status`、`execution.render_status` 与 `delivery_status` 要分别读取。LibreOffice 逐页渲染成功后仍为 `pending_visual_review`；应检查实际 PNG，并用目标 PowerPoint/WPS 打开或导出。macOS 自动预览当前标为 `pending_manual`，需在目标编辑器中逐页导出和检查。渲染失败时保留已通过组装及静态审计的候选 PPTX，交付状态为 `pending_render`，不能报已完成。找不到渲染器时同样不能把视觉状态标为通过。缺结构页、缺字体或未显式启用后端时继续阻断完整稿。

macOS/Linux 已完成候选入口的代表性实测，仍使用 `--native-experimental`；是否将其转为正式发布能力，要另行确定支持范围、发布归档和目标应用视觉验收口径。S5 真实材料及用户 macOS 实测结论以对应验收记录为准。
