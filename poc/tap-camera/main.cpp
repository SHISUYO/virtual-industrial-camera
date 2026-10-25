#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <winioctl.h>
#include <iphlpapi.h>
#include <objbase.h>
#include <tap-windows.h> // Upstream public API header, used under its MIT option.
#include "engine.hpp"
#include <atomic>
#include <array>
#include <chrono>
#include <iostream>
#include <map>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#ifdef VIC_G05_CONTROL
#include "control/session.hpp"
#endif
#ifdef VIC_06_SOURCES
#include "control06/gige_source.hpp"
#endif

namespace {
#ifdef VIC_06_SOURCES
constexpr unsigned max_write_depth=512;
#else
constexpr unsigned max_write_depth=64;
#endif
std::atomic<bool> stopping{false};
BOOL WINAPI on_stop(DWORD) {stopping=true;return TRUE;}
std::uint64_t ms() {return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
struct Event {
    HANDLE h=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    Event(){if(!h)throw std::runtime_error("CreateEvent failed");}
    ~Event(){CloseHandle(h);}
};
std::uint32_t ip(const std::string& s) {
    IN_ADDR addr{};if(InetPtonA(AF_INET,s.c_str(),&addr)!=1)throw std::invalid_argument("Invalid IPv4");return ntohl(addr.s_addr);
}
std::string mac_text(const tap_poc::Mac& mac) {
    std::ostringstream s;s<<std::hex<<std::setfill('0');
    for(std::size_t i=0;i<mac.size();++i){if(i)s<<':';s<<std::setw(2)<<unsigned(mac[i]);}return s.str();
}
std::string canonical_guid(const std::string& s) {
    const std::wstring w(s.begin(),s.end());GUID g{};
    if(FAILED(CLSIDFromString(w.c_str(),&g)))throw std::invalid_argument("Invalid adapter GUID");
    wchar_t out[40]{};StringFromGUID2(g,out,40);std::string result;
    for(const auto ch:std::wstring(out))result.push_back(static_cast<char>(ch));return result;
}
// All IP Helper calls below are read-only. C is deliberately NOT a Windows IP.
void verify_adapter(const std::string& guid,std::uint32_t host,std::uint32_t camera) {
    ULONG size=16384;std::vector<unsigned char> data(size);
    auto list=reinterpret_cast<IP_ADAPTER_ADDRESSES*>(data.data());
    auto error=GetAdaptersAddresses(AF_INET,0,nullptr,list,&size);
    if(error==ERROR_BUFFER_OVERFLOW){data.resize(size);list=reinterpret_cast<IP_ADAPTER_ADDRESSES*>(data.data());error=GetAdaptersAddresses(AF_INET,0,nullptr,list,&size);}
    if(error!=NO_ERROR)throw std::runtime_error("Adapter enumeration failed");
    bool found=false;
    for(auto a=list;a;a=a->Next) {
        const bool selected=_stricmp(a->AdapterName,guid.c_str())==0;
        if(selected && std::wstring(a->FriendlyName)!=L"VIC-PoC-TAP")throw std::runtime_error("Only the explicitly named new VIC-PoC-TAP is allowed");
        for(auto u=a->FirstUnicastAddress;u;u=u->Next) {
            if(u->Address.lpSockaddr->sa_family!=AF_INET)continue;
            auto addr=ntohl(reinterpret_cast<sockaddr_in*>(u->Address.lpSockaddr)->sin_addr.s_addr);
            if(addr==camera)throw std::runtime_error("Camera IP must not be assigned to Windows");
            if(selected && addr==host && u->OnLinkPrefixLength==24)found=true;
        }
    }
    if(!found)throw std::runtime_error("Dedicated TAP GUID with the approved host IPv4 /24 was not found");
    if(host==camera || (host&0xffffff00)!=(camera&0xffffff00) || !(host&255) || (host&255)==255 || !(camera&255) || (camera&255)==255)
        throw std::runtime_error("Host/camera must be distinct unicast IPv4 in the approved /24");
}
class Tap {
    HANDLE file_=INVALID_HANDLE_VALUE;
    Event read_event_;
    OVERLAPPED read_{};
    bool pending_=false,active_=false;
    tap_poc::Bytes buffer_=tap_poc::Bytes(65536);
    struct Write {
        Event event;
        OVERLAPPED op{};
        DWORD length=0;
        bool pending=false;
    };
    // Each slot owns a stable OVERLAPPED/event. Caller buffers remain alive until
    // send_batch has drained every slot, including on exceptions/cancellation.
    std::array<Write,max_write_depth> writes_;
    std::uint64_t wait_us_=0,submit_us_=0;
    static std::uint64_t us(){return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
    void complete(Write& w) {
        if(!w.pending)return;
        const auto start=us();DWORD count=0;
        if(WaitForSingleObject(w.event.h,2000)!=WAIT_OBJECT_0) {
            CancelIoEx(file_,&w.op);GetOverlappedResult(file_,&w.op,&count,TRUE);w.pending=false;
            throw std::runtime_error("TAP WriteFile timeout");
        }
        const bool ok=GetOverlappedResult(file_,&w.op,&count,FALSE)!=FALSE;
        w.pending=false;wait_us_+=us()-start;
        if(!ok || count!=w.length)throw std::runtime_error("TAP WriteFile incomplete");
    }
    void cancel_writes() noexcept {
        for(auto& w:writes_)if(w.pending)CancelIoEx(file_,&w.op);
        for(auto& w:writes_)if(w.pending){DWORD ignored=0;GetOverlappedResult(file_,&w.op,&ignored,TRUE);w.pending=false;}
    }
    DWORD ioctl(DWORD code,void* in,DWORD insize,void* out,DWORD outsize) {
        Event event;OVERLAPPED op{};op.hEvent=event.h;DWORD count=0;
        if(!DeviceIoControl(file_,code,in,insize,out,outsize,&count,&op) && GetLastError()!=ERROR_IO_PENDING)
            throw std::runtime_error("TAP IOCTL failed: "+std::to_string(GetLastError()));
        if(WaitForSingleObject(event.h,2000)!=WAIT_OBJECT_0){CancelIoEx(file_,&op);GetOverlappedResult(file_,&op,&count,TRUE);throw std::runtime_error("TAP IOCTL timeout");}
        if(!GetOverlappedResult(file_,&op,&count,FALSE))throw std::runtime_error("TAP IOCTL completion failed");return count;
    }
public:
    tap_poc::Mac host_mac{};
    explicit Tap(const std::string& guid) {
        const std::string path=std::string(USERMODEDEVICEDIR)+guid+TAP_WIN_SUFFIX;
        file_=CreateFileA(path.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_SYSTEM|FILE_FLAG_OVERLAPPED,nullptr);
        if(file_==INVALID_HANDLE_VALUE)throw std::runtime_error("Cannot exclusively open approved TAP: "+std::to_string(GetLastError()));
        try {
            ULONG version[3]{},mtu=0;
            if(ioctl(TAP_WIN_IOCTL_GET_VERSION,nullptr,0,version,sizeof(version))!=sizeof(version) || version[0]!=9 || version[1]!=27 || version[2]!=0)
                throw std::runtime_error("PoC requires the reviewed release TAP9.27 (non-debug)");
            if(ioctl(TAP_WIN_IOCTL_GET_MAC,nullptr,0,host_mac.data(),6)!=6)throw std::runtime_error("TAP MAC query failed");
            ioctl(TAP_WIN_IOCTL_GET_MTU,nullptr,0,&mtu,sizeof(mtu));if(mtu!=1500)throw std::runtime_error("PoC requires TAP MTU1500");
        } catch(...) {CloseHandle(file_);file_=INVALID_HANDLE_VALUE;throw;}
    }
    void activate(){ULONG up=1;ioctl(TAP_WIN_IOCTL_SET_MEDIA_STATUS,&up,sizeof(up),&up,sizeof(up));active_=true;}
    ~Tap() {
        if(file_==INVALID_HANDLE_VALUE)return;
        cancel_writes();
        if(pending_){DWORD ignored=0;CancelIoEx(file_,&read_);GetOverlappedResult(file_,&read_,&ignored,TRUE);}
        if(active_)try{ULONG down=0;ioctl(TAP_WIN_IOCTL_SET_MEDIA_STATUS,&down,sizeof(down),&down,sizeof(down));}catch(...){std::cerr<<"MEDIA_DOWN_FAILED: inspect only the dedicated test TAP\n";}
        CloseHandle(file_);
    }
    bool receive(tap_poc::Bytes& out,DWORD timeout=1) {
        if(!pending_) {
            read_={};read_.hEvent=read_event_.h;ResetEvent(read_event_.h);DWORD count=0;
            if(!ReadFile(file_,buffer_.data(),static_cast<DWORD>(buffer_.size()),&count,&read_) && GetLastError()!=ERROR_IO_PENDING)
                throw std::runtime_error("TAP ReadFile failed");
            pending_=true;
        }
        const auto wait=WaitForSingleObject(read_event_.h,timeout);if(wait==WAIT_TIMEOUT)return false;
        if(wait!=WAIT_OBJECT_0)throw std::runtime_error("TAP read wait failed");DWORD count=0;
        if(!GetOverlappedResult(file_,&read_,&count,FALSE))throw std::runtime_error("TAP read completion failed");
        pending_=false;out.assign(buffer_.begin(),buffer_.begin()+count);return true;
    }
#ifdef VIC_06_SOURCES
    void send_control(const tap_poc::Bytes& packet) {
        Write control;control.op.hEvent=control.event.h;control.length=static_cast<DWORD>(packet.size());DWORD count=0;
        if(!WriteFile(file_,packet.data(),control.length,&count,&control.op) && GetLastError()!=ERROR_IO_PENDING)
            throw std::runtime_error("TAP control WriteFile failed");
        control.pending=true;complete(control);
    }
#endif
    void send_batch(const std::vector<tap_poc::Bytes>& packets,unsigned depth,const std::function<void(const tap_poc::Bytes&)>& submitted) {
        if(depth<1 || depth>writes_.size())throw std::invalid_argument("Invalid TAP write depth");
        std::size_t index=0;
        try {
            for(const auto& b:packets) {
                if(stopping)break;
                auto& w=writes_[index++%depth];complete(w);
                w.op={};w.op.hEvent=w.event.h;ResetEvent(w.event.h);w.length=static_cast<DWORD>(b.size());
                const auto start=us();DWORD count=0;
                const bool ok=WriteFile(file_,b.data(),w.length,&count,&w.op)!=FALSE;
                if(!ok && GetLastError()!=ERROR_IO_PENDING)throw std::runtime_error("TAP WriteFile failed: "+std::to_string(GetLastError()));
                w.pending=true;submit_us_+=us()-start;
                // Capture submission, not NDIS buffer-return time or SDK delivery.
                submitted(b);
            }
            for(auto& w:writes_)complete(w);
        } catch(...) {cancel_writes();throw;}
    }
    std::uint64_t wait_us() const{return wait_us_;}
    std::uint64_t submit_us() const{return submit_us_;}
};
}
int main(int argc,char** argv) {
    try {
        if(argc==3 && std::string(argv[1])=="--offline")return tap_poc::offline(argv[2]);
        if(argc==1 || (argc==2 && std::string(argv[1])=="--help")) {
#ifdef VIC_G05_CONTROL
            std::cout<<"VICGigEControl G05-0.5.0 TAP (local control; Consumer validation separate)\n";
#else
            std::cout<<"VICTapPoC 0.1.1 G04-D (independent user-mode Ethernet adapter; consumer acceptance separate)\n"
                ;
#endif
            std::cout<<"--offline <output-dir> : synthetic tests; no device opened\n"
                <<"--live --owned-adapter-consent --adapter-guid <GUID> --host-ip <H> --camera-ip <C> --seconds <1..120> --log <file> --pcap <file> [--write-depth <1..64>]\n"
                <<"LIVE requires prior approval for a NEW dedicated VIC-PoC-TAP adapter and its host IPv4. Never assigns an IP or installs a driver.\n";return 0;
        }
        bool live=false,consent=false;std::map<std::string,std::string> options;
        for(int i=1;i<argc;++i) {
            const std::string key=argv[i];if(key=="--live"){live=true;continue;}if(key=="--owned-adapter-consent"){consent=true;continue;}
#ifdef VIC_06_SOURCES
            if(key=="--source-config"){
                if(i+1==argc || !options.emplace(key,argv[++i]).second)throw std::invalid_argument("Missing/duplicate source configuration");continue;
            }
#endif
#ifdef VIC_G05_CONTROL
            if(key=="--pipe" || key=="--packet-size" || key=="--trigger-delay-us" || key=="--drop-percent" || key=="--seed") {
                if(i+1==argc || !options.emplace(key,argv[++i]).second)throw std::invalid_argument("Missing/duplicate control option");continue;
            }
#endif
            if(key!="--adapter-guid" && key!="--host-ip" && key!="--camera-ip" && key!="--seconds" && key!="--log" && key!="--pcap" && key!="--write-depth")throw std::invalid_argument("Unknown option");
            if(i+1==argc || !options.emplace(key,argv[++i]).second)throw std::invalid_argument("Missing/duplicate option");
        }
        if(!live || !consent)throw std::runtime_error("LIVE REFUSED: deployment approval / --owned-adapter-consent is required before any adapter access");
        for(auto key:{"--adapter-guid","--host-ip","--camera-ip","--seconds","--log","--pcap"})if(!options.count(key))throw std::invalid_argument("Missing live option");
        const int seconds=std::stoi(options.at("--seconds"));
#ifdef VIC_G05_CONTROL
        if(seconds<1 || seconds>86400)throw std::invalid_argument("Duration outside1..86400");
        const auto number=[&](const char* key,unsigned fallback){
            if(!options.count(key))return fallback;
            const auto& text=options.at(key);if(text.empty() || text.find_first_not_of("0123456789")!=std::string::npos)throw std::invalid_argument("Invalid numeric control option");
            const auto value=std::stoull(text);if(value>0xffffffffu)throw std::invalid_argument("Control option overflow");return static_cast<unsigned>(value);
        };
        const auto initial_packet=number("--packet-size",1400),initial_delay=number("--trigger-delay-us",0);
        vic_control::PacketFault faults(number("--drop-percent",0),number("--seed",1));
#else
        if(seconds<1 || seconds>120)throw std::invalid_argument("Duration outside1..120");
#endif
        const int depth=options.count("--write-depth")?std::stoi(options.at("--write-depth")):64;
        if(depth<1 || depth>static_cast<int>(max_write_depth))throw std::invalid_argument("Write depth exceeds this build's bounded capacity");
        tap_poc::Config config;config.host=ip(options.at("--host-ip"));config.camera=ip(options.at("--camera-ip"));
#ifdef VIC_06_SOURCES
        if(!options.count("--source-config"))throw std::invalid_argument("06 requires an explicit source configuration");
        load_source_config(options.at("--source-config"),config);
#endif
        const auto guid=canonical_guid(options.at("--adapter-guid"));verify_adapter(guid,config.host,config.camera);
        std::ofstream log(options.at("--log"));if(!log)throw std::runtime_error("Cannot create log");
        auto emit=[&](const std::string& s){
#ifdef VIC_G05_CONTROL
            if(s.compare(0,20,"GVSP_FRAME_GENERATED")==0)return; // Bounded one-second aggregate replaces per-frame disk logging.
#endif
            const auto line="t_ms="+std::to_string(ms())+" "+s;std::cout<<line<<std::endl;log<<line<<'\n';
#ifndef VIC_G05_CONTROL
            log.flush();
#endif
        };
        Tap tap(guid);config.host_mac=tap.host_mac;tap_poc::Engine engine(config,emit);
#ifdef VIC_06_SOURCES
        emit("SOURCE_CONFIG kind="+std::to_string(static_cast<unsigned>(config.source.kind))+" path="+config.source.path+" serial="+config.identity.serial+" width="+std::to_string(config.initial_camera.width)+" height="+std::to_string(config.initial_camera.height)+" max_dimension=6000 large_frame_write_depth="+std::to_string(max_write_depth)+" control_service_every128=1");
#endif
        std::unique_ptr<tap_poc::Pcap> pcap;
#ifdef VIC_G05_CONTROL
        engine.configure_initial_stream(initial_packet,initial_delay);
        if(options.at("--pcap")!="-")pcap=std::make_unique<tap_poc::Pcap>(options.at("--pcap"));
        std::unique_ptr<vic_control::ControlPipe> pipe;
        if(options.count("--pipe"))pipe=std::make_unique<vic_control::ControlPipe>(options.at("--pipe"),stopping);
#else
        pcap=std::make_unique<tap_poc::Pcap>(options.at("--pcap"));
#endif
        auto capture=[&](const tap_poc::Bytes& frame){if(pcap) {
#ifdef VIC_G05_CONTROL
            try{pcap->record(frame);}catch(const std::exception& e){emit(std::string("CAPTURE_DISABLED reason=")+e.what());pcap.reset();}
#else
            pcap->record(frame);
#endif
        }};
        tap.activate();SetConsoleCtrlHandler(on_stop,TRUE);
        emit(std::string("READY build=")+
#ifdef VIC_06_SOURCES
             "06-GIGE-0.6.5"
#elif defined(VIC_G05_CONTROL)
             "G05-0.5.0"
#else
             "TAP-POC-0.1.1"
#endif
             +" mode=LIVE device_boundary_pcap="+std::to_string(bool(pcap))+" pcap_stage=submission NDIS_delivery_NOT_PROVEN=1 write_depth="+std::to_string(depth)+" adapter="+guid+
             " camera_ip="+options.at("--camera-ip")+" host_ip="+options.at("--host-ip")+
             " camera_mac="+mac_text(config.camera_mac)+" host_mac="+mac_text(config.host_mac)+" stream_source_port=49152");
        const auto deadline=ms()+static_cast<std::uint64_t>(seconds)*1000;std::uint64_t rx=0,tx=0;
        std::uint64_t capture_us=0;
        std::uint64_t complete_frames=0;
        auto send=[&](const std::vector<tap_poc::Bytes>& packets){
            std::size_t submitted_count=0;
            const std::vector<tap_poc::Bytes>* selected=&packets;
#ifdef VIC_G05_CONTROL
            const auto before_drops=faults.dropped;std::vector<tap_poc::Bytes> filtered;
            if(number("--drop-percent",0)) {for(const auto& p:packets)if(!faults.discard(p.data(),p.size()))filtered.push_back(p);selected=&filtered;}
#endif
            unsigned frame_depth=static_cast<unsigned>(depth);
#ifdef VIC_06_SOURCES
            // Bound outstanding NDIS writes for large frames; retain G05's path.
            if(packets.size()>4096 && !options.count("--write-depth"))frame_depth=max_write_depth;
#endif
            tap.send_batch(*selected,frame_depth,[&](const tap_poc::Bytes& b){
            const auto before=std::chrono::steady_clock::now();capture(b);++tx;++submitted_count;
            capture_us+=static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-before).count());
#ifdef VIC_06_SOURCES
            if(packets.size()>4096 && submitted_count%128==0) {
                // Keep control/heartbeat requests responsive during a large frame.
                // A separate OVERLAPPED avoids reusing pending payload slots.
                tap_poc::Bytes control;
                for(unsigned n=0;n<8 && tap.receive(control,0);++n) {
                    capture(control);++rx;
                    const auto replies=engine.receive(control,ms());
                    for(const auto& reply:replies){tap.send_control(reply);capture(reply);++tx;}
                }
            }
#endif
            });
            if(packets.size()>1 && submitted_count==packets.size()
#ifdef VIC_G05_CONTROL
                && faults.dropped==before_drops
#endif
            )++complete_frames;
        };
#ifdef VIC_G05_CONTROL
        auto last_metrics=ms();std::uint64_t last_generated=0,last_complete=0;
        const auto metrics=[&](){const auto now=ms();const auto elapsed=std::max<std::uint64_t>(1,now-last_metrics);const auto state=engine.settings();const auto owner=engine.controller();
            emit("METRICS generated="+std::to_string(engine.frames)+" submitted_frames="+std::to_string(complete_frames)+" submitted_packets="+std::to_string(tx)+" simulated_drop_packets="+std::to_string(faults.dropped)+
                " generated_fps="+std::to_string((engine.frames-last_generated)*1000.0/elapsed)+" submitted_fps="+std::to_string((complete_frames-last_complete)*1000.0/elapsed)+
                " acquiring="+std::to_string(state.acquiring)+" controller="+std::to_string(owner?owner->ip:0)+" packet_size="+std::to_string(state.packet_size)+" trigger_delay_us="+std::to_string(state.camera.trigger_delay_us)+" gvcp="+std::to_string(engine.gvcp)+" rejected="+std::to_string(engine.rejected));
            log.flush();last_metrics=now;last_generated=engine.frames;last_complete=complete_frames;
        };
#endif
        while(!stopping && ms()<deadline) {
            tap_poc::Bytes frame;if(tap.receive(frame)){capture(frame);++rx;send(engine.receive(frame,ms()));}
            send(engine.poll(ms()));
#ifdef VIC_G05_CONTROL
            if(ms()-last_metrics>=1000)metrics();
#endif
        }
#ifdef VIC_G05_CONTROL
        metrics();
#endif
        emit("STOP rx="+std::to_string(rx)+" tx_submitted="+std::to_string(tx)+" rejected="+std::to_string(engine.rejected)+
             " frames_generated="+std::to_string(engine.frames)+" VisionPro_valid_frames=NOT_TESTED_BY_THIS_PROCESS");
        emit("IO_PROFILE submit_us="+std::to_string(tap.submit_us())+" completion_wait_us="+std::to_string(tap.wait_us())+" capture_us="+std::to_string(capture_us));
        SetConsoleCtrlHandler(on_stop,FALSE);return 0;
    } catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
