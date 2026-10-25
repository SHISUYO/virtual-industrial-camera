#include <winsock2.h>
#include <ws2tcpip.h>
#include <mswsock.h>
#include <iphlpapi.h>
#include "gige/gvcp.hpp"
#include "gige/stream_sender.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <fstream>
#include <iostream>
#include <mutex>
#include <stdexcept>

namespace {
std::atomic<bool> stopping{false};
BOOL WINAPI on_console(DWORD event) {
    if(event==CTRL_C_EVENT || event==CTRL_BREAK_EVENT || event==CTRL_CLOSE_EVENT) {
        stopping=true;return TRUE;
    }
    return FALSE;
}
std::uint64_t now_ms() {
    return std::uint64_t(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
std::string ip_text(std::uint32_t host) {
    IN_ADDR a{};a.s_addr=htonl(host);char text[INET_ADDRSTRLEN]{};
    if(!InetNtopA(AF_INET,&a,text,sizeof(text))) throw std::runtime_error("InetNtop failed");
    return text;
}
struct Selected { vic::Network net;ULONG index; };
Selected select_adapter(const std::string& ip) {
    IN_ADDR requested{};
    if(InetPtonA(AF_INET,ip.c_str(),&requested)!=1 || requested.s_addr==0 || ntohl(requested.s_addr)==0xffffffff)
        throw std::runtime_error("--bind requires a specific local IPv4 address");
    ULONG size=16384;
    std::vector<unsigned char> storage(size);
    auto* list=reinterpret_cast<IP_ADAPTER_ADDRESSES*>(storage.data());
    auto result=GetAdaptersAddresses(AF_INET,GAA_FLAG_INCLUDE_PREFIX|GAA_FLAG_INCLUDE_GATEWAYS,nullptr,list,&size);
    if(result==ERROR_BUFFER_OVERFLOW) {
        storage.resize(size);list=reinterpret_cast<IP_ADAPTER_ADDRESSES*>(storage.data());
        result=GetAdaptersAddresses(AF_INET,GAA_FLAG_INCLUDE_PREFIX|GAA_FLAG_INCLUDE_GATEWAYS,nullptr,list,&size);
    }
    if(result!=NO_ERROR) throw std::runtime_error("GetAdaptersAddresses failed: "+std::to_string(result));
    for(auto* adapter=list;adapter;adapter=adapter->Next) {
        if(adapter->OperStatus!=IfOperStatusUp) continue;
        for(auto* unicast=adapter->FirstUnicastAddress;unicast;unicast=unicast->Next) {
            const auto* address=reinterpret_cast<const sockaddr_in*>(unicast->Address.lpSockaddr);
            if(address->sin_family!=AF_INET || address->sin_addr.s_addr!=requested.s_addr) continue;
            Selected out{};out.index=adapter->IfIndex;out.net.ip=ntohl(requested.s_addr);
            auto prefix=unicast->OnLinkPrefixLength;
            if(prefix>32) throw std::runtime_error("Invalid IPv4 prefix length");
            out.net.mask=prefix==0?0:(0xffffffffu<<(32-prefix));
            if(adapter->PhysicalAddressLength==6)
                std::copy(adapter->PhysicalAddress,adapter->PhysicalAddress+6,out.net.mac.begin());
            for(auto* gateway=adapter->FirstGatewayAddress;gateway;gateway=gateway->Next) {
                if(gateway->Address.lpSockaddr->sa_family==AF_INET) {
                    out.net.gateway=ntohl(reinterpret_cast<const sockaddr_in*>(gateway->Address.lpSockaddr)->sin_addr.s_addr);break;
                }
            }
            return out;
        }
    }
    throw std::runtime_error("Bind IP is not assigned to an active local adapter");
}
struct Wsa {
    Wsa(){ WSADATA data{};auto e=WSAStartup(MAKEWORD(2,2),&data);if(e) throw std::runtime_error("WSAStartup failed: "+std::to_string(e)); }
    ~Wsa(){WSACleanup();}
};
struct Socket {
    SOCKET value=INVALID_SOCKET;
    ~Socket(){if(value!=INVALID_SOCKET) closesocket(value);}
};
template<typename T> T extension(SOCKET socket,GUID guid) {
    T function=nullptr;DWORD count=0;
    if(WSAIoctl(socket,SIO_GET_EXTENSION_FUNCTION_POINTER,&guid,sizeof(guid),&function,sizeof(function),&count,nullptr,nullptr)==SOCKET_ERROR)
        throw std::runtime_error("Winsock message extension unavailable: "+std::to_string(WSAGetLastError()));
    return function;
}
}
int main(int argc,char** argv) {
    try {
        std::string bind_ip,config="assets/g01-camera.ini",log_path,xml_path;
        std::uint64_t duration=0;
        vic::SourceOptions source;bool source_set=false;
        for(int i=1;i<argc;++i) {
            std::string key=argv[i];
            if(key=="--help") {
                std::cout<<"VICGigE G04-0.4.0 (VIC Core Mono8/RGB8, continuous/software trigger)\n"
                    <<"--bind <local IPv4> [--config <INI>] [--log <file>] [--dump-xml <file>] [--duration-ms <1..86400000>] [--image <file> | --sequence <directory> | --video <file>] [--resize fit|stretch]\n";
                return 0;
            }
            if(i+1==argc) throw std::runtime_error("Missing option value");
            std::string value=argv[++i];
            if(key=="--bind") bind_ip=value;
            else if(key=="--config") config=value;
            else if(key=="--log") log_path=value;
            else if(key=="--dump-xml") xml_path=value;
            else if(key=="--image" || key=="--sequence" || key=="--video") {
                if(source_set) throw std::runtime_error("Choose only one image source");
                source_set=true;source.path=value;
                source.kind=key=="--image"?vic::SourceOptions::Kind::Image:(key=="--sequence"?vic::SourceOptions::Kind::Sequence:vic::SourceOptions::Kind::Video);
            } else if(key=="--resize") {
                if(value!="fit" && value!="stretch") throw std::runtime_error("--resize requires fit or stretch");
                source.fit=value=="fit";
            } else if(key=="--duration-ms") {
                if(value.empty() || value.find_first_not_of("0123456789")!=std::string::npos) throw std::runtime_error("Invalid duration");
                duration=std::stoull(value);
                if(!duration || duration>86400000) throw std::runtime_error("Duration out of range");
            } else throw std::runtime_error("Unknown option: "+key);
        }
        if(bind_ip.empty()) throw std::runtime_error("--bind is required; no default all-interface service");
        Wsa wsa;auto selected=select_adapter(bind_ip);auto identity=vic::load_identity(config);
        vic::Gvcp core(identity,selected.net,true);
        std::ofstream log;
        if(!log_path.empty()) {log.open(log_path);if(!log) throw std::runtime_error("Cannot open log file");}
        std::mutex log_mutex;
        auto emit=[&](const std::string& message){
            std::lock_guard<std::mutex> guard(log_mutex);
            const auto wall=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
            const auto line="epoch_ms="+std::to_string(wall)+" t_ms="+std::to_string(now_ms())+" "+message;
            std::cout<<line<<std::endl;
            if(log.is_open()) log<<line<<std::endl;
        };
        if(!xml_path.empty()) {
            std::ofstream xml(xml_path,std::ios::binary);xml<<core.xml();
            if(!xml) throw std::runtime_error("Cannot write XML dump");
        }
        Socket socket;socket.value=WSASocketW(AF_INET,SOCK_DGRAM,IPPROTO_UDP,nullptr,0,0);
        if(socket.value==INVALID_SOCKET) throw std::runtime_error("WSASocket failed");
        auto option=[&](int level,int name,int value){
            if(setsockopt(socket.value,level,name,reinterpret_cast<const char*>(&value),sizeof(value))==SOCKET_ERROR)
                throw std::runtime_error("setsockopt failed: "+std::to_string(WSAGetLastError()));
        };
        option(SOL_SOCKET,SO_EXCLUSIVEADDRUSE,1);option(IPPROTO_IP,IP_PKTINFO,1);
        option(SOL_SOCKET,SO_RCVBUF,1024*1024);
        sockaddr_in local{};local.sin_family=AF_INET;local.sin_port=htons(vic::wire::port);
        // Windows broadcasts require a wildcard receive socket. IP_PKTINFO below
        // enforces the explicitly selected NIC + destination on every datagram.
        if(bind(socket.value,reinterpret_cast<sockaddr*>(&local),sizeof(local))==SOCKET_ERROR)
            throw std::runtime_error("bind UDP 3956 failed: "+std::to_string(WSAGetLastError()));
        auto receive=extension<LPFN_WSARECVMSG>(socket.value,WSAID_WSARECVMSG);
        auto send=extension<LPFN_WSASENDMSG>(socket.value,WSAID_WSASENDMSG);
        vic::StreamSender stream(selected.net.ip,emit,source);core.set_source_port(stream.source_port());
        if(!SetConsoleCtrlHandler(on_console,TRUE)) throw std::runtime_error("SetConsoleCtrlHandler failed");
        const auto start=now_ms();
        emit("READY build=G04-0.4.0 bind="+bind_ip+" interface_index="+std::to_string(selected.index)+
            " udp=3956 socket=0.0.0.0 filtered_by=IP_PKTINFO serial="+identity.serial+" streams=1 source_port="+std::to_string(stream.source_port()));
        std::uint64_t received=0,filtered=0,discovery_count=0,sent=0,errors=0;
        while(!stopping && (!duration || now_ms()-start<duration)) {
            const auto old_expirations=core.expirations();
            core.expire(now_ms());
            stream.configure(core.stream_settings());
            if(core.expirations()!=old_expirations) emit("HEARTBEAT_EXPIRED controller_released=1");
            fd_set read_set;FD_ZERO(&read_set);FD_SET(socket.value,&read_set);timeval timeout{0,100000};
            int ready=select(0,&read_set,nullptr,nullptr,&timeout);
            if(ready==SOCKET_ERROR) throw std::runtime_error("select failed: "+std::to_string(WSAGetLastError()));
            if(!ready) continue;
            std::array<char,65536> bytes{};
            alignas(WSACMSGHDR) char ancillary[WSA_CMSG_SPACE(sizeof(IN_PKTINFO))]{};
            sockaddr_in peer{};WSABUF buffer{static_cast<ULONG>(bytes.size()),bytes.data()};
            WSAMSG msg{};msg.name=reinterpret_cast<sockaddr*>(&peer);msg.namelen=sizeof(peer);
            msg.lpBuffers=&buffer;msg.dwBufferCount=1;msg.Control={sizeof(ancillary),ancillary};
            DWORD size=0;
            if(receive(socket.value,&msg,&size,nullptr,nullptr)==SOCKET_ERROR) {
                ++errors;emit("RECEIVE_ERROR wsa="+std::to_string(WSAGetLastError()));continue;
            }
            const IN_PKTINFO* info=nullptr;
            for(auto* c=WSA_CMSG_FIRSTHDR(&msg);c;c=WSA_CMSG_NXTHDR(&msg,c))
                if(c->cmsg_level==IPPROTO_IP && c->cmsg_type==IP_PKTINFO && c->cmsg_len>=WSA_CMSG_LEN(sizeof(IN_PKTINFO)))
                    info=reinterpret_cast<const IN_PKTINFO*>(WSA_CMSG_DATA(c));
            auto destination=info?ntohl(info->ipi_addr.s_addr):0;
            const auto subnet_broadcast=selected.net.ip|~selected.net.mask;
            if((msg.dwFlags&(MSG_TRUNC|MSG_CTRUNC)) || !info || info->ipi_ifindex!=selected.index ||
                (destination!=selected.net.ip && destination!=0xffffffff && destination!=subnet_broadcast)) {
                ++filtered;continue;
            }
            ++received;
            vic::Bytes packet(bytes.begin(),bytes.begin()+size);
            core.set_completed_triggers(stream.completed_triggers());
            auto reply=core.process(packet,{ntohl(peer.sin_addr.s_addr),ntohs(peer.sin_port)},now_ms());
            stream.configure(core.stream_settings());
            const auto command=packet.size()>=4?vic::get16(packet.data()+2):0;
            if(command==vic::wire::discovery && reply && vic::get16(reply->data())==0) ++discovery_count;
            emit("RX peer="+ip_text(ntohl(peer.sin_addr.s_addr))+":"+std::to_string(ntohs(peer.sin_port))+
                " dst="+ip_text(destination)+" bytes="+std::to_string(size)+" cmd="+std::to_string(command)+
                " id="+(packet.size()>=8?std::to_string(vic::get16(packet.data()+6)):"absent")+
                " address="+(packet.size()>=12?std::to_string(vic::get32(packet.data()+8)):"absent")+
                " data_word="+(packet.size()>=16?std::to_string(vic::get32(packet.data()+12)):"absent")+
                " status="+(reply?std::to_string(vic::get16(reply->data())):"silent"));
            if(!reply) continue;
            WSABUF output{static_cast<ULONG>(reply->size()),reinterpret_cast<char*>(reply->data())};
            alignas(WSACMSGHDR) char send_control[WSA_CMSG_SPACE(sizeof(IN_PKTINFO))]{};
            WSAMSG response{};response.name=reinterpret_cast<sockaddr*>(&peer);response.namelen=sizeof(peer);
            response.lpBuffers=&output;response.dwBufferCount=1;response.Control={sizeof(send_control),send_control};
            auto* c=WSA_CMSG_FIRSTHDR(&response);c->cmsg_level=IPPROTO_IP;c->cmsg_type=IP_PKTINFO;c->cmsg_len=WSA_CMSG_LEN(sizeof(IN_PKTINFO));
            auto* outgoing=reinterpret_cast<IN_PKTINFO*>(WSA_CMSG_DATA(c));
            outgoing->ipi_ifindex=selected.index;outgoing->ipi_addr.s_addr=htonl(selected.net.ip);
            DWORD count=0;
            if(send(socket.value,&response,0,&count,nullptr,nullptr)==SOCKET_ERROR) {
                ++errors;emit("SEND_ERROR wsa="+std::to_string(WSAGetLastError()));
            } else ++sent;
        }
        stream.finish();
        emit("STOP received="+std::to_string(received)+" discovery="+std::to_string(discovery_count)+
            " filtered="+std::to_string(filtered)+" sent="+std::to_string(sent)+" errors="+std::to_string(errors)+
            " heartbeat_expirations="+std::to_string(core.expirations()));
        SetConsoleCtrlHandler(on_console,FALSE);
        return (errors || stream.send_errors())?2:0;
    } catch(const std::exception& error) {
        std::cerr<<"FATAL "<<error.what()<<std::endl;return 1;
    }
}
