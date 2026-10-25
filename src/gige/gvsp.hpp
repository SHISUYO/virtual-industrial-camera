#pragma once
#include "gige/gvcp.hpp"

namespace vic {
constexpr std::uint32_t mono8=0x01080001, image_width=640, image_height=480;
constexpr std::size_t image_bytes=image_width*image_height;
// Classic GVSP definitions from fixed Aravis 0.8.36 headers/construction code.
// IP(20)+UDP(8)+GVSP(8), no extended IDs or padding. Not a compliance claim.
constexpr std::uint32_t gvsp_overhead=36;
Bytes image_leader(std::uint16_t block,std::uint64_t timestamp_ns,std::uint32_t width=640,std::uint32_t height=480,std::uint32_t pixel_format=mono8);
Bytes image_trailer(std::uint16_t block,std::uint32_t packet_id,std::uint32_t height=480);
void image_payload(Bytes& packet,std::uint16_t block,std::uint32_t packet_id,
                   const std::uint8_t* data,std::size_t size);
void fill_test_image(Bytes& image,std::uint16_t block);
std::uint16_t next_block(std::uint16_t block);
}
