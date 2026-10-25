# GitHub 发布准备

这份说明用于整理公开源码；**尚未创建或推送 GitHub 仓库**。当前开发仓库已跟踪数千个历史测试证据，其中有超过 GitHub 单文件限制的 PCAP、诊断 ZIP 与本机路径。只在当前分支删除文件并直接推送，旧提交中的数据仍会进入公开历史或导致推送失败。

## 生成干净源码快照

在项目根目录运行：

```powershell
./scripts/prepare-github-snapshot.ps1
```

默认输出 `out/github-public-snapshot/`。脚本只复制源码、核心设计文档、自动化测试源码、构建/安装脚本和许可证；若目标目录已存在会停止，不会删除或覆盖。它对候选文本检查本机用户路径和常见 GitHub token 形态，并拒绝大于 50 MiB 的单文件。开发仓库、`tests/evidence/`、`tests/manual/`、`log/`、`out/`、`PROJECT_STATUS.md` 与旧 Git 历史仍保留在本机。

检查快照后，在该目录**单独**初始化新 Git 仓库，再关联新建的 GitHub 仓库。不要把当前开发仓库直接作为公开仓库推送，也不要在公开快照中复制 `.git/`。安装包放到 GitHub Releases，不放入 Git 文件历史。

## 构建限制

- `CMakeLists.txt` 需要外部 OpenCV 4.12 SDK，并仍有固定 DLL 文件名；全新克隆的依赖获取尚未自动化。
- `scripts/09-package.ps1` 目前复用开发环境 `out/` 中先前构建的 Engine、GigE 和 OpenCV DLL；`scripts/09-installer.ps1` 在前一步发布目录存在时才能工作。公开快照可阅读与改进源码，但尚不能从零一键制作安装包。
- 现有安装包无代码签名。TAP 驱动、Cognex VisionPro 与 HALCON 均不随仓库或安装包分发。
- GPL-3.0-only 适用于本项目源码；发布含 PySide6/Qt、OpenCV、Python 和 Windows App SDK 的二进制前，需逐项核对随附许可证、源代码与再分发要求。第三方说明见 `control/THIRD_PARTY_NOTICES.md` 和 `poc/tap-camera/third_party/NOTICE.md`。
- WinUI 安装版在真实 VisionPro 中的发现、打开、采图、触发和重连尚待用户验收；公开说明不得将其写成已通过。

## 发布前核对

1. 审阅快照中的源代码、许可证和 README；搜索私有路径、令牌及不准备公开的资源。
2. 在干净的 Windows x64 环境补齐构建依赖并完成构建/测试；记录尚未复测的项目。
3. 用户完成 WinUI 安装版与 VisionPro 的手动验收后，再决定发布标签和二进制 Release 描述。
4. 推送新的快照仓库；开发仓库及其抓包历史继续私有保存。
