#pragma once
#include <windows.h>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>

namespace vic_control {
// Local control protocol, NOT GVCP/GVSP: 40-byte little-endian message.
// magic[4], version:u16, command:u16, length:u32, request:u64, device[16], status:u32.
constexpr std::size_t message_size=40;
inline unsigned u16(const unsigned char* b){return unsigned(b[0])|(unsigned(b[1])<<8);}
inline std::uint32_t u32(const unsigned char* b){return u16(b)|(std::uint32_t(u16(b+2))<<16);}
class ControlPipe {
    HANDLE pipe_=INVALID_HANDLE_VALUE,shutdown_=nullptr;
    std::thread worker_;
    std::atomic<bool>& stopping_;
    bool finish(OVERLAPPED& op,BOOL started,DWORD error,DWORD& bytes) {
        if(started)return true;
        if(error!=ERROR_IO_PENDING)return false;
        HANDLE events[]{shutdown_,op.hEvent};
        const auto state=WaitForMultipleObjects(2,events,FALSE,2000);
        if(state!=WAIT_OBJECT_0+1){CancelIoEx(pipe_,&op);GetOverlappedResult(pipe_,&op,&bytes,TRUE);return false;}
        return GetOverlappedResult(pipe_,&op,&bytes,FALSE)!=FALSE;
    }
    void run() noexcept {
        while(WaitForSingleObject(shutdown_,0)!=WAIT_OBJECT_0) {
            HANDLE event=CreateEventW(nullptr,TRUE,FALSE,nullptr);if(!event)break;
            OVERLAPPED op{};op.hEvent=event;DWORD count=0;
            BOOL connected=ConnectNamedPipe(pipe_,&op);DWORD error=connected?ERROR_SUCCESS:GetLastError();
            // Connect can remain idle indefinitely; no client means no work.
            if(!connected && error==ERROR_IO_PENDING) {
                HANDLE events[]{shutdown_,event};const auto state=WaitForMultipleObjects(2,events,FALSE,INFINITE);
                if(state==WAIT_OBJECT_0+1)connected=GetOverlappedResult(pipe_,&op,&count,FALSE);
                else {CancelIoEx(pipe_,&op);GetOverlappedResult(pipe_,&op,&count,TRUE);CloseHandle(event);break;}
            } else if(error==ERROR_PIPE_CONNECTED)connected=TRUE;
            std::array<unsigned char,message_size> bytes{};
            bool stop=false;
            if(connected) {
                ResetEvent(event);op={};op.hEvent=event;
                const BOOL started=ReadFile(pipe_,bytes.data(),DWORD(bytes.size()),&count,&op);error=started?ERROR_SUCCESS:GetLastError();
                if(finish(op,started,error,count) && count==bytes.size()) {
                    unsigned status=0;const auto command=u16(bytes.data()+6);
                    const char device[16]="VICGE000001";
                    if(std::memcmp(bytes.data(),"VIC1",4) || u16(bytes.data()+4)!=1 || u32(bytes.data()+8)!=message_size)status=1;
                    else if(std::memcmp(bytes.data()+20,device,16))status=3;
                    else if(command!=1 && command!=2)status=2;
                    std::memcpy(bytes.data(),"VIC1",4);bytes[4]=1;bytes[5]=0;
                    bytes[36]=static_cast<unsigned char>(status);bytes[37]=bytes[38]=bytes[39]=0;
                    ResetEvent(event);op={};op.hEvent=event;
                    const BOOL written=WriteFile(pipe_,bytes.data(),DWORD(bytes.size()),&count,&op);error=written?ERROR_SUCCESS:GetLastError();
                    if(finish(op,written,error,count) && count==bytes.size()) {
                        stop=status==0 && command==1;
                        // Wait for a bounded client receipt acknowledgement before
                        // DisconnectNamedPipe can discard the queued response.
                        unsigned char ack=0;ResetEvent(event);op={};op.hEvent=event;
                        const BOOL readAck=ReadFile(pipe_,&ack,1,&count,&op);error=readAck?ERROR_SUCCESS:GetLastError();
                        finish(op,readAck,error,count);
                    }
                }
            }
            DisconnectNamedPipe(pipe_);CloseHandle(event);
            if(stop){stopping_=true;break;}
        }
    }
public:
    ControlPipe(const std::string& name,std::atomic<bool>& stopping):stopping_(stopping) {
        const std::string prefix="\\\\.\\pipe\\VIC.G05.";
        if(name.size()!=prefix.size()+32 || name.compare(0,prefix.size(),prefix)!=0 || name.find_first_not_of("0123456789abcdef",prefix.size())!=std::string::npos)
            throw std::invalid_argument("Invalid private control pipe name");
        pipe_=CreateNamedPipeA(name.c_str(),PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED|FILE_FLAG_FIRST_PIPE_INSTANCE,
            PIPE_TYPE_MESSAGE|PIPE_READMODE_MESSAGE|PIPE_WAIT|PIPE_REJECT_REMOTE_CLIENTS,1,64,64,2000,nullptr);
        if(pipe_==INVALID_HANDLE_VALUE)throw std::runtime_error("Cannot create private control pipe");
        shutdown_=CreateEventW(nullptr,TRUE,FALSE,nullptr);
        if(!shutdown_){CloseHandle(pipe_);throw std::runtime_error("Cannot create control shutdown event");}
        try{worker_=std::thread([this]{run();});}catch(...){CloseHandle(shutdown_);CloseHandle(pipe_);throw;}
    }
    ~ControlPipe(){SetEvent(shutdown_);if(worker_.joinable())worker_.join();CloseHandle(pipe_);CloseHandle(shutdown_);}
    ControlPipe(const ControlPipe&)=delete;
    ControlPipe& operator=(const ControlPipe&)=delete;
};
class PacketFault {
    unsigned percent_;
    std::uint32_t state_;
public:
    std::uint64_t dropped=0;
    PacketFault(unsigned percent,std::uint32_t seed):percent_(percent),state_(seed?seed:1) {
        if(percent>100)throw std::invalid_argument("Drop percentage outside0..100");
    }
    bool discard(const unsigned char* b,std::size_t size) {
        // Only classic GVSP IMAGE payload; discovery/control/leader/trailer stay intact.
        if(!percent_ || size<50 || b[12]!=8 || b[13]!=0 || b[23]!=17 || b[34]!=0xc0 || b[35]!=0 || b[46]!=3)return false;
        state_^=state_<<13;state_^=state_>>17;state_^=state_<<5;
        if(state_%100<percent_){++dropped;return true;}return false;
    }
};
}
