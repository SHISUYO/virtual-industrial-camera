#include "engine.hpp"
#include <filesystem>
#include <iostream>
#include <stdexcept>

namespace tap_poc {
int offline(const std::string& folder) {
    std::filesystem::create_directories(folder);
    std::ofstream log(folder+"/offline.txt");auto emit=[&](const std::string& s){log<<s<<'\n';std::cout<<s<<'\n';};
    emit("MODE=OFFLINE synthetic_vectors=1 driver_opened=0 compatibility=NOT_TESTED");
    Config c;Engine engine(c,emit);Pcap cap(folder+"/synthetic.pcap");
    auto require=[](bool ok,const char* text){if(!ok)throw std::runtime_error(text);};
    const Mac broadcast{255,255,255,255,255,255};
    Bytes arp(broadcast.begin(),broadcast.end());arp.insert(arp.end(),c.host_mac.begin(),c.host_mac.end());
    vic::put16(arp,0x0806);vic::put16(arp,1);vic::put16(arp,0x0800);arp.push_back(6);arp.push_back(4);vic::put16(arp,1);
    arp.insert(arp.end(),c.host_mac.begin(),c.host_mac.end());vic::put32(arp,c.host);arp.resize(38,0);vic::put32(arp,c.camera);arp.resize(60,0);
    cap.record(arp);auto out=engine.receive(arp,100);require(out.size()==1,"ARP reply missing");cap.record(out[0]);
    require(vic::get32(out[0].data()+28)==c.camera && vic::get16(out[0].data()+20)==2,"ARP identity");
    std::uint16_t request_id=10;
    auto command=[&](std::uint16_t cmd,Bytes data={},bool broadcast_request=false){
        Bytes gvcp{0x42,static_cast<std::uint8_t>(broadcast_request?0x11:1)};
        vic::put16(gvcp,cmd);vic::put16(gvcp,static_cast<std::uint16_t>(data.size()));vic::put16(gvcp,++request_id);gvcp.insert(gvcp.end(),data.begin(),data.end());
        auto b=udp_frame(c.host_mac,broadcast_request?broadcast:c.camera_mac,c.host,broadcast_request?0xffffffff:c.camera,50000,3956,gvcp);
        cap.record(b);auto response=engine.receive(b,100);
        require(response.size()==1,"GVCP ACK missing");cap.record(response[0]);
        require(vic::get16(response[0].data()+42)==0 && vic::get16(response[0].data()+44)==cmd+1,"GVCP ACK status/command");
        return response[0];
    };
    auto discovery=command(2,{},true);
    require(vic::get32(discovery.data()+50+0x24)==c.camera,"Discovery camera IP");
    auto write=[&](std::uint32_t address,std::uint32_t value){Bytes b;vic::put32(b,address);vic::put32(b,value);command(0x82,b);};
    write(0xa00,2);write(0xd18,c.host);write(0xd00,50001);write(0xd04,1500);
    auto frame=[&](std::uint64_t now){auto packets=engine.poll(now);require(!packets.empty(),"No frame generated");for(const auto& b:packets)cap.record(b);};
    write(0x20000,1);frame(100);write(0x20000,0);
    write(0x2000c,vic::pfnc_rgb8);write(0x20000,1);frame(100);write(0x20000,0);
    write(0x20014,1);write(0x20000,1);
    require(engine.poll(100).empty(),"Triggered mode emitted before command");
    write(0x20018,1);frame(100);require(engine.poll(101).empty(),"Duplicate software-trigger frame");
    write(0x20000,0);write(0xa00,0);
    require(engine.poll(102).empty(),"Frame after stop");
    // Reopen same single virtual endpoint, as a new control session after release.
    write(0xa00,2);write(0x20014,0);write(0x20000,1);frame(100);write(0x20000,0);write(0xa00,0);
    Bytes query{0x42,1,0,2,0,0,0,77};auto valid=udp_frame(c.host_mac,c.camera_mac,c.host,c.camera,50000,3956,query);
    auto invalid=[&](Bytes b){auto count=engine.rejected;require(engine.receive(b,110).empty(),"Invalid frame emitted reply");require(engine.rejected==count+1,"Invalid frame not rejected");};
    auto bad=valid;bad[24]^=1;invalid(bad); // IPv4 checksum.
    bad=valid;bad[48]^=1;invalid(bad); // UDP checksum (GVCP body mutated).
    bad=valid;bad.resize(35);invalid(bad); // Truncated UDP.
    bad=valid;bad[6]^=0x10;invalid(bad); // Other source MAC.
    bad=arp;bad[41]^=1;invalid(bad); // Other ARP target.
    bad=valid;bad[20]=0x20;bad[24]=bad[25]=0;
    auto sum=checksum(Bytes(bad.begin()+14,bad.begin()+34));bad[24]=std::uint8_t(sum>>8);bad[25]=std::uint8_t(sum);invalid(bad); // Fragment.
    require(engine.frames==4 && engine.rejected==6,"Offline counts");
    emit("PASS: OFFLINE ARP/discovery/control/Mono8/RGB8/software-trigger/stop/reopen; 4 frames; 6 malformed frames rejected");
    emit("NOT TESTED: TAP driver I/O, NDIS capture, VisionPro discovery/open/acquisition/valid frames");return 0;
}
}
