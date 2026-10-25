#pragma once
#include "gige/gvcp.hpp"
#include "gige/gvsp.hpp"
#include <array>
#include <fstream>
#include <functional>

namespace tap_poc {
using vic::Bytes;
using Mac=std::array<std::uint8_t,6>;
struct Config {
    std::uint32_t host=0x0acb0001,camera=0x0acb0002,mask=0xffffff00;
    Mac host_mac{0x02,0x56,0x49,0x43,0x10,0x01};
    Mac camera_mac{0x02,0x56,0x49,0x43,0,1};
    vic::SourceOptions source;
    vic::Identity identity;
    vic::CameraSettings initial_camera;
};
std::uint16_t checksum(const Bytes& bytes);
Bytes udp_frame(const Mac& src_mac,const Mac& dst_mac,std::uint32_t src,std::uint32_t dst,
                std::uint16_t sport,std::uint16_t dport,const Bytes& data,std::uint16_t id=1,bool df=false);
class Engine {
public:
    explicit Engine(Config config,std::function<void(const std::string&)> log);
    std::vector<Bytes> receive(const Bytes& frame,std::uint64_t now_ms);
    std::vector<Bytes> poll(std::uint64_t now_ms);
    void configure_initial_stream(std::uint32_t packet_size,std::uint32_t delay){protocol_.configure_initial_stream(packet_size,delay);}
    vic::StreamSettings settings() const{return protocol_.stream_settings();}
    std::optional<vic::Peer> controller() const{return protocol_.controller();}
    Config config;
    std::uint64_t rejected=0,gvcp=0,arp=0,frames=0;
private:
    vic::Gvcp protocol_;
    vic::CameraCore core_;
    std::function<void(const std::string&)> log_;
    std::uint16_t block_=65530,ip_id_=0;
    std::optional<vic::StreamSettings> previous_;
    void sync(std::uint64_t now_ms);
};
// Live files contain device-boundary RX and successfully submitted TX bytes.
// Offline files are explicitly named synthetic.pcap. Neither proves NDIS delivery.
class Pcap {
public:
    explicit Pcap(const std::string& path);
    void record(const Bytes& frame);
private:
    std::ofstream file_;
    void u32(std::uint32_t value);
};
int offline(const std::string& folder);
}
