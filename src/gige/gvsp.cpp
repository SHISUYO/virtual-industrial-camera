#include "gige/gvsp.hpp"
#include <stdexcept>

namespace vic {
namespace {
void header(Bytes& packet,std::uint16_t block,std::uint32_t id,std::uint8_t type) {
    if(!block || id>0xffffff) throw std::invalid_argument("Invalid classic GVSP IDs");
    packet.clear();put16(packet,0);put16(packet,block);put32(packet,(std::uint32_t(type)<<24)|id);
}
}
Bytes image_leader(std::uint16_t block,std::uint64_t timestamp,std::uint32_t width,std::uint32_t height,std::uint32_t pixel_format) {
    Bytes packet;packet.reserve(44);header(packet,block,0,1);
    put16(packet,0);put16(packet,1); // Flags=0, payload type IMAGE=1.
    put32(packet,std::uint32_t(timestamp>>32));put32(packet,std::uint32_t(timestamp));
    put32(packet,pixel_format);put32(packet,width);put32(packet,height);
    put32(packet,0);put32(packet,0);put16(packet,0);put16(packet,0);
    return packet;
}
Bytes image_trailer(std::uint16_t block,std::uint32_t id,std::uint32_t height) {
    Bytes packet;packet.reserve(16);header(packet,block,id,2);put32(packet,1);put32(packet,height);return packet;
}
void image_payload(Bytes& packet,std::uint16_t block,std::uint32_t id,const std::uint8_t* data,std::size_t size) {
    if(!data || !size || size>1500-gvsp_overhead) throw std::invalid_argument("Invalid G02 GVSP payload length");
    header(packet,block,id,3);packet.insert(packet.end(),data,data+size);
}
void fill_test_image(Bytes& image,std::uint16_t block) {
    image.resize(image_bytes);
    for(std::uint32_t y=0;y<image_height;++y)
        for(std::uint32_t x=0;x<image_width;++x)
            image[y*image_width+x]=std::uint8_t((x+y+block)&255);
}
std::uint16_t next_block(std::uint16_t block) { return block==65535?1:std::uint16_t(block+1); }
}
