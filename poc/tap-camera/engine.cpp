#include "engine.hpp"
#include <algorithm>
#include <chrono>
#include <stdexcept>

namespace tap_poc {
namespace {
bool mac_is(const Bytes& b,std::size_t at,const Mac& mac) {return std::equal(mac.begin(),mac.end(),b.begin()+at);}
Bytes pseudo(std::uint32_t src,std::uint32_t dst,const Bytes& udp) {
    Bytes b;vic::put32(b,src);vic::put32(b,dst);b.push_back(0);b.push_back(17);
    vic::put16(b,static_cast<std::uint16_t>(udp.size()));b.insert(b.end(),udp.begin(),udp.end());return b;
}
void set16(Bytes& b,std::size_t pos,std::uint16_t v) {b[pos]=std::uint8_t(v>>8);b[pos+1]=std::uint8_t(v);}
}
std::uint16_t checksum(const Bytes& b) {
    std::uint32_t sum=0;
    for(std::size_t i=0;i<b.size();i+=2) sum+=(std::uint32_t(b[i])<<8)|(i+1<b.size()?b[i+1]:0);
    while(sum>>16) sum=(sum&0xffff)+(sum>>16);
    return static_cast<std::uint16_t>(~sum);
}
Bytes udp_frame(const Mac& sm,const Mac& dm,std::uint32_t src,std::uint32_t dst,
                std::uint16_t sp,std::uint16_t dp,const Bytes& data,std::uint16_t id,bool df) {
    if(data.size()>1472) throw std::invalid_argument("PoC UDP payload exceeds MTU1500");
    Bytes udp;vic::put16(udp,sp);vic::put16(udp,dp);vic::put16(udp,std::uint16_t(8+data.size()));vic::put16(udp,0);
    udp.insert(udp.end(),data.begin(),data.end());auto c=checksum(pseudo(src,dst,udp));set16(udp,6,c?c:0xffff);
    Bytes ip{0x45,0};vic::put16(ip,std::uint16_t(20+udp.size()));vic::put16(ip,id);vic::put16(ip,df?0x4000:0);
    ip.push_back(64);ip.push_back(17);vic::put16(ip,0);vic::put32(ip,src);vic::put32(ip,dst);set16(ip,10,checksum(ip));
    Bytes frame(dm.begin(),dm.end());frame.insert(frame.end(),sm.begin(),sm.end());vic::put16(frame,0x0800);
    frame.insert(frame.end(),ip.begin(),ip.end());frame.insert(frame.end(),udp.begin(),udp.end());
    if(frame.size()<60) frame.resize(60,0);return frame;
}
Engine::Engine(Config c,std::function<void(const std::string&)> log):config(c),
    protocol_(c.identity,vic::Network{c.camera,c.mask,0,c.camera_mac},true),core_(c.source),log_(std::move(log)) {
    if(c.host==c.camera || (c.host&c.mask)!=(c.camera&c.mask) || c.host_mac==c.camera_mac)
        throw std::invalid_argument("Camera identity must differ from host in the test subnet");
    protocol_.set_source_port(49152);
    protocol_.configure_initial_camera(c.initial_camera);
}
void Engine::sync(std::uint64_t now) {
    protocol_.expire(now);auto s=protocol_.stream_settings();auto camera=s.camera;camera.acquiring=s.acquiring;
    core_.configure(camera,now*1000000);protocol_.set_completed_triggers(core_.completed_triggers());
    if(!previous_ || !(s==*previous_)) {
        log_("STREAM_CONFIG acquiring="+std::to_string(s.acquiring)+" destination_host_order="+std::to_string(s.destination)+
             " port="+std::to_string(s.port)+" packet_size="+std::to_string(s.packet_size));previous_=s;
    }
}
std::vector<Bytes> Engine::receive(const Bytes& b,std::uint64_t now) {
    sync(now);auto reject=[&](){++rejected;return std::vector<Bytes>{};};
    const Mac broadcast{255,255,255,255,255,255};
    if(b.size()<14 || b.size()>1514 || !mac_is(b,6,config.host_mac) ||
       (!mac_is(b,0,config.camera_mac) && !mac_is(b,0,broadcast))) return reject();
    const auto type=vic::get16(b.data()+12);
    if(type==0x0806) {
        if(b.size()<42 || vic::get16(b.data()+14)!=1 || vic::get16(b.data()+16)!=0x0800 ||
           b[18]!=6 || b[19]!=4 || vic::get16(b.data()+20)!=1 || !mac_is(b,22,config.host_mac) ||
           vic::get32(b.data()+28)!=config.host || vic::get32(b.data()+38)!=config.camera) return reject();
        Bytes out(config.host_mac.begin(),config.host_mac.end());out.insert(out.end(),config.camera_mac.begin(),config.camera_mac.end());
        vic::put16(out,0x0806);vic::put16(out,1);vic::put16(out,0x0800);out.push_back(6);out.push_back(4);vic::put16(out,2);
        out.insert(out.end(),config.camera_mac.begin(),config.camera_mac.end());vic::put32(out,config.camera);
        out.insert(out.end(),config.host_mac.begin(),config.host_mac.end());vic::put32(out,config.host);out.resize(60,0);
        ++arp;log_("ARP_REPLY own_camera_only=1");return {out};
    }
    if(type!=0x0800 || b.size()<42 || b[14]!=0x45 || b[23]!=17 ||
       (vic::get16(b.data()+20)&0xbfff) || !b[22] || checksum(Bytes(b.begin()+14,b.begin()+34))) return reject();
    const auto total=vic::get16(b.data()+16),length=vic::get16(b.data()+38);
    if(total<28 || std::size_t(total)+14>b.size() || length!=total-20 || length<8) return reject();
    const auto src=vic::get32(b.data()+26),dst=vic::get32(b.data()+30);
    if(src!=config.host || (dst!=config.camera && dst!=0xffffffff && dst!=(config.camera|~config.mask)) ||
       vic::get16(b.data()+36)!=3956) return reject();
    Bytes udp(b.begin()+34,b.begin()+14+total);
    if(vic::get16(udp.data()+6) && checksum(pseudo(src,dst,udp))) return reject();
    const auto port=vic::get16(udp.data());Bytes request(udp.begin()+8,udp.end());
    auto reply=protocol_.process(request,{src,port},now);++gvcp;
    log_("GVCP command="+std::to_string(request.size()>=4?vic::get16(request.data()+2):0)+
         " peer_port="+std::to_string(port)+" address="+(request.size()>=12?std::to_string(vic::get32(request.data()+8)):"absent")+
         " value="+(request.size()>=16?std::to_string(vic::get32(request.data()+12)):"absent")+
         " status="+(reply?std::to_string(vic::get16(reply->data())):"silent"));
    sync(now);
    if(!reply) return {};
    return {udp_frame(config.camera_mac,config.host_mac,config.camera,src,3956,port,*reply,++ip_id_)};
}
std::vector<Bytes> Engine::poll(std::uint64_t now) {
    sync(now);const auto s=protocol_.stream_settings();
    if(!s.acquiring || s.destination!=config.host || !s.port) return {};
    auto frame=core_.next_frame(vic::next_block(block_),now*1000000);if(!frame)return {};
    block_=vic::next_block(block_);std::vector<Bytes> packets;
    auto emit=[&](const Bytes& payload){packets.push_back(udp_frame(config.camera_mac,config.host_mac,config.camera,
        config.host,49152,static_cast<std::uint16_t>(s.port),payload,++ip_id_,s.dont_fragment));};
    emit(vic::image_leader(block_,frame->timestamp_ns,s.camera.width,s.camera.height,s.camera.pixel_format));
    const auto capacity=s.packet_size-vic::gvsp_overhead;std::uint32_t id=1;Bytes payload;
    for(std::size_t i=0;i<frame->pixels.size();i+=capacity) {
        vic::image_payload(payload,block_,id++,frame->pixels.data()+i,std::min<std::size_t>(capacity,frame->pixels.size()-i));emit(payload);
    }
    emit(vic::image_trailer(block_,id,s.camera.height));++frames;
    log_("GVSP_FRAME_GENERATED block="+std::to_string(block_)+" packets="+std::to_string(packets.size())+
         " destination_port="+std::to_string(s.port)+" bytes="+std::to_string(frame->pixels.size()));return packets;
}
void Pcap::u32(std::uint32_t v) {for(unsigned i=0;i<4;++i)file_.put(static_cast<char>(v>>(8*i)));}
Pcap::Pcap(const std::string& path):file_(path,std::ios::binary) {
    if(!file_)throw std::runtime_error("Cannot create pcap");u32(0xa1b2c3d4);u32(0x00040002);u32(0);u32(0);u32(65535);u32(1);
}
void Pcap::record(const Bytes& b) {
    if(file_.tellp()>std::streamoff(256*1024*1024))throw std::runtime_error("PoC pcap limit256MiB reached; stopping");
    const auto t=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    u32(static_cast<std::uint32_t>(t/1000000));u32(static_cast<std::uint32_t>(t%1000000));u32(static_cast<std::uint32_t>(b.size()));u32(static_cast<std::uint32_t>(b.size()));
    file_.write(reinterpret_cast<const char*>(b.data()),static_cast<std::streamsize>(b.size()));file_.flush();
    if(!file_)throw std::runtime_error("pcap write failed");
}
}
