#include "gige/stream_sender.hpp"
#include <ws2tcpip.h>
#include "gige/gvsp.hpp"
#include <algorithm>
#include <chrono>
#include <stdexcept>

namespace vic {
StreamSender::StreamSender(std::uint32_t ip,std::function<void(const std::string&)> log,SourceOptions source):core_(std::move(source)),log_(std::move(log)) {
    socket_=::socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);
    if(socket_==INVALID_SOCKET) throw std::runtime_error("GVSP socket failed");
    sockaddr_in local{};local.sin_family=AF_INET;local.sin_addr.s_addr=htonl(ip);
    DWORD timeout=100;
    if(setsockopt(socket_,SOL_SOCKET,SO_SNDTIMEO,reinterpret_cast<const char*>(&timeout),sizeof(timeout))==SOCKET_ERROR ||
       bind(socket_,reinterpret_cast<sockaddr*>(&local),sizeof(local))==SOCKET_ERROR) {
        auto error=WSAGetLastError();closesocket(socket_);socket_=INVALID_SOCKET;
        throw std::runtime_error("GVSP bind/options failed: "+std::to_string(error));
    }
    int length=sizeof(local);
    if(getsockname(socket_,reinterpret_cast<sockaddr*>(&local),&length)==SOCKET_ERROR) {
        closesocket(socket_);socket_=INVALID_SOCKET;throw std::runtime_error("GVSP source port query failed");
    }
    port_=ntohs(local.sin_port);
    pacer_=CreateWaitableTimerExW(nullptr,nullptr,CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,TIMER_MODIFY_STATE|SYNCHRONIZE);
    if(!pacer_) {
        closesocket(socket_);socket_=INVALID_SOCKET;
        throw std::runtime_error("High-resolution GVSP packet pacer unavailable: "+std::to_string(GetLastError()));
    }
    try {worker_=std::thread(&StreamSender::run,this);}
    catch(...) {CloseHandle(pacer_);pacer_=nullptr;closesocket(socket_);socket_=INVALID_SOCKET;throw;}
}
StreamSender::~StreamSender(){finish();}
void StreamSender::configure(StreamSettings settings) {
    std::lock_guard<std::mutex> lock(mutex_);
    if(fatal_) throw std::runtime_error("Camera Core worker failed; see CORE_ERROR log");
    if(settings_==settings) return;
    const int df=settings.dont_fragment?1:0;
    if(setsockopt(socket_,IPPROTO_IP,IP_DONTFRAGMENT,reinterpret_cast<const char*>(&df),sizeof(df))==SOCKET_ERROR)
        throw std::runtime_error("GVSP IP_DONTFRAGMENT failed: "+std::to_string(WSAGetLastError()));
    auto camera=settings.camera;camera.acquiring=settings.acquiring;
    const auto now=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
    core_.configure(camera,static_cast<std::uint64_t>(now));
    settings_=settings;
    log_("STREAM_CONFIG acquiring="+std::to_string(settings.acquiring)+" destination_host_order="+
        std::to_string(settings.destination)+" port="+std::to_string(settings.port)+" packet_size="+std::to_string(settings.packet_size));
    wake_.notify_all();
}
std::uint64_t StreamSender::completed_triggers() {
    std::lock_guard<std::mutex> lock(mutex_);return core_.completed_triggers();
}
void StreamSender::finish() {
    {
        std::lock_guard<std::mutex> lock(mutex_);shutdown_=true;wake_.notify_all();
    }
    if(worker_.joinable()) worker_.join();
    if(pacer_) {CloseHandle(pacer_);pacer_=nullptr;}
    if(socket_!=INVALID_SOCKET) {
        closesocket(socket_);socket_=INVALID_SOCKET;
        log_("STREAM_STOP sent_frames="+std::to_string(frames_)+" sent_packets="+std::to_string(packets_)+" send_errors="+std::to_string(failures_));
    }
}
bool StreamSender::send_packet(const Bytes& packet,const sockaddr_in& target) {
    const auto count=sendto(socket_,reinterpret_cast<const char*>(packet.data()),static_cast<int>(packet.size()),0,
        reinterpret_cast<const sockaddr*>(&target),sizeof(target));
    if(count!=static_cast<int>(packet.size())) {
        ++failures_;log_("GVSP_SEND_ERROR wsa="+std::to_string(WSAGetLastError()));return false;
    }
    ++packets_;return true;
}
void StreamSender::run() {
    using Clock=std::chrono::steady_clock;
    Bytes packet;packet.reserve(1500);
    std::unique_lock<std::mutex> lock(mutex_);
    try {
    while(!shutdown_) {
        if(!settings_.acquiring || !settings_.destination || !settings_.port) {
            wake_.wait(lock,[&]{return shutdown_ || (settings_.acquiring && settings_.destination && settings_.port);});
            continue;
        }
        sockaddr_in target{};target.sin_family=AF_INET;target.sin_addr.s_addr=htonl(settings_.destination);
        target.sin_port=htons(static_cast<std::uint16_t>(settings_.port));
        const auto stamp=std::uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count());
        auto frame=core_.next_frame(next_block(block_),stamp);
        if(!frame) {wake_.wait_for(lock,std::chrono::milliseconds(1));continue;}
        block_=next_block(block_);
        const auto& image=frame->pixels;
        bool success=send_packet(image_leader(block_,frame->timestamp_ns,frame->settings.width,frame->settings.height,frame->settings.pixel_format),target);
        const auto capacity=settings_.packet_size-gvsp_overhead;
        std::uint32_t packet_id=1;
        for(std::size_t offset=0;success && offset<image.size();offset+=capacity) {
            image_payload(packet,block_,packet_id++,image.data()+offset,std::min<std::size_t>(capacity,image.size()-offset));
            success=send_packet(packet,target);
            // Bound each burst to 8 datagrams. A Windows high-resolution timer
            // avoids Sleep(1)'s coarse resolution while giving the receiver time
            // to drain its UDP socket (especially on the very first frame).
            if(success && (packet_id-1)%8==0 && offset+capacity<image.size()) {
                LARGE_INTEGER due{};due.QuadPart=-2500; // Relative 250 microseconds, in 100 ns units.
                if(!SetWaitableTimer(pacer_,&due,0,nullptr,nullptr,FALSE) || WaitForSingleObject(pacer_,100)!=WAIT_OBJECT_0) {
                    ++failures_;log_("GVSP_PACER_ERROR win32="+std::to_string(GetLastError()));success=false;
                }
            }
        }
        if(success) success=send_packet(image_trailer(block_,packet_id,frame->settings.height),target);
        if(success) ++frames_;
        // Release the serialization lock between frames so control/Stop can proceed.
        wake_.wait_for(lock,std::chrono::microseconds(100));
    }
    } catch(const std::exception& error) {
        ++failures_;fatal_=true;log_(std::string("CORE_ERROR ")+error.what());
    }
}
}
