#include "gige/gvsp.hpp"
#include <algorithm>
#include <iostream>
#include <stdexcept>

using namespace vic;
static void expect(bool result,const char* text) {if(!result) throw std::runtime_error(text);}
static Bytes request(std::uint16_t cmd,std::initializer_list<std::uint32_t> words) {
    Bytes p{0x42,1};put16(p,cmd);put16(p,static_cast<std::uint16_t>(words.size()*4));put16(p,42);
    for(auto value:words) put32(p,value);return p;
}
int main() {
    try {
        Gvcp core({},{});const Peer owner{0xac11f001,50100},other{0xac11f001,50101};
        auto call=[&](std::uint16_t cmd,std::initializer_list<std::uint32_t> words,Peer peer,std::uint16_t status,std::uint64_t time=1){
            auto result=core.process(request(cmd,words),peer,time);
            expect(result && get16(result->data())==status,"Unexpected control response");return *result;
        };
        call(0x82,{wire::acquisition,1},other,wire::access_denied);
        call(0x82,{0xa00,2},owner,0);
        call(0x82,{wire::acquisition,1},owner,wire::invalid_parameter);
        call(0x82,{0xd04,216},owner,wire::invalid_parameter);
        call(0x82,{0xd04,1504},owner,wire::invalid_parameter);
        call(0x82,{0xd04,1401},owner,wire::invalid_parameter);
        call(0x82,{0xd04,0x80000578},owner,wire::invalid_parameter);
        call(0x82,{0xd18,0xe0000001},owner,wire::invalid_parameter);
        call(0x82,{0xd00,65536},owner,wire::invalid_parameter);
        call(0x86,{0xd00,50100},other,wire::access_denied);
        call(0x86,{0xd00,50100,216},owner,wire::invalid_parameter);
        expect(core.stream_settings().port==0,"WriteMem partially applied");
        call(0x86,{0xd18,0xac11f001},owner,0);
        call(0x86,{0xd00,50100},owner,0);
        call(0x86,{0xd04,0x40000578},owner,0);
        expect(core.stream_settings().dont_fragment,"DF flag not preserved");
        call(0x82,{wire::acquisition,1},owner,0);
        expect(core.stream_settings().acquiring,"Start not applied");
        call(0x82,{0xd04,1200},owner,wire::access_denied);
        call(0x82,{0xd18,0xac11f002},owner,wire::access_denied);
        call(0x82,{wire::acquisition,0},other,wire::access_denied);
        call(0x82,{wire::acquisition,0},owner,0);
        expect(!core.stream_settings().acquiring,"Stop not applied");
        call(0x82,{wire::acquisition,1},owner,0);
        call(0x82,{0xa00,0},owner,0);
        expect(!core.stream_settings().acquiring,"Release did not stop stream");
        call(0x82,{0xa00,2},owner,0);
        call(0x82,{wire::acquisition,1},owner,0);
        core.expire(3001);
        expect(!core.stream_settings().acquiring,"Heartbeat expiry did not stop stream");
        expect(next_block(65535)==1 && next_block(1)==2,"BlockID wrap");
        const auto leader=image_leader(65535,0x123456789abcdef0ull);
        expect(leader.size()==44 && get16(leader.data())==0 && get16(leader.data()+2)==65535 &&
            get32(leader.data()+4)==0x01000000 && get16(leader.data()+10)==1 &&
            get32(leader.data()+12)==0x12345678 && get32(leader.data()+16)==0x9abcdef0 &&
            get32(leader.data()+20)==0x01080001 && get32(leader.data()+24)==640 &&
            get32(leader.data()+28)==480,"Leader wire fields");
        Bytes image;fill_test_image(image,65535);
        for(auto size:{220u,1200u,1400u,1500u}) {
            const auto capacity=size-gvsp_overhead;std::size_t total=0;std::uint32_t id=1;Bytes packet;
            while(total<image.size()) {
                auto count=std::min<std::size_t>(capacity,image.size()-total);
                image_payload(packet,65535,id,image.data()+total,count);
                expect(packet.size()+28<=size && get32(packet.data()+4)==(0x03000000|id),"Payload packet sizing/IDs");
                for(std::size_t n=0;n<count;++n) {
                    auto offset=total+n;
                    expect(packet[8+n]==((offset%640+offset/640+65535)&255),"Pixel or payload order");
                }
                total+=count;++id;
            }
            const auto trailer=image_trailer(65535,id);
            expect(total==307200 && trailer.size()==16 && get32(trailer.data()+4)==(0x02000000|id) &&
                get32(trailer.data()+8)==1 && get32(trailer.data()+12)==480,"Trailer fields and total image bytes");
        }
        bool rejected=false;try {image_leader(0,0);}catch(const std::invalid_argument&){rejected=true;}
        expect(rejected,"Invalid BlockID accepted");
        std::cout<<"PASS: stream ownership/start/stop/heartbeat, WriteMem atomicity, GVSP leader/payload/trailer, packet sizes, pixels and BlockID wrap\n";
        return 0;
    } catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
