# 跨系统运行：S1 候选实现

本轮解决发布字节校验、隔离依赖安装和独立自检。非 Windows 的完整 PPTX 组装仍待 S2，不得把安装成功或自检通过当成 Mac/Linux 整稿支持。

## 安装与运行

需要可执行的 Python 3.10 或更高版本。Windows 在技能根目录执行 `powershell -File .\install.ps1`；macOS/Linux 执行 `sh ./install.sh`。启动器会实际运行候选 Python，不要求用户机械替换 python/python3。

安装器创建用户状态目录下的版本化虚拟环境；完成依赖和本地模板包校验后才原子更新 `runtime.json`。失败保留先前的活动解释器，重复安装复用同一依赖版本环境。核心直接依赖记录于 `requirements-core.txt`，实际安装的直接和间接依赖版本记录在 `runtime.json`。不同 OS/架构仍需实测，不因依赖能安装就声明完整支持。

安装到指定位置：两个安装脚本都支持 `--state-dir <目录>`。后续设置 `EPOINT_STATE_DIR` 为同一目录，再用启动器选中的 Python 执行 `scripts/run.py`。该入口读取活动解释器，转调原有统一工作流并原样传递参数。旧入口仍可使用，但须自行指定正确解释器。

离线依赖安装支持 `--wheelhouse <目录>`，仅从提供的兼容 wheel 目录安装。模板离线包不包含 Python/Office/字体安装包；首次断网且没有兼容 wheels 时，应报告依赖安装失败，不伪报就绪。安装器不修改全局 Python 或系统代理。

回退时先验证记录中的 `previous_python` 存在，再使用该解释器直接调用统一入口；旧环境不会被安装器删除。本轮未提供自动卸载或一键回退命令。

## 自检

`<Python> scripts/run_presentation.py --doctor --out runtime-report.json`

也可直接执行 `<Python> scripts/doctor.py`。自检只用标准库启动；依赖导入放在有超时限制的子进程内，缺少 pptx/Pillow 时仍输出 JSON。`--library` 指定待校验知识库，默认校验安装包内最小模板包。

- `--goal inspect`：校验环境和模板包。可选依赖缺失会报告，但不阻断检查本身。
- `--goal fill`：另外要求核心 Python 包能导入；不代表已经完成实际单页或视觉验收。
- `--goal assemble`：要求已验证的整稿后端。本轮尚未实现深度后端冒烟测试，Windows 检出 COM 也标记 `untested`，不会据此宣称整稿验收通过。

结果区分 available、unavailable、untested，stdout 仅输出 ASCII 安全的机器 JSON；报告文件为 UTF-8。不会启动 Office、自动上传材料、安装依赖或调整网络设置。字体、实际渲染、可写目录深测和网络连通性主动探测仍待后续补齐。

## 分发与校验

源码文本采用 `.gitattributes` 定义的 LF 规范；Windows PowerShell 脚本保留 UTF-8 BOM；二进制不转换。发布者在隔离工作区先暂存拟分发的新文件，再执行：

```text
<Python> scripts/prepare_distribution.py --root <技能根目录> --manifest-root <技能根目录>/assets/minimal-template-pack --write
<Python> scripts/prepare_distribution.py --root <知识库根目录> --write
```

不带 `--write` 时只校验。重建清单只包含 Git 已跟踪/已暂存文件，防止把验证产物或工作区杂项混入发布包。`update_knowledge_manifest.py` 同样采用该规则；不再自动吸收未跟踪文件。

运行时校验只计算原始文件字节哈希，不自动修复、改写或忽略换行差异。跨平台修复必须发新版本，不覆盖旧标签。本轮代码位于独立开发工作区，尚未更新远端发布版。

## 本轮边界

已抽取公共路径与进程模块并用于新自检和安装器；旧知识库缓存路径、在线自动更新最小包及其他业务脚本尚未全部迁移。只读安装目录下的完整在线工作流仍须继续改造验证。原生模板组装、深度渲染自检和系统字体配置按后续阶段推进。
