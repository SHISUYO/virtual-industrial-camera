# Changelog

## GitHub 发布前整理（待用户核对）

- 项目源码按用户选择加入 GPL-3.0；README 改为当前架构、状态和构建限制，补充发布指南与独立源码快照脚本。
- 开发仓库的本机证据和历史提交保持原样；新公开快照不含抓包、诊断 ZIP、构建产物和旧 Git 历史。尚未推送 GitHub，也未将 G05/VisionPro 验收标记通过。

## 09-0.1.0 安装版 — G05 WinUI 3（AWAITING MANUAL TEST）

- 为现有独立 WinUI 发布包增加当前用户的单文件 Inno Setup 安装器、简体中文向导、开始菜单入口及卸载；不安装 TAP 或修改系统网络。
- 隔离目录实际安装/启动/后端哈希/卸载测试通过。VisionPro 安装版人工取图待验收，安装包未签名。

## 09-0.1.0 — G05 原生 WinUI 3 控制界面（AWAITING MANUAL TEST）

- 新增独立 WinUI 3/XAML 前端与既有 Engine/GigE 控制器桥接；保留旧06.8/Sandbox发布包和同字节后端，不更改相机协议及系统网络。
- 按设计图实现七页导航、设备摘要、紧凑运行指标、真实本地预览、来源/参数编辑、日志与诊断导出；未提供的VisionPro指标明确标记，暂未实现的保存/全屏入口禁用。
- 发布/本地预览/旧GUI及CTest回归通过；两轮截图修正完成。新版GUI的VisionPro有效取图与主题/DPI人工验收待用户，见 `docs/G05_WINUI09_UI.md`。

## 06-0.6.8 — 示意图仪表盘（AWAITING MANUAL TEST）

- 按用户示意图将现有PySide6前端改为左侧导航、相机摘要、真实本地状态卡、实时预览、参数概览和底部常驻双日志。连接状态没有消费端数据时显示“未提供”。
- 独立新包复用06.7相同Engine/GigE后台；改前Git和用户文件备份已验证。GUI23项、CTest7项、PyInstaller/冻结截图通过；新界面的VisionPro人工取图待验收。

## 06-0.6.7 — 控制界面视觉改版（AWAITING MANUAL TEST）

- 基于现有PySide6界面采用Fluent风格卡片、明确的VisionPro主操作、状态标记、六页配置和固定预览区；不更改相机后台、网络协议、来源或控制行为。
- 改前Git bundle及未提交用户文件已备份；独立新包复用旧版原生后台。PyInstaller、GUI21项、CTest7项及冻结程序启动截图通过；新GUI在VisionPro中实际采图待人工。

## 06-0.6.6 — 大文件夹启动等待（AWAITING MANUAL TEST）

- 修复109张序列完整校验超过8秒后被前端判超时并停止：等待上限120秒、初始化提示、startup.json状态与时间记录，真正超时保留后台及诊断。
- 同一文件夹原失败复现；SDK3张大图及最终冻结GUI按钮启动通过。原生相机/Engine复用06.5同字节，网络配置/协议不变，旧包保留。

## 2026-10-23 — 06 文件夹序列启停后继续（AWAITING MANUAL TEST）

- 修复文件夹游标每次AcquisitionStart归零；同一Core内停止/重启、Consumer重连继续下一张，末张循环；重载来源/重启后台从首张开始。
- 新06-0.6.5包及旧Engine能力保护，视频行为和GVCP/GVSP/TAP算法不变。CTest7项、GUI21项、SDK普通/软件Mono/RGB共36帧顺序及全像素通过，QuickBuild人工待验收。

## 2026-10-23 — 06 QuickBuild取图参数恢复（AWAITING MANUAL TEST）

- 在真实QuickBuild复现AUTO_ABORTED并通过单变量对照确认：传输15000ms时Latency3失败、Latency0取图恢复。当前Mono单帧/实时成功，默认参数兼容仍FAIL。
- 仅修改消费端参数，保存独立新vpp（本机），补充可直接操作的中文三步指南及证据；VIC源码/系统网络/Sandbox不变，CTest6/6通过。

## 2026-10-23 — 06 TAP地址恢复（AWAITING MANUAL TEST）

- 经用户批准仅恢复既有专用TAP的10.203.0.1/24并持久保存；原ActiveStore配置不持久，现场地址缺失导致启动前检查失败。
- GUI06-0.6.4区分缺网卡与缺地址，诊断ZIP导出当前TAP身份/地址；不自动改网络。独立新包，原Sandbox/0.6.3保留。
- CTest6项、GUI21项、10项网卡/导出检查、真实SDK大图9帧全像素通过；实际重启后取图及QuickBuild人工仍待验收。

## 2026-10-23 — 06 分辨率 / 自动尺寸（AWAITING MANUAL TEST）

- 原1920×1080上限使5472等输入被拒绝末位；宽高范围同步扩展到6000、结束编辑提交。CameraCore/GVCP/XML/108MB RGB共享帧与能力握手同步。
- 默认选图/文件夹/视频时自动读取实际源尺寸，序列按排序首张；可关闭自动手输、显式读取，失败/超限不静默发布旧尺寸。不重复复制空闲的大预览。
- 新06目标大帧有界512写槽与控制服务；旧G05/Sandbox产物保留。真实SDK大图9帧四区域全像素通过，明确需传输超时15000ms/Latency0（普通FIFO Timeout30秒），默认大图失败仍记录。
- GUI/后台06-0.6.3独立新包；CTest6项、GUI21项、旧G05及保护测试通过。大图QuickBuild仍待人工验收。

## 2026-10-23 — 06 按钮点击丢失修复（AWAITING MANUAL TEST）

- 复现500ms状态刷新禁用按钮吞掉鼠标松开；后台查询不再禁用操作按钮，前台操作排队串行执行。
- 去除GigE发布对本地预览Engine版本/运行状态依赖，来源由既有GigE后台验证；保留本地预览升级保护，旧Engine提示不覆盖发布结果。
- GUI06-0.6.2独立06-button包；编译/CTest6项、GUI21项、真实SDK9帧及按钮事件回归通过。旧包保留，QuickBuild等待用户复测。

## 2026-10-23 — 06 来源切换与VisionPro入口修复（AWAITING MANUAL TEST）

- 复现并修复新配置仍显示旧共享测试帧；来源代次隔离、应用清图、自动文件类型与一键预览，旧Engine升级提示。
- 增加“启动/停止 VisionPro 相机”，将已验证图片/序列/视频配置传到独立TAP后台；保留原G05/Sandbox产物和协议传输路径，增加启动校验/来源快照/诊断PCAP。
- 名称/序列号的GigE ASCII15字符限制明确提示，新默认VIC Camera 01；发布期间锁定GUI来源，预览与网络计数分开。新包06-0.6.1，独立out/06-fix。
- MSVC/CTest6项、本地GUI21项及G05真实SDK回归通过；新来源SDK逐像素结果见TESTING.md和专项报告。QuickBuild人工验收待用户，GenTL仍BLOCKED，不推进下一阶段。

## 2026-10-23 — 06 PySide6控制面板（AWAITING MANUAL TEST）

- 用户澄清执行tasks/06.md；改前7.04GB逐文件校验备份、Git tag/bundle完成，独立feature/06-control；G05下拉框用户反馈人工通过。
- 新真实C++ Core本地Engine、命名管道/有界共享预览，六页GUI支持身份/来源/采集/触发/实时预览/模拟丢帧/配置/日志；GUI独立退出及重连接管。保留G05/TAP/Sandbox源码和原字节产物。
- CTest6/6、原生Windows/PS5.1/打包后台各21项GUI集成PASS，真实Mono/RGB像素、来源、错误恢复、在线改参、生命周期及诊断；独立Release自带依赖和样例。
- GenTL前置Producer/Harvester套件缺失，Consumer连接/交付/运行中改参BLOCKED；不以预览宣称兼容，阶段等待人工验收，不推进07。

## G05 GUI QComboBox修复（AWAITING MANUAL TEST）

- 数据检查及原生复现确认选中弹出行空白，局部QComboBox QSS明确普通/选中/悬停/禁用颜色，Qt标准QStyledItemDelegate替代菜单绘制；保留原模型及选中高亮，不改其他控件视觉。
- GUI版本G05-0.5.0-gui.1；新Release-combobox保留原Release/旧运行界面，TAP/协议/状态机/SDK逻辑及后端不变。
- Windows/offscreen DPR1/1.5、浅深浅应用方案、鼠标/键盘/禁用/真实文字像素测试及打包PASS；Windows系统主题/DPI切换留人工，更新专项指南/记录，G05仍待验收。

## 2026-10-23 — G05 VIC Control / 故障测试（AWAITING MANUAL TEST）

- 编码前完整逐SHA256备份及Git标签pre-g05-20261023_022003；独立feature/g05-control，原Sandbox/已验证TAP EXE不覆盖。
- 新PySide6 Control与独立TAP后台；启动停止/网卡只读选择/用户态相机IP、Packet Size/触发延迟/固定种子Payload丢包、GVCP/GVSP日志、真实生成/提交FPS和模拟丢弃计数、诊断ZIP/可选PCAP。GUI退出后台继续、重开接管停止，正常释放I/O；原GenTL目标保留为诚实未实现入口。
- Release自带Qt/Python，不需要用户安装依赖。修复原生深色主题下浅色界面文字不可读，实际截图重测。
- CTest5/5、真实SDK正常/100%预期故障/恢复/GUI进程退出期间图像、Aravis1314帧、稳定TAP与Sandbox各15帧回归PASS；PCAP正常19+恢复16帧完整/全像素；不改宿主网络或用户指定防火墙状态。
- 更新G05指南/实现报告/进度与路线，保留首轮等待条件FAIL、打包保护失败和原始截图；QuickBuild与冻结GUI人工验收NOT TESTED、GenTL回归BLOCKED，不宣称阶段PASS。

## 2026-10-23 — G04-D TAP GVSP 缺陷修复（AWAITING MANUAL TEST）

- 仍属G04；分支fix/g04-d-tap-gvsp、父dc06ac7，稳定Sandbox/旧研究refs不动。用固定64个稳定OVERLAPPED槽位替换逐包等待NDIS缓冲归还，去掉粗粒度Sleep；保留缓冲至完成/取消排空，不改协议字节或宿主网络配置。
- 相同构建深度1仍Cognex超时（Mono约2秒/帧），深度64 Mono3帧PASS（约39~47ms提交跨度）；TAP完整两轮各15帧，RGB/三次相机软件触发/连续/Stop/断开重连分别PASS。当前测试条件为用户已关闭并要求保留Private/Public防火墙；开启状态NOT TESTED，未自行改规则或开关。
- powershell.exe -NoProfile -File scripts/tap-poc-build.ps1 PASS/CTest1/1；python tests/automated/tap_poc_verify.py --out tests/evidence/G04-D/offline PASS；原CTest4/4 PASS；PS5.1新g04-d-check.ps1实际完整PASS、解析/版本保护、Python py_compile及非法写深度保护PASS。
- 真实PktMon/TAP PCAP分析：17帧完整、像素/MTU/校验和/序号/BlockID回绕通过，Stop ACK后GVSP为0；相机相关流未观察到旧drop。SDK图像不以PCAP代替。已保留深度1实际FAIL、R2旧失败及用户未跟踪日志。
- 原scripts/g04-check.ps1 Sandbox回归五组15帧PASS（G04/manual/20261023_013648），24项稳定源/脚本/EXE哈希不变；旧共享日志备份后恢复，新观察另存。
- 附件GVSP_TAP_DEBUG.md、指南tests/manual/G04_D_TAP.md；G04任务/状态/路线同步。G04未标PASS；TAP QuickBuild/小时长测/HALCON/Harvester NOT TESTED，等待用户验收，不进入G05。

## 2026-10-23 — R2/R3/R4 TAP真实部署（AWAITING MANUAL TEST）

- 用户批准后仅创建一个VIC-PoC-TAP，正式Microsoft签名9.27已加载；GUID/PnP/oem112.inf及精确回滚留档。首次Win32_PnPSignedDriver漏报保护停止已诊断，未重复安装；现有网卡/绑定/防火墙/安全策略不改。
- H=10.203.0.1/24，C=10.203.0.2只在用户态；仅新H的SkipAsSource true→false对照使Cognex控制面从ReadRegister超时变为参数/XML/FIFO/开始PASS。
- 真实SDK59.2.0.0五组有效图像FAIL：Mono/RGB超时，连续/软件/重连MISSING_PACKETS；停止/断开PASS。一条TriggerSoftware命令交付PASS，三帧触发验收FAIL。禁止兼容性成功声明。
- 两次PktMon真抓包及TAP实际PCAP保存；边界10帧像素正确不等于SDK交付。逐帧提交1.287~3.007秒，端点未找到/端口不可达/Inspection drop需进一步时序定位；未改防火墙或绑定来绕过失败。
- powershell.exe -NoProfile -File scripts/tap-poc-build.ps1 PASS/CTest1/1；tap-poc-check.ps1 PASS；out/network-research/build CTest4/4 PASS；PS5.1解析/Python py_compile PASS；tap_live_run.py --deployment tests/evidence/tap-r2/20261023_003814 最终真实SDK FAIL（live-20261023_004830），--network-only对照PASS；tap_capture_review.py真实抓包分析PASS。
- 增加受限部署/配置/抓包/复测/回滚辅助及docs/TAP_R2_R4_RESULTS.md、tests/manual/TAP_R2_LIVE.md。24项Sandbox基准哈希不变；回滚/Sandbox本轮重跑/GUI NOT TESTED。专用TAP保留、媒体断开；一条./scripts/tap-r2-check.ps1人工复测，待验收。

## 2026-10-23 — TAP/Wintun独立PoC（AWAITING MANUAL TEST / DEPLOYMENT APPROVAL）

- 分支research/tap-wintun-poc，基于3ee8c05；原master/基准标签及旧研究分支不动。24项既有源码/脚本/EXE哈希匹配；配置及Driver Store清单未变。
- 官方TAP9.27签名/CAT成员/内核策略验证PASS；Wintun0.14.1官网ZIP哈希及DLL签名PASS。驱动GPL、公开头MIT选项与Wintun预编译许可已分别记录，没有安装/加载驱动或关闭安全机制。
- 新增poc/tap-camera独立用户态Ethernet/ARP/IPv4/UDP适配，复用原GVCP/GVSP/Core；不改主入口。媒体激活须明确指定新GUID、专用名和许可标志，默认离线不打开网卡。
- `powershell.exe -NoProfile -File scripts/tap-poc-build.ps1` PASS（x64/C++17/CTest1/1）；`scripts/tap-poc-check.ps1` PS5.1 PASS，2148个UDP数据报与4帧全像素/错误帧/触发停重开及保护检查；最终manual/20261023_001226/。基准ctest4/4 PASS；初始编译失败保留并已修复。
- TAP I/O、NDIS抓包及真实VisionPro发现/打开/开始/有效帧NOT TESTED，安装新TAP及新接口IP需用户确认。报告TAP_WINTUN_FEASIBILITY.md，精简手动指南tests/manual/TAP_POC.md；不把synthetic pcap当真实抓包。


## 2026-10-22 — 同宿主网络架构研究（AWAITING MANUAL TEST）

- 调查前完成4.29GB全量备份/68,529文件SHA256比对PASS，Git基线401fde2/tag baseline-sandbox-working-20261022及独立bundle验证PASS；本地研究分支，无推送。
- 新增network_research.py和network-research-check.ps1，仅配置不变的socket/Cognex原生对照与UDP端口观察；src/G04路径及基准二进制不改。独立编译/CTest4/4 PASS。
- 实测：同IP socket单播/广播/ACK/3帧全像素PASS；Cognex四组发现/XML/FIFO/开始PASS、有效帧FAIL，软件命令已执行。源/目的与SDK实际端口绑定对齐，但没有包路径证据，不归因于单一IP冲突或某驱动。
- Sandbox基准重新启动五组15帧PASS（G04/manual/20261022_212729/）；新研究证据network-research/。双IP/独立端点NOT TESTED，未更改网络配置；PktMon权限BLOCKED，没有pcap。
- 报告NETWORK_ARCHITECTURE_RESEARCH.md及简版tests/manual/NETWORK_ARCHITECTURE_RESEARCH.md；包含候选方案、局限、抓包、需审批操作/回滚。下一步等用户复核及管理员捕获，未进入G05。


## G04 取流修复 — 2026-10-22（AWAITING MANUAL TEST）

- 用户授权准备隔离环境；Windows Sandbox实际启动、相机/宿主独立IP。新增g04-sandbox-prepare.ps1、g04_sandbox_run.py，g04-check.ps1一条命令完成启动和五组原生SDK测试。
- RGB8Packed Custom别名使本机Cognex识别RGB8视频格式；PFNC/传输字节序不变。探针校验每个灰度/RGB像素并保存真实PGM/PPM，软件触发等待异步采集已开始。
- PASS：MSVC构建/CTest4/4（rgb-alias-build.txt）、C#构建（probe-build.txt）、Cognex五组15帧全像素（sandbox-final-pixels/）、PS5.1入口（sandbox-entry-check-fixed.txt及sandbox-fresh-entry.txt）、原同机Aravis1069帧/停止重连/零发送错误（rgb-alias-aravis-single/）。
- 保留失败：同IP历史取图、RGB识别、软件触发开始竞态、旧Sandbox进程名识别、双序列号发现冲突、GUI占控、跨Sandbox Aravis缺帧。未伪造抓包/兼容PASS。
- QuickBuild设备/Mono FIFO已观察，GUI有效图像NOT TESTED；跨Sandbox Aravis FAIL、真实抓包BLOCKED、HALCON/Harvester NOT TESTED。简版手动指南tests/manual/G04_visionpro.md；等待用户反馈，未进入下一阶段。


## G04 — 2026-10-22（AWAITING MANUAL TEST）

- 实际Cognex SDK59.2枚举/身份/XML/Mono FIFO PASS，但Mono和连续取图超时FAIL；RGB视频格式不可用，软件触发被SDK重写，未声称兼容。QuickBuild列表和错误截图存档，GUI有效采集未验证。
- 修复536字节ReadMem；`powershell.exe -NoProfile -File scripts/g04-server-build.ps1` PASS（CTest4/4），`powershell.exe -NoProfile -File scripts/g04-build.ps1` PASS；G04 EXE实际Aravis1069帧回归PASS。
- `powershell.exe -NoProfile -File scripts/g04-check.ps1` 已实际运行完整调查，兼容结果含FAIL/BLOCKED；日志tests/evidence/G04/manual/20261022_201729/。报告docs/G04_VISIONPRO.md，简版tests/manual/G04_visionpro.md。
- 保留旧IP回归失败、初始编译/锁定EXE与节点加载失败；抓包/规范/GenTL缺口未解决，不进入G05。


## 2026-10-22 — G03 手动入口修复（AWAITING MANUAL TEST）

- 用户G03两次FAIL：上一轮G02自动测试仍占用3956，原入口立刻失败；PS5.1将Python stderr转为终止错误并截断详情。保留用户截图/原日志和WinError10048复现。
- 增加最多60秒自动等待，不停止其他进程；超时完整记录阶段/原因。独立Python日志助手把stderr转为文本，按真实退出码判断；PS5.1/7成功和失败均覆盖，6项回归PASS。
- 完整MSVC重编译、CTest3/3 PASS，C++逻辑未改；实际G02占用时启动PS5.1 G03入口，自动等待后完整7组1314帧再次PASS；简版教程仍两行命令，明确只运行G03、看到WAIT等候即可。阶段保持等待用户重测，不进入G04。

## 2026-10-22 — G03（AWAITING MANUAL TEST）

- 新增独立VIC Core、OpenCV4.12本地依赖、图片/序列/视频、保持比例缩放补边、Mono8/RGB8转换、FPS调度、软件触发/延迟及16项上限。
- GVCP真实可写尺寸/格式/FPS/触发状态与PayloadSize，GVSP使用真实Core元数据；停止、控制释放与心跳取消触发并等待旧帧结束，旧G02二进制及默认图回归保留。
- MSVC x64 Release、CTest3/3、6个启动错误场景PASS；真实Aravis7组1314帧全像素/尺寸/格式/FPS/触发/停止重开PASS。PS5.1整轮简版入口PASS，教程只需两行命令、等待、发截图；保留初始夹具失败及最终证据。
- 原仓库没有GenTL实现，GenTL回归BLOCKED；规范/抓包BLOCKED。VisionPro/HALCON/Harvester未测，不宣称兼容，不进入G04/GUI；无Git元数据，未提交。

## 2026-10-22 — G02 用户基础采集复测PASS

- 用户在Windows PowerShell5.1执行简版命令成功：发现/打开/开始/有效图像分别PASS，连续1000帧及重连20帧逐像素通过，零发送/接收错误。截图与本机日志存档于tests/evidence/G02/manual/20261022_073223/。
- 更新进度、路线图、任务、来源报告和验收表；真实抓包/规范审查仍BLOCKED且未豁免，阶段仍AWAITING MANUAL TEST。未改代码或运行新测试，不进入G03。

## 2026-10-22 — G02 手动入口修复（AWAITING MANUAL TEST）

- 用户截图报告Windows PowerShell5.1运行g02-check.ps1出现乱码/字符串未终止；同环境复现FAIL。改用UTF-8 BOM保存脚本，保留中文提示，无执行策略变更。
- Windows PowerShell5.1与PowerShell7解析PASS；5.1实际启动虚拟设备并完成1000+20帧逐像素/停止重连/零发送错误测试PASS；完整MSVC构建及CTest2/2 PASS。保留截图、修复前后解析和实际运行证据，简版教程仍只需两行命令。
- 用户复测待反馈；没有进入新阶段或新增外部兼容结论。

## 2026-10-22 — G02（AWAITING MANUAL TEST）

- 增加单通道640×480 Mono8经典GVSP Leader/Payload/Trailer、BlockID/PacketID、包长/流目标/源端口、真实Start/Stop和XML节点；必要WriteMem权限及原子校验。
- 独立发送线程使用有界单帧缓冲，控制权释放/心跳到期停止，Stop ACK等待旧帧发送结束；加入高分辨率发送节奏控制降低UDP突发丢包。
- MSVC完整构建/CTest2项通过；真实Aravis连续1000+重连20帧全像素/元数据/停止重连通过，最终零网络发送/接收失败并正常退出，保留全部早期失败与修复证据。
- 增加自动选网卡的一条复测命令和三步简版手动指南，保存实际接收图片与独立证据目录；更新任务和进度。
- 正式规范审查和真实抓包仍BLOCKED；未验证VisionPro/HALCON/Harvester，不开发G03/RGB8/触发/GUI；无Git元数据，未提交。

## 2026-10-22 — G01（AWAITING MANUAL TEST）

- 增加C++17/CMake/MSVC x64 Winsock2控制面：选定NIC过滤、单播/广播发现、稳定身份、寄存器/XML ROM、控制权/心跳、异常校验和日志；不提供GVSP/GUI/图像流。
- 使用项目内官方Windows SDK补齐本机缺失依赖；增加准备/构建脚本、独立Python客户端、外部Aravis检查及10000异常输入单元测试。
- 修复XML根标识符不符合Schema和测试客户端旧READY日志竞态，最终构建/网络/XML/外部Aravis控制访问通过；保留失败证据。
- 正式规范审查与Wireshark真实抓包仍BLOCKED，未声明标准认证或外部采集兼容；新增详细手动验收和协议来源文档，更新进度。
- 用户明确授权阶段切换，G00仍未人工验收；G02未启动，根目录非Git仓库，未提交。

## 2026-10-22 — G00（AWAITING MANUAL TEST）

- 固定并原样编译 Aravis 0.8.36 Windows x64，增加可重复的 Meson 构建、指定 IP 启动、网络消费者和 Cognex SDK 探针脚本。
- 上游 7 个测试 PASS；Aravis 网络路径完成 Mono8/RGB8、软件触发及重连检查。
- 实际记录 Cognex SDK 发现/FIFO 创建成功但 Mono 采集超时、GUI 未发现，以及默认缓冲下的丢包失败；测试消费者固定 8 MiB socket 缓冲后干净启动和跨 Consumer 恢复复测 PASS，未声明外部兼容或长期稳定性。
- 保存构建/测试/网络配置/截图证据，新增可行性报告、详细手动验收指南和测试记录，更新任务及进度；抓包因权限 BLOCKED。
- 未实现 G01 或 GenTL 阶段；根目录非 Git 仓库，未提交。
