# VIC — GigE Vision 扩展开发任务书 v1.1

## 1. 开发目标
在 Virtual Industrial Camera 中增加 GigE Vision 相机模拟，目标是 Cognex VisionPro 9.x（以实际安装版本为准）经原生 GigE Vision Acquisition 发现、连接和取图。保留 VICGenTL.cti、HALCON 与 Harvester 兼容目标。实际兼容必须测试，不能从协议完成度直接推定。

## 2. 总体架构
- VIC Core：虚拟相机、帧、参数、采集状态机
- VIC GenTL：现有 Producer
- VIC GigE：新增 GigE Vision 协议服务
- VIC Control：PySide6 GUI
- VIC Tests：协议与外部软件兼容性测试
共用 Core，外部传输路径独立；不可把 GigE Vision 简化成随意 TCP 图像传输。

## 3. 核心协议
### GVCP
依正式 GigE Vision 标准实现 Discovery、ReadReg、WriteReg、ReadMem、必要的 WriteMem、Bootstrap Register、控制权限、心跳、设备信息、Stream Channel。GVCP 默认 UDP 端口 3956。网络字节序、字段长度、偏移、flags、request ID 必须遵循规范；不能猜命令号或寄存器地址。
### GVSP
实现 Leader、Payload、Trailer、BlockID、PacketID、PixelFormat、Timestamp、Width/Height、Packet Size、Frame Transmission 与正确停止。首版非压缩、无 Padding、非分块 Mono8/RGB8。正确分包与包 ID 递增，不得自创 UDP 图像格式。
### GenICam
提供可被 GenApi 解析的标准 XML，节点包括：DeviceVendorName、DeviceModelName、DeviceSerialNumber、DeviceUserID、Width、Height、PixelFormat、PayloadSize、AcquisitionMode、AcquisitionStart、AcquisitionStop、AcquisitionFrameRate、TriggerMode、TriggerSource、TriggerSoftware、GevSCDA、GevSCPHostPort、GevSCPSPacketSize；AcquisitionFrameRateAbs 仅在实际兼容需要时增加正确映射。XML 与 GVCP 寄存器状态一致。

## 4. 虚拟网络设备
- Vendor: VIC Project
- Model: VIC-1000-GE
- Serial: VICGE000001
- Transport: GigE Vision
- Default Format: Mono8
- Default Resolution: 640×480
- Default FPS: 30
可选 IPv4 网卡与绑定 IP；对发现广播和单播控制作出正确响应。不得冒用他人厂商 MAC/OUI，也不得擅改物理网卡 MAC；对纯用户态模拟独立二层相机身份的限制如实报告。

## 5. 图像流
复用 VIC Core 图片与视频：单张 JPG/PNG/BMP、图片序列循环、视频逐帧、Mono8/RGB8、连续采集、软件触发、自定义 FPS、可配置触发延迟。AcquisitionStart 后按触发模式发帧；仅在 Stream Channel 及控制/采集状态有效时发送；GVSP 目标 IP/端口来自 Consumer 配置，禁止硬编码。

## 6. 网络故障模拟
GVSP Packet Loss、Frame Loss、Packet Delay、可选 Reordering、第二阶段 Packet Resend、Heartbeat Timeout、Control Disconnect。分别统计丢包和丢帧，可控随机种子，测试可复现。

## 7. Windows x64
C++17、MSVC、CMake、Winsock2；可选择本机网卡，不默认绑定所有接口；不得强行禁用整个 Windows Firewall。诊断显示绑定 IP、GVCP 收包/Discovery 计数、寄存器访问、GVSP 目的地址端口、发包成功失败数、交付帧数、流状态、网络错误码。
单机 VisionPro+VICGigE 为目标拓扑；出现问题用抓包与双机对照区分协议和网络路径，不能武断归因于 Loopback。

## 8. 与 GenTL 的关系
保留 VICGenTL.cti。VisionPro 原生 GigE 路径不依赖自定义 CTI。两条路径共享引擎和图像源，但需定义控制权限和订阅机制。首版允许只有一个 Consumer 控制/采集设备，不承诺多客户端并行取流。

## 9. VisionPro 验收
1. GigE Configuration Tool 发现 VIC-1000-GE。
2. 读取 Vendor、Model、Serial。
3. QuickBuild Acquisition 能选择设备。
4. 创建采集 FIFO。
5. Mono8 正确取图。
6. RGB8 正确取图。
7. Continuous 正确采集。
8. 软件触发正确运行。
9. 图像内容与源图一致。
10. 停止、断开、重连恢复。
逐项记录 PASS、FAIL、NOT TESTED；只发现设备不等于兼容性成功。

## 10. 开发规则
每阶段编译/测试；不得破坏 GenTL；先 Mono8 后 RGB8；协议字段需要官方参考；保留 Wireshark 抓包方法；失败需日志定位；缺少正式规范时列出受限功能；每阶段 Git Commit，维护 CHANGELOG/TESTING.md；未在 VisionPro 真实测试不得宣称通过。
