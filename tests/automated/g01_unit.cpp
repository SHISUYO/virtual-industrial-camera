#include "gige/gvcp.hpp"
#include <iostream>
#include <stdexcept>

using namespace vic;
void require(bool condition,const char* what){if(!condition) throw std::runtime_error(what);}
Bytes request(std::uint16_t cmd,Bytes payload={},std::uint8_t flags=1) {
    Bytes p{0x42,flags};put16(p,cmd);put16(p,static_cast<std::uint16_t>(payload.size()));put16(p,0x2345);
    p.insert(p.end(),payload.begin(),payload.end());return p;
}
Bytes words(std::initializer_list<std::uint32_t> list) {Bytes p;for(auto w:list) put32(p,w);return p;}
int main() {
    try {
        Gvcp core({},{});Peer a{1,10},b{1,11};
        auto status=[&](const Bytes& p,Peer peer,std::uint64_t time,std::uint16_t expected){
            auto r=core.process(p,peer,time);require(r.has_value(),"Missing response");
            require(get16(r->data())==expected,"Wrong response status");
            require(get16(r->data()+6)==0x2345,"Request ID not echoed");return *r;
        };
        auto d=status(request(wire::discovery),a,0,0);require(d.size()==256,"Discovery size");
        for(std::size_t n=0;n<8;++n) require(!core.process(Bytes(n,0x42),a,0),"Short header must be silent");
        auto truncated=request(wire::read_reg,words({0}));truncated.pop_back();
        status(truncated,a,0,wire::invalid_header);
        status(request(wire::read_reg,words({1})),a,0,wire::bad_alignment);
        status(request(wire::read_reg,words({0xfffffffc})),a,0,wire::invalid_access);
        status(request(wire::read_mem,words({0xfffffffc,8})),a,0,wire::invalid_access);
        status(request(wire::write_reg,words({wire::heartbeat,100})),a,0,wire::access_denied);
        status(request(wire::write_reg,words({wire::privilege,2})),a,0,0);
        status(request(wire::write_reg,words({wire::privilege,2})),b,1,wire::access_denied);
        status(request(wire::write_reg,words({0x48,0})),a,1,wire::write_protect);
        status(request(wire::write_reg,words({wire::heartbeat,100,0x48,0})),a,1,wire::write_protect);
        auto r=status(request(wire::read_reg,words({wire::heartbeat})),a,1,0);
        require(get32(r.data()+8)==3000,"Invalid batch partially changed state");
        status(request(wire::write_reg,words({wire::heartbeat,100})),a,2,0);
        status(request(wire::write_reg,words({wire::privilege,2})),b,101,wire::access_denied);
        status(request(wire::write_reg,words({wire::privilege,1})),b,102,0);
        require(core.expirations()==1,"Expiry boundary incorrect");
        status(request(wire::read_reg,words({0})),a,103,wire::access_denied);
        status(request(wire::write_reg,words({wire::privilege,0})),b,104,0);
        status(request(wire::write_reg,words({wire::privilege,2})),a,105,0);
        status(request(wire::read_reg,words({wire::privilege})),a,190,0);
        status(request(wire::write_reg,words({wire::privilege,2})),b,205,wire::access_denied);
        require(!core.process(request(wire::write_reg,words({wire::heartbeat,500}),0),a,206),"No-ACK request must be silent");
        r=status(request(wire::read_reg,words({wire::heartbeat})),a,207,0);
        require(get32(r.data()+8)==500,"No-ACK write not applied");
        status(request(0x86,words({0x48,0})),a,208,wire::write_protect);
        // Every prefix and deterministic malformed byte sequence must be bounded and safe.
        std::uint32_t random=1234567;
        for(unsigned i=0;i<10000;++i) {
            random=random*1664525u+1013904223u;Bytes p(random%800);
            for(auto& c:p){random=random*1664525u+1013904223u;c=std::uint8_t(random>>24);}
            auto response=core.process(p,a,209);
            require(!response || response->size()<=548,"Unbounded reply");
        }
        std::cout<<"PASS: wire bounds, overflow, permissions, atomic validation, exclusive access, heartbeat, malformed corpus\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}
}
