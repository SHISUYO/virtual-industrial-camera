# VIC：虚拟工业相机

## 项目介绍

VIC 是一款运行在 Windows 上的虚拟 GigE Vision 工业相机软件。你可以把**单张图片、图片文件夹或视频**作为画面来源，让其他软件像连接网络工业相机一样连接 VIC。也可以先在 VIC Control 中预览画面。

<img width="1586" height="893" alt="image" src="https://github.com/user-attachments/assets/2bbecfbc-43f9-4f48-8783-976e62c81b59" />

当前版本使用 WinUI 3 控制界面，支持 Mono8、RGB8、连续采集和软件触发。图片文件夹会按顺序循环播放。项目仍在开发中；MVS，VisionPro经过测试可正常取图

## 项目依赖

- **运行环境：**Windows 10/11 x64。要让同一台电脑上的 VisionPro 通过 GigE Vision 连接 VIC，需要单独部署 TAP-Windows6 虚拟网卡；VIC 不会安装驱动或修改网络设置。
- **从源码构建：**MSVC、CMake、OpenCV 4.12、.NET 9 SDK、Python 3.12，以及 [`control/requirements.txt`](control/requirements.txt) 中的依赖。制作安装包还需要 Inno Setup 6。

## 软件手册

1. **选择画面：**打开“图像源”，选择“单张图片”“图片文件夹”或“视频”，点击“选择文件”或“选择文件夹”。需要时点击“读取来源分辨率”，然后点击“应用并预览此来源”。
2. **本地预览：**在“采集参数”中选择分辨率、像素格式和采集模式，点击“应用配置”及“开始预览采集”。选择“软件触发”时，每次点击“软件触发”获取下一帧。
3. **连接 VisionPro：**确认专用 TAP 网卡已部署，点击顶部“启动相机”，再到 VisionPro 中分别检查设备发现、打开和取图。界面显示“GigE 已发布”只表示 VIC 后台已启动，**不代表 VisionPro 已收到有效图像**。
4. **结束：**点击“停止采集”结束本地预览；点击顶部“停止相机”结束 GigE 相机。

VIC 源码采用 [GPL-3.0-only](LICENSE)。第三方组件与发布限制见 [`docs/PUBLISHING.md`](docs/PUBLISHING.md)。
