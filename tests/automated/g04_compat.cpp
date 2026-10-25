#include "gige/gvcp.hpp"
#include <iostream>
#include <stdexcept>

using namespace vic;
static void check(bool v,const char* message) {if(!v) throw std::runtime_error(message);}
int main() {
    try {
        Gvcp camera({}, {},true);
        auto read=[&](unsigned address,unsigned bytes,unsigned reserved=0) {
            Bytes p{0x42,1};put16(p,wire::read_mem);put16(p,8);put16(p,42);
            put32(p,address);put16(p,static_cast<std::uint16_t>(reserved));put16(p,static_cast<std::uint16_t>(bytes));
            auto response=camera.process(p,{1,1},0);check(response.has_value(),"No ReadMem ACK");return *response;
        };
        for(unsigned size:{512u,516u,536u}) {
            auto p=read(wire::xml_base,size);
            check(get16(p.data())==0 && p.size()==12+size && get16(p.data()+4)==4+size && get32(p.data()+8)==wire::xml_base,"ReadMem ACK framing/length");
            check(std::string(p.begin()+12,p.end())==camera.xml().substr(0,size),"XML bytes differ");
        }
        std::string xml;
        for(unsigned offset=0;offset<camera.xml().size();offset+=536) {
            const auto remaining=camera.xml().size()-offset;
            const auto count=static_cast<unsigned>(remaining>=536?536:((remaining+3)&~std::size_t(3)));
            auto p=read(wire::xml_base+offset,count);check(get16(p.data())==0,"XML chunk failed");
            xml.append(p.begin()+12,p.end());
        }
        xml.resize(camera.xml().size());check(xml==camera.xml(),"536-byte XML reconstruction");
        check(get16(read(wire::xml_base,540).data())==wire::invalid_parameter,"Oversized read accepted");
        check(get16(read(wire::xml_base,534).data())==wire::bad_alignment,"Unaligned read accepted");
        check(get16(read(wire::xml_base,536,1).data())==wire::invalid_parameter,"Reserved bits accepted");
        check(get16(read(0xfffffffc,536).data())==wire::invalid_access,"Address wrap accepted");
        std::cout<<"PASS: Cognex 536-byte XML reads/reassembly, ACK fields, bounds/alignment/reserved/overflow\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<"FAIL: "<<error.what()<<'\n';return 1;}
}
