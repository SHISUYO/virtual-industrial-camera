# Virtual Industrial Camera (VIC)

VIC 是面向 Windows x64 的虚拟 GigE Vision 工业相机实验项目。现有实现包含 GVCP/GVSP 相机后台、图片/图片集/视频来源、本地采集 Engine，以及原生 WinUI 3 控制界面。GigE 模式使用单独安装的 TAP-Windows6 虚拟网卡；仓库和 VIC 安装包均不包含 TAP 驱动。

## 当前状态

| 项目 | 状态 |
|---|---|
| WinUI 3 控制界面 `09-0.1.0` | 已构建并完成本地预览、GigE 后台启停及安装/卸载自动检查；等待用户手动验收 |
| Cognex VisionPro | 曾在指定测试环境下验证部分 SDK 取图路径；**当前 WinUI 安装版的发现、打开和有效帧尚未完成手动验收** |
| GenTL Producer `.cti` | 尚未实现；不得据此声称 Harvester 或 HALCON 兼容 |
| Windows Sandbox 路径 | 已有可运行基准，保留在开发记录中 |

“发现设备”“打开设备”“开始采集”和“取得有效图像”是四项独立结果。具体阶段状态见开发仓库中的 `PROJECT_STATUS.md`；公开源码快照不包含本机抓包和个人诊断记录。

## 目录

| 路径 | 内容 |
|---|---|
| `src/core/`、`src/gige/` | 共享相机核心、GVCP/GVSP 实现 |
| `src/control06/`、`control/` | 本地 Engine、Python 桥接及控制界面 |
| `control/winui09/` | 原生 WinUI 3 前端 |
| `poc/tap-camera/` | TAP 用户态虚拟网络端点 |
| `installer/` | WinUI 安装器脚本与简体中文向导资源 |
| `scripts/` | 构建、打包和开发测试入口 |
| `tests/automated/` | 自动化测试源码 |
| `docs/SPEC.md`、`docs/GIGE.md` | 项目规格及 GigE 设计资料 |

## 构建与运行

目标系统为 Windows 10/11 x64。源码构建使用 CMake、MSVC C++17、OpenCV 4.12、.NET 9 SDK、Python 3.12，以及 `control/requirements.txt` 中的 Python 依赖。制作安装器另需 Inno Setup 6。运行 GigE 模式需事先部署兼容的 TAP-Windows6 网卡；程序不会自动安装驱动或修改宿主网络配置。

现有 `scripts/09-package.ps1`、`scripts/09-installer.ps1` 已在开发环境验证，但前者目前复用 `out/` 中先前构建的 Engine、GigE 和 OpenCV DLL。**全新克隆尚无一键完成 WinUI 安装包的构建流程**。源码构建依赖和已知限制见 [发布准备说明](docs/PUBLISHING.md)。`out/` 中的 EXE、DLL、安装包属于构建产物，不应提交到 Git；对外提供二进制时请使用 GitHub Releases。

## 许可证与第三方组件

VIC 项目源码采用 [GPL-3.0-only](LICENSE)。TAP 公共头文件的来源及许可见 `poc/tap-camera/third_party/NOTICE.md`；GUI 和打包依赖见 `control/THIRD_PARTY_NOTICES.md`。Cognex VisionPro、HALCON 和 TAP 驱动由使用者分别取得，不随本项目分发。

## 公开仓库与发布注意

本公开仓库由独立源码快照创建，未包含开发仓库的旧 Git 历史、大型 PCAP、诊断 ZIP 和本机日志。后续更新仍应使用 `scripts/prepare-github-snapshot.ps1` 生成并检查源码快照，不要直接推送原开发仓库。二进制安装包尚未公开；许可核对与安装版 VisionPro 手动验收仍待完成。操作细节见 [发布准备说明](docs/PUBLISHING.md)。
