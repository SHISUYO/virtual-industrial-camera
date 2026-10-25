#pragma once
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>
#include <utility>

namespace vic {
// PFNC values cross-checked with Aravis 0.8.36 arvenums.h.
constexpr std::uint32_t pfnc_mono8=0x01080001, pfnc_rgb8=0x02180014;
constexpr std::uint32_t max_dimension=6000;
struct CameraSettings {
    std::uint32_t width=640,height=480,pixel_format=pfnc_mono8,fps_milli=30000;
    bool acquiring=false,trigger_mode=false;
    std::uint32_t trigger_delay_us=0;
    std::uint64_t trigger_sequence=0,generation=0;
    std::size_t payload() const {return std::size_t(width)*height*(pixel_format==pfnc_rgb8?3:1);}
    bool operator==(const CameraSettings& b) const {
        return width==b.width && height==b.height && pixel_format==b.pixel_format && fps_milli==b.fps_milli &&
            acquiring==b.acquiring && trigger_mode==b.trigger_mode && trigger_delay_us==b.trigger_delay_us &&
            trigger_sequence==b.trigger_sequence && generation==b.generation;
    }
};
struct SourceOptions {
    enum class Kind {Pattern,Image,Sequence,Video};
    Kind kind=Kind::Pattern;
    std::string path;
    bool fit=true; // Aspect-preserving black padding; false = explicit stretch.
};
struct Frame {
    CameraSettings settings;
    std::uint64_t timestamp_ns=0;
    std::vector<std::uint8_t> pixels; // Owned, tightly packed Mono or RGB (never BGR).
};
// Transport-independent core. The adapter serializes access; no sockets or ABI here.
// One current frame plus at most 16 pending trigger deadlines, no image queue.
class CameraCore {
public:
    explicit CameraCore(SourceOptions options={});
    ~CameraCore();
    std::pair<std::uint32_t,std::uint32_t> source_dimensions() const;
    void configure(const CameraSettings& settings,std::uint64_t now_ns);
    std::optional<Frame> next_frame(std::uint16_t block,std::uint64_t now_ns);
    std::uint64_t completed_triggers() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
