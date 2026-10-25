#include "control06/engine.hpp"
#include <windows.h>
#include <array>
#include <atomic>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <fstream>
#include <iterator>
#include <thread>

namespace {
constexpr std::size_t limit=16384,max_pixels=std::size_t(vic::max_dimension)*vic::max_dimension*3,mapping_size=40+max_pixels;
#pragma pack(push,1)
struct Header {char magic[4];std::uint16_t version,command;std::uint32_t length;std::uint64_t request;char device[16];std::uint32_t status;};
struct PreviewHeader {char magic[4];std::uint32_t version,width,height,format;std::uint64_t frame,timestamp;std::uint32_t bytes;};
#pragma pack(pop)
static_assert(sizeof(Header)==40 && sizeof(PreviewHeader)==40);
struct Handle {HANDLE h=nullptr;~Handle(){if(h && h!=INVALID_HANDLE_VALUE)CloseHandle(h);}Handle()=default;Handle(const Handle&)=delete;};
class Preview {
    Handle mapping_,mutex_;void* address_=nullptr;
public:
    Preview(const std::wstring& name,const std::wstring& mutex){
        mapping_.h=CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,DWORD(mapping_size),name.c_str());
        if(!mapping_.h || GetLastError()==ERROR_ALREADY_EXISTS)throw std::runtime_error("Shared mapping unavailable/already exists");
        address_=MapViewOfFile(mapping_.h,FILE_MAP_WRITE,0,0,mapping_size);if(!address_)throw std::runtime_error("MapViewOfFile failed");
        mutex_.h=CreateMutexW(nullptr,FALSE,mutex.c_str());if(!mutex_.h || GetLastError()==ERROR_ALREADY_EXISTS){UnmapViewOfFile(address_);address_=nullptr;throw std::runtime_error("Preview mutex unavailable/already exists");}
        std::memset(address_,0,40);
    }
    ~Preview(){if(address_)UnmapViewOfFile(address_);}
    bool write(const vic::Frame& frame,std::uint64_t id){
        if(frame.pixels.size()>max_pixels)throw std::runtime_error("Preview payload overflow");
        const auto result=WaitForSingleObject(mutex_.h,0);if(result!=WAIT_OBJECT_0 && result!=WAIT_ABANDONED)return false;
        PreviewHeader header{{'V','0','6','F'},1,frame.settings.width,frame.settings.height,frame.settings.pixel_format,id,frame.timestamp_ns,static_cast<std::uint32_t>(frame.pixels.size())};
        std::memcpy(address_,&header,sizeof(header));std::memcpy(static_cast<unsigned char*>(address_)+40,frame.pixels.data(),frame.pixels.size());ReleaseMutex(mutex_.h);return true;
    }
};
class Pipe {
    Handle pipe_,shutdown_;std::thread thread_;vic06::Engine& engine_;std::atomic<bool>& stopping_;
    bool finish(BOOL ok,DWORD error,OVERLAPPED& op,DWORD& count){
        if(ok)return true;if(error!=ERROR_IO_PENDING)return false;
        HANDLE waits[]{shutdown_.h,op.hEvent};const auto state=WaitForMultipleObjects(2,waits,FALSE,2000);
        if(state!=WAIT_OBJECT_0+1){CancelIoEx(pipe_.h,&op);GetOverlappedResult(pipe_.h,&op,&count,TRUE);return false;}
        return GetOverlappedResult(pipe_.h,&op,&count,FALSE)!=FALSE;
    }
    void run() noexcept {
        while(WaitForSingleObject(shutdown_.h,0)!=WAIT_OBJECT_0){
            Handle event;event.h=CreateEventW(nullptr,TRUE,FALSE,nullptr);if(!event.h)return;OVERLAPPED op{};op.hEvent=event.h;DWORD count=0;
            BOOL connected=ConnectNamedPipe(pipe_.h,&op);auto error=connected?ERROR_SUCCESS:GetLastError();
            if(!connected && error==ERROR_IO_PENDING){HANDLE waits[]{shutdown_.h,event.h};if(WaitForMultipleObjects(2,waits,FALSE,INFINITE)==WAIT_OBJECT_0+1)connected=GetOverlappedResult(pipe_.h,&op,&count,FALSE);else {CancelIoEx(pipe_.h,&op);GetOverlappedResult(pipe_.h,&op,&count,TRUE);return;}}
            else if(error==ERROR_PIPE_CONNECTED)connected=TRUE;
            bool stop=false;
            if(connected){
                std::array<char,limit> input{};ResetEvent(event.h);op={};op.hEvent=event.h;
                auto ok=ReadFile(pipe_.h,input.data(),DWORD(input.size()),&count,&op);error=ok?ERROR_SUCCESS:GetLastError();
                if(finish(ok,error,op,count) && count>=sizeof(Header)){
                    Header header{};std::memcpy(&header,input.data(),sizeof(header));std::string body;
                    try{
                        const char device[16]="VIC-DEVICE-0001";
                        if(std::memcmp(header.magic,"V06C",4) || header.version!=1 || header.length!=count || std::memcmp(header.device,device,16))throw std::runtime_error("Invalid IPC version/length/device");
                        if(header.command==1){body="{\"stopping\":1}";stop=true;}
                        else body=engine_.command(header.command,std::string(input.data()+sizeof(header),count-sizeof(header)));
                        header.status=0;
                    }catch(const std::exception& e){header.status=1;body=vic06::json([&](cv::FileStorage& f){f<<"error"<<e.what();});std::cout<<"COMMAND_ERROR "<<e.what()<<std::endl;}
                    header.length=static_cast<std::uint32_t>(sizeof(header)+body.size());
                    std::vector<char> output(header.length);std::memcpy(output.data(),&header,sizeof(header));std::memcpy(output.data()+sizeof(header),body.data(),body.size());
                    ResetEvent(event.h);op={};op.hEvent=event.h;ok=WriteFile(pipe_.h,output.data(),DWORD(output.size()),&count,&op);error=ok?ERROR_SUCCESS:GetLastError();
                    if(finish(ok,error,op,count) && count==output.size()){
                        char ack=0;ResetEvent(event.h);op={};op.hEvent=event.h;ok=ReadFile(pipe_.h,&ack,1,&count,&op);error=ok?ERROR_SUCCESS:GetLastError();finish(ok,error,op,count);
                    }
                }
            }
            DisconnectNamedPipe(pipe_.h);if(stop){stopping_=true;return;}
        }
    }
public:
    Pipe(const std::wstring& name,vic06::Engine& engine,std::atomic<bool>& stopping):engine_(engine),stopping_(stopping){
        shutdown_.h=CreateEventW(nullptr,TRUE,FALSE,nullptr);if(!shutdown_.h)throw std::runtime_error("Cannot create shutdown event");
        pipe_.h=CreateNamedPipeW(name.c_str(),PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED|FILE_FLAG_FIRST_PIPE_INSTANCE,PIPE_TYPE_MESSAGE|PIPE_READMODE_MESSAGE|PIPE_WAIT|PIPE_REJECT_REMOTE_CLIENTS,1,limit,limit,2000,nullptr);
        if(pipe_.h==INVALID_HANDLE_VALUE)throw std::runtime_error("Cannot create local Engine pipe");thread_=std::thread([this]{run();});
    }
    ~Pipe(){SetEvent(shutdown_.h);if(thread_.joinable())thread_.join();}
};
}
int wmain(int argc,wchar_t** argv){try{
    if(argc==3 && std::wstring(argv[1])==L"--probe-source"){
        std::ifstream file(std::filesystem::path(argv[2]),std::ios::binary|std::ios::ate);
        if(!file || file.tellg()<=0 || file.tellg()>limit)throw std::invalid_argument("Missing/oversized source configuration");
        file.seekg(0);const std::string input((std::istreambuf_iterator<char>(file)),{});
        vic06::Engine engine;engine.command(3,input);std::cout<<engine.command(8,"{}")<<std::endl;return 0;
    }
    if(argc==2 && std::wstring(argv[1])==L"--help"){std::cout<<"VICEngine 06-0.6.5: local CameraCore preview; GenTL Producer NOT IMPLEMENTED\n--session <32 lowercase hex> --seconds <1..28800>\n";return 0;}
    if(argc!=5 || std::wstring(argv[1])!=L"--session" || std::wstring(argv[3])!=L"--seconds")throw std::invalid_argument("Expected --session token --seconds duration");
    const std::wstring token=argv[2];if(token.size()!=32 || token.find_first_not_of(L"0123456789abcdef")!=std::wstring::npos)throw std::invalid_argument("Invalid session token");
    const int seconds=std::stoi(argv[4]);if(seconds<1 || seconds>28800)throw std::invalid_argument("Duration outside1..28800");
    const auto name=L"Local\\VIC.06."+token;Preview preview(name,name+L".lock");vic06::Engine engine;std::atomic<bool> stopping{false};Pipe pipe(L"\\\\.\\pipe\\VIC.06."+token,engine,stopping);
    std::cout<<"READY build=06-0.6.5 local_preview=1 GenTL=NOT_IMPLEMENTED mapping_bytes="<<mapping_size<<std::endl;
    const auto deadline=vic06::now_ns()+std::uint64_t(seconds)*1000000000ull;auto log_at=vic06::now_ns();
    while(!stopping && vic06::now_ns()<deadline){engine.tick([&](const vic::Frame& f,std::uint64_t id){return preview.write(f,id);});
        if(vic06::now_ns()-log_at>=1000000000ull){std::cout<<"STATUS "<<engine.command(2,"{}")<<std::endl;log_at=vic06::now_ns();}Sleep(1);
    }
    std::cout<<"STOP build=06-0.6.5"<<std::endl;return 0;
}catch(const std::exception& e){std::cerr<<"ENGINE_ERROR "<<e.what()<<std::endl;return 1;}}
