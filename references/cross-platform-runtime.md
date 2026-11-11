# 跨系统运行：S1 候选实现

本轮解决发布字节校验、隔离依赖安装、独立自检及知识库缓存迁移。非 Windows 的完整 PPTX 组装仍待 S2，不得把安装成功或自检通过当成 Mac/Linux 整稿支持。

## 安装与运行

需要可执行的 Python 3.10 或更高版本。Windows 在技能根目录执行 `powershell -File .\install.ps1`；macOS/Linux 执行 `sh ./install.sh`。启动器会实际运行候选 Python，不要求用户机械替换 python/python3。

安装器创建用户状态目录下的版本化虚拟环境；完成依赖和本地模板包校验后才原子更新 `runtime.json`。失败保留先前的活动解释器，重复安装复用同一依赖版本环境。安装器使用系统文件锁，崩溃退出后锁可自动释放。核心直接依赖记录于 `requirements-core.txt`，实际安装的直接和间接依赖版本记录在 `runtime.json`。不同 OS/架构仍需实测，不因依赖能安装就声明完整支持。

安装到指定位置：两个安装脚本都支持 `--state-dir <目录>`。后续设置 `EPOINT_STATE_DIR` 为同一目录，再用启动器选中的 Python 执行 `scripts/run.py`。该入口读取活动解释器，转调原有统一工作流并原样传递参数。旧入口仍可使用，但须自行指定正确解释器。

离线依赖安装支持 `--wheelhouse <目录>`，仅从提供的兼容 wheel 目录安装。模板离线包不包含 Python/Office/字体安装包；首次断网且没有兼容 wheels 时，应报告依赖安装失败，不伪报就绪。安装器不修改全局 Python 或系统代理。

回退时先验证记录中的 `previous_python` 存在，再使用该解释器直接调用统一入口；旧环境不会被安装器删除。本轮未提供自动卸载或一键回退命令。

## 自检

`<Python> scripts/run_presentation.py --doctor --out runtime-report.json`

也可直接执行 `<Python> scripts/doctor.py`。自检只用标准库启动；依赖导入放在有超时限制的子进程内，缺少 pptx/Pillow 时仍输出 JSON。`--library` 指定待校验知识库，默认校验安装包内最小模板包。

- `--goal inspect`：校验环境和模板包。可选依赖缺失会报告，但不阻断检查本身。
- `--goal fill`：另外要求核心 Python 包能导入；不代表已经完成实际单页或视觉验收。
- `--goal assemble`：要求已验证的整稿后端。本轮尚未实现深度后端冒烟测试，Windows 检出 COM 也标记 `untested`，不会据此宣称整稿验收通过。

显式添加 `--deep` 时，在指定用户状态目录及缓存目录写入并读取临时文件，并用当前 Python 创建一页含中文可编辑文本的 PPTX，保存后重开核对。`--state-dir` 与 `EPOINT_CACHE_DIR` 可指定这些检查使用的目录；检查报告的 `deep_checks` 记录结果。此检查验证写入与 PPTX 基础往返，不代表已有模板的合并、目标 Office 打开、导出或视觉验收。

结果区分 available、unavailable、untested，stdout 仅输出 ASCII 安全的机器 JSON；报告文件为 UTF-8。基础自检不会启动 Office、自动上传材料、安装依赖或调整网络设置。字体、实际渲染、应用打开与导出、网络连通性主动探测仍待后续补齐。

## 分发与校验

源码文本采用 `.gitattributes` 定义的 LF 规范；Windows PowerShell 脚本保留 UTF-8 BOM；二进制不转换。发布者在隔离工作区先暂存拟分发的新文件，再执行：

```text
<Python> scripts/prepare_distribution.py --root <技能根目录> --manifest-root <技能根目录>/assets/minimal-template-pack --write
<Python> scripts/prepare_distribution.py --root <知识库根目录> --write
```

不带 `--write` 时只校验。重建清单只包含 Git 已跟踪/已暂存文件，防止把验证产物或工作区杂项混入发布包。`update_knowledge_manifest.py` 同样采用该规则；不再自动吸收未跟踪文件。

运行时校验只计算原始文件字节哈希，不自动修复、改写或忽略换行差异。跨平台修复必须发新版本，不覆盖旧标签。本轮代码位于独立开发工作区，尚未更新远端发布版。

## 知识库缓存与升级

知识库默认缓存位于用户状态目录下的 `cache/libraries/<来源标识>/`，可以通过 `EPOINT_CACHE_DIR` 指定其他可写目录。来源标识区分仓库 URL、分支、库内路径和知识库版本；不依赖当前工作目录。状态目录由 `EPOINT_STATE_DIR` 或系统用户目录决定。

在线解析先查询远端提交，再下载到候选目录；完整校验原始文件哈希、来源及提交后，将目录保存为 `snapshots/<commit>/`，原子更新 `last-good.json`。下载采用包含当前提交全部文件的浅克隆，不使用延迟下载 blob 的部分克隆。并发更新使用系统文件锁；进程异常退出会释放锁，不以锁文件存在判断占用。

更新失败保留上次有效快照及记录。显式 `--offline` 不连接远端；优先复验当前完整快照，损坏时尝试记录中的上一有效快照，然后尝试旧版完整缓存，最后使用技能自带最小包。每次回退保留原因，不把坏缓存标为有效。旧版安装目录附近的缓存只读兼容，不再更新或覆盖它。

在线成功不再重建安装目录内的最小包；新的完整快照本身支持离线调用。最小包仅在发布构建时更新，继续作为首次离线的补救措施，不扩充模板数量。旧快照当前不会自动删除，避免删除正在被其他出稿任务引用的版本。

错误区分代理 `git_proxy`、TLS `git_tls`、认证权限 `git_permission`、网络 `git_network`、超时 `git_timeout`、Git 缺失及清单/缓存异常；不改变系统代理或关闭证书校验。在线失败不代表所有离线能力不可用，报告以实际采用的来源和提交为准。

## 本轮边界

已抽取公共路径与进程模块并用于新自检和安装器；知识库更新已迁入用户缓存，缓存子流程完成 Windows 与 WSL Linux 的更新、回退、并发和故障验证。Linux 已实测只读安装目录，Windows 已检查安装文件无变更；尚未据此宣称完整出稿工作流均支持只读安装。离线依赖安装矩阵、失败运行环境升级、深度环境自检、原生模板组装和系统字体配置仍按计划推进。macOS 仍待用户实机验证。

## S2 原生组装试点

`scripts/assemble_native.py --experimental --first <已填充单页1.pptx> --second <已填充单页2.pptx> --out <输出.pptx>` 是仅支持两张单页的隔离试点，不接入统一出稿入口。它复制源部件及其关系，仅向演示文稿登记两页实际使用的母版；对已测试的蓝色目录＋章节样本，可在 Linux 生成，并由 Windows PowerPoint 打开及导出。试点没有完成通用图表、表格、字体、媒体和来源门禁，不得将它作为正式整稿后端或跳过原有组装阻断。

试点增加 `scripts/audit_native_package.py --input <两页包> --sources <源页1> <源页2> --out <JSON>`，检查包内 XML、部件关系、内容类型、实际使用母版、母版及版式全局 ID、两页源文本及来源标记。它能拒绝多余母版、重复版式 ID、缺失版式和源页 XML 被改动的负例。红色和科技风结构页试点分别暴露了复制版式 ID 冲突及第二个备注母版冲突；修正后，两套两页包均由 Windows PowerPoint 16.0 打开并逐页导出。**静态检查仍不等于 PowerPoint 兼容性验收**，每一类新对象组合都要另外执行目标 Office 打开、逐页导出及视觉复核，不能据包审计结果直接放行正式整稿。
