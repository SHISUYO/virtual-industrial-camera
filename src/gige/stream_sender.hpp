#pragma once
#include <winsock2.h>
#include "gige/gvcp.hpp"
#include <condition_variable>
#include <functional>
#include <mutex>
#include <thread>

namespace vic {
class StreamSender {
public:
    StreamSender(std::uint32_t bind_ip,std::function<void(const std::string&)> log,SourceOptions source={});
    ~StreamSender();
    StreamSender(const StreamSender&)=delete;
    StreamSender& operator=(const StreamSender&)=delete;
    std::uint16_t source_port() const {return port_;}
    std::uint64_t send_errors() const {return failures_;} // Only read after finish()/join.
    // Serialized with sending: no further datagrams from the prior configuration
    // can be sent after this returns. Stop ACK is sent only after this barrier.
    void configure(StreamSettings settings);
    void finish();
    std::uint64_t completed_triggers();
private:
    SOCKET socket_=INVALID_SOCKET;
    HANDLE pacer_=nullptr;
    std::uint16_t port_=0,block_=65530; // Exercise classic BlockID wrap in every long test.
    StreamSettings settings_;
    CameraCore core_;
    bool fatal_=false;
    std::mutex mutex_;
    std::condition_variable wake_;
    bool shutdown_=false;
    std::thread worker_;
    std::function<void(const std::string&)> log_;
    std::uint64_t frames_=0,packets_=0,failures_=0;
    void run();
    bool send_packet(const Bytes& packet,const sockaddr_in& target);
};
}
