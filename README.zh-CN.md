<p align="center"><img src="assets/brand/logo.png" width="104" height="104" alt="OdenMap app icon"></p>
<h1 align="center">Oden ARC</h1>
<p align="center"><strong>把散落的资料，整理成清晰、可追溯的思维导图。</strong></p>
<p align="center">为 OdenMap 配套的开源 AI 技能与本地工具</p>
<p align="center"><a href="README.md">English</a> · 简体中文 · <a href="README.zh-TW.md">繁體中文</a></p>

Oden ARC 帮助 AI 助手把文档、图片、表格等资料整理成 **OdenMap** 原生思维导图，在精炼结论旁保留可编辑公式、资源卡片、备注与证据。

它由 **Agent Skill、命令行工具和可恢复的本地证据记忆**组成。AI 宿主负责理解材料，ARC 负责保存进度、校验引用、生成新的 `.odenmap` 文件。它不自带模型，也不要求单独配置模型 API 账号。

**[OdenMap 官网与 Mac 测试版](https://baojiachen0214.github.io/oden-website/)** · [开源仓库](https://github.com/baojiachen0214/oden-arc)

**OdenMap 是独立的闭源 Swift 原生应用。** 本仓库只开放配套技能、Python 工具、文档及合成示例，不开放软件本体。

## 为什么使用 ARC？

- **围绕问题组织。** 按读者需要理解、决定或执行的事情构图，而不是复制文件目录。
- **不止纯文本。** 图表、局部摘录、文档、表格与原生 LaTeX 可以共同构成导图。
- **证据不与结论脱节。** 关键限定、相反证据和未决问题不会为了简洁而消失。
- **中断后继续。** 本地工作区持久保存批次、租约、来源指纹与交接状态。
- **有目的地使用上下文。** 只取相关证据组；宿主明确保留内容时才省略重复正文。
- **不覆盖原件。** 在新目录生成交付物，校验后再由 OdenMap 打开。

```text
原始资料 → 证据与上下文 → MapPlan → OdenMap 原生文件与来源
              AI + 本地工具              确定性编译
```

## 快速开始

需要 **Python 3.10 或更高版本**。核心编译和记忆引擎仅使用标准库。在下载或克隆的仓库目录执行：

```sh
python3 scripts/arc.py capabilities
python3 scripts/arc.py preflight examples/quickstart/plan.json
python3 scripts/arc.py compile examples/quickstart/plan.json \
  --out ./my-first-map --strict-review
python3 scripts/arc.py validate-delivery ./my-first-map
```

使用 OdenMap 打开 `my-first-map/map.odenmap`，同时保留整个交付目录中的计划、来源副本和检查信息。每次生成都选择**尚不存在的输出目录**。

快速示例使用合成资料，无需联网、模型或可选依赖。安装、媒体扩展和大任务说明见 [入门指南](docs/getting-started.md)。

## 交给 AI 使用

把完整仓库目录交给 AI，让它先读取 [`SKILL.md`](SKILL.md)：

> 使用 Oden ARC，围绕我的目标整理这些资料。先读 SKILL.md，按需加载其他规范。保留关键条件和来源。大量资料使用持久工作区，每批处理后提交。最终交付新的 OdenMap 原生文件、来源与验证结果。

支持 Agent Skills 的宿主应加载**整个 `oden-arc/` 目录**，不是只复制一个 Markdown 文件。技能发现和安装方法由宿主决定，仓库不会自行写入全局技能目录。

小任务直接写 MapPlan 即可。长任务参阅 [持久记忆](references/memory-protocol.md) 和 [Context Atlas](references/context-atlas.md)。技能规范以英文维护，要求助手按照用户的语言生成内容。

## 能力范围

| 本项目提供 | 由宿主或其他工具提供 |
| --- | --- |
| 目标导向的提示词流程与审阅规则 | 模型推理、多模态理解 |
| 原生文件编译与静态校验 | OdenMap 显示、编辑与运行验收 |
| 批量记忆、恢复与证据检索 | OCR、语音转录、Office 解析 |
| 可选的图片/PDF 裁片及溯源 | Mermaid 渲染、活动内容沙箱 |

**ARC 是 Skill 与 CLI 工具，不是已经运行的 MCP 服务。** MCP 封装属于可扩展方向，不是当前已交付功能。

## 独立边界与隐私

这是 **OdenMap 的独立配套项目，不是应用源码**。公开适配器只实现生成其支持文件格式所需的数据结构，不包含应用的渲染器、交互画布、专有排版引擎或性能优化代码。导出位置估算是独立的通用回退实现。见 [架构](docs/architecture.md) 与 [格式说明](references/native-format.md)。

Python 工具不会主动联网或调用模型，但 **AI 宿主可能将你提供的材料发送给模型服务商**。工作区和备份含未加密的原件快照，应放在仓库之外，不要上传到公开 Issue。见 [安全说明](SECURITY.md)。

静态校验不证明事实正确，也不保证原生应用中的显示效果。实际使用前应在 OdenMap 中检查导图。本项目不宣称兼容所有模型宿主或已达到榜单最优。

## 文档与贡献

[文档导航](docs/README.md) · [示例](examples/README.md) · [贡献指南](CONTRIBUTING.md) · [测试](docs/testing.md) · [更新记录](CHANGELOG.md)

```sh
python3 scripts/run_tests.py
python3 scripts/audit_public.py
```

缺少可选媒体依赖时，相关测试会明确跳过。公开审查脚本只检查已定义的规则，不能保证未来任意贡献都不存在泄露风险。

## 许可

ARC 自有代码、提示词、文档及合成示例采用 [MIT 许可](LICENSE)，**不包含对 OdenMap 应用或第三方依赖的授权**。

可选 PDF 后端 **PyMuPDF** 采用 AGPL/商业双许可；使用、分发或集成前请阅读 [第三方依赖说明](THIRD_PARTY.md)。无依赖核心和仅图片安装不需要该后端。

`assets/brand/` 中的 OdenMap 图标为产品品牌素材，不在 ARC 的 MIT 授权范围内，见[品牌素材说明](assets/brand/README.md)。
