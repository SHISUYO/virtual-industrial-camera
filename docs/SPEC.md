# Virtual Industrial Camera (VIC)
## GenTL 虚拟工业相机 — 开发需求规范 v1.0

### 1. 项目介绍
开发运行于 Windows x64 的虚拟工业相机系统。无需真实工业相机硬件，通过自研 GenTL Producer（.cti）向标准 GenTL Consumer 提供虚拟设备、GenICam 参数及图像数据流。
首要目标 Consumer 为 Python Harvester，第二目标为 HALCON 24.11 的 GenICamTL 图像采集接口。
注意：本项目不是 Windows DirectShow/Media Foundation 虚拟摄像头，也不是 GigE Vision 网络相机模拟器。GigE Vision 扩展参见 docs/GIGE.md。

### 2. 技术约束
- 操作系统：Windows 10/11 x64
- 核心：C++17、MSVC、CMake
- 标准：GenTL 1.6、GenICam GenApi、SFNC、PFNC
- 图像处理：OpenCV 4.x
- GUI：Python 3.11、PySide6
- 外部测试：Harvester、HALCON 24.11
- 构建架构：x64 Release / Debug
- UTF-8 源文件，外部标准 ABI 按规范实现
- 不使用未经授权的商业 SDK 或专有协议

### 3. 项目模块
VIC Producer：GenTL ABI、System/Interface/Device/DataStream、设备发现、设备访问、GenICam XML、Buffer 和事件。
VIC Engine：图像输入、图像格式转换、帧率控制、触发状态机、帧数据和故障模拟。
VIC Control：设备身份设置、图像源、运行状态、图像预览、日志和故障模拟参数。
VIC Tests：C++ 单元测试、GenTL ABI 测试、Harvester 集成测试、HALCON 测试脚本和测试结果。

### 4. 模拟设备身份
- Vendor: VIC Project
- Model: VIC-1000
- SerialNumber: VIC000001
- UserDefinedName: Virtual Camera 01
- DeviceID: VIC-DEVICE-0001
- 初始相机数量：1 台，预留扩展 4 台
身份参数应持久化，设备 ID 和序列号应稳定。修改后通过明确的设备重建/重新枚举生效，禁止在设备已打开时直接改变识别 ID。

### 5. GenTL 功能需求
按照官方 GenTL 1.6 标准实现：
- ABI 入口与初始化、关闭
- Producer/System、Interface、Device、DataStream 的发现、打开及关闭
- 设备信息查询
- Buffer 公告、分配、撤销、队列
- 开始/停止采集、New Buffer 事件与必要的事件等待
- 图像宽高、像素格式、填充大小、FrameID、Timestamp
- 正确返回码及线程级错误描述
- GenICam XML 与 Remote Device 的参数访问
- 资源和 Handle 生命周期管理
不能只导出空函数伪装兼容。标准允许但未实现的可选能力应按规范返回 Unsupported，不得虚报成功。

### 6. GenICam 参数
- DeviceVendorName、DeviceModelName、DeviceSerialNumber、DeviceUserID
- Width、Height、PixelFormat、PayloadSize
- AcquisitionMode、AcquisitionStart、AcquisitionStop、AcquisitionFrameRate
- TriggerSelector、TriggerMode、TriggerSource、TriggerSoftware
首版仅 Mono8 / RGB8；采用正式 PFNC 定义，RGB8 为 RGB 顺序而非 OpenCV BGR。参数必须对应真实状态。XML 必须遵守官方 Schema，Remote Device Port 提供合法读取与访问机制，GenApi 可以解析节点并执行 Command。

### 7. 图像输入
支持单张 JPG/PNG/BMP、多张图片序列循环、视频逐帧、指定输出 FPS、Mono8/RGB8 转换。
图像尺寸不一致时提供缩放及保持比例补边，避免变形。图像缺失、损坏、视频读取失败时返回明确错误，不得导致 CTI 崩溃。

### 8. 采集与触发
Continuous：AcquisitionStart 后按 FPS 调度帧，AcquisitionStop 后停止交付；Buffer 由 Consumer 正确重新排队后才可复用。
Software Trigger：TriggerMode=On 且 TriggerSource=Software 时，TriggerSoftware 每次被接受的触发产生一次采集，未触发不产生新帧；支持可配置延迟、停止及未完成触发取消。
TriggerMode=Off 时按内部 FPS 运行。初始单流单设备独占。

### 9. Buffer 管理
- 消费者提供的内存按 GenTL 规则使用，不在其持有时覆盖
- Buffer 容量不足要返回规范错误
- FrameID、Timestamp、Width、Height、PixelFormat、PayloadSize 正确
- 紧凑布局：Mono8 PayloadSize = Width × Height；RGB8 = Width × Height × 3
- 交付、回收、撤销、销毁线程安全
- 有界队列，不得无界内存增长
- Stop、Close 后无悬挂线程、Handle 或内存泄漏

### 10. 故障模拟
固定触发延迟、额外采集延迟、指定帧丢弃、随机丢帧、取流超时、图像源耗尽、可控随机种子。
明确区分传感器侧未产生/丢弃帧、已产生未交付帧、Consumer 等待超时；不能全部简单用 sleep 代替。记录原因、帧号和统计。

### 11. GUI
PySide6 独立控制程序，支持设备身份、图像源、分辨率、像素格式、FPS、连续/软件触发、手动触发、预览、Consumer 连接状态、产生/交付/丢弃帧数、两类 FPS、故障参数、日志和配置持久化。
GUI 不实现 GenTL ABI；GUI 退出不应使正在工作的 Consumer 崩溃。

### 12. IPC 与架构
Producer 和 Engine 优先抽象为稳定 C++ API；Engine 独立时使用 Named Pipe 控制和 Shared Memory 交换大帧，具备协议版本、长度、DeviceID、RequestID、错误码。
考虑服务未启动、中途退出、Consumer 意外退出、重连、超时、通道关闭及帧数据覆盖。
首阶段允许进程内 Engine Stub，后续再实现跨进程 IPC。

### 13. 日志
结构化记录：时间、线程 ID、设备 ID、GenTL API、事件、FrameID、耗时、错误码和描述；同时输出文件与 GUI 日志；不得每帧同步写盘阻塞采集。

### 14. 工程交付
完整源码、CMake、x64 CTI、GUI、示例图片、配置、Harvester 测试、HALCON 脚本/说明、README、BUILD.md、TESTING.md、KNOWN_ISSUES.md、CHANGELOG、自动化测试报告。所有兼容声明应有实测依据。

### 15. 最终验收
1. CTI 在 Windows x64 正常加载。
2. Harvester 发现设备、读取节点。
3. Mono8 及 RGB8 各连续取 1000 帧。
4. 图像和输入一致（按约定处理）。
5. 无触发时无新帧。
6. 图片序列循环、视频按指定 FPS 输出。
7. GUI 显示真实预览与日志。
8. 故障注入可观察、可恢复。
9. HALCON GenICamTL 实测发现、打开、取流。
10. Stop/Close/Restart 不崩溃；连续运行一小时无明显泄漏、死锁。
兼容 HALCON 必须实际运行才可标 PASS。

### 16. Codex 工作准则
每次只实现一个阶段，每阶段须可编译、可运行、可测试；采用官方规范/头文件，不猜 ABI。Mock 不代替外部 Consumer 测试。无法验证标记 NOT TESTED；不硬编码测试成功；每阶段更新 README、CHANGELOG、测试报告并提交 Git Commit；遇到兼容问题调查规范而不是伪造行为。
