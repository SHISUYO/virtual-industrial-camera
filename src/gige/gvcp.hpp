#pragma once
#include "core/camera.hpp"
#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace vic {
using Bytes = std::vector<std::uint8_t>;
// Numeric wire definitions cross-checked against upstream Aravis 0.8.36
// arvgvcpprivate.h / arvgvcp.c. See docs/G01_PROTOCOL_SOURCES.md.
// These references are implementation evidence, not a normative certification.
namespace wire {
constexpr std::uint16_t port=3956, discovery=0x0002, read_reg=0x0080,
    write_reg=0x0082, read_mem=0x0084;
constexpr std::uint32_t heartbeat=0x938, privilege=0xa00;
constexpr std::uint32_t xml_base=0x10000; // VIC-owned ROM, not a bootstrap register.
constexpr std::uint32_t acquisition=0x20000; // VIC-defined command register, mapped in XML.
constexpr std::uint16_t ok=0, not_implemented=0x8001, invalid_parameter=0x8002,
    invalid_access=0x8003, write_protect=0x8004, bad_alignment=0x8005,
    access_denied=0x8006, invalid_header=0x800e;
}
std::uint16_t get16(const std::uint8_t* p);
std::uint32_t get32(const std::uint8_t* p);
void put16(Bytes& b, std::uint16_t value);
void put32(Bytes& b, std::uint32_t value);
struct Peer {
    std::uint32_t ip; // host order
    std::uint16_t port;
    bool operator==(const Peer& other) const { return ip==other.ip && port==other.port; }
};
struct Identity {
    std::string vendor="VIC Project", model="VIC-1000-GE",
        serial="VICGE000001", user_name="VIC Camera 01";
};
Identity load_identity(const std::string& path);
struct Network {
    std::uint32_t ip=0, mask=0, gateway=0;
    std::array<std::uint8_t,6> mac{}; // Actual selected NIC MAC, never modified.
};
struct StreamSettings {
    bool acquiring=false;
    std::uint32_t destination=0, port=0, packet_size=1400;
    bool dont_fragment=false;
    CameraSettings camera;
    bool operator==(const StreamSettings& other) const {
        return acquiring==other.acquiring && destination==other.destination && port==other.port && packet_size==other.packet_size && dont_fragment==other.dont_fragment && camera==other.camera;
    }
};
class Gvcp {
public:
    Gvcp(Identity identity, Network network, bool enable_core=false);
    void set_completed_triggers(std::uint64_t completed) {completed_triggers_=completed;}
    std::optional<Bytes> process(const Bytes& packet, Peer peer, std::uint64_t now_ms);
    void expire(std::uint64_t now_ms);
    const std::string& xml() const { return xml_; }
    std::uint64_t expirations() const { return expirations_; }
    StreamSettings stream_settings() const;
    void set_source_port(std::uint16_t port) { set32(0xd1c,port); }
    // Local defaults are applied before a Consumer obtains control, never as a
    // second GVCP owner or a way to override active acquisition.
    void configure_initial_stream(std::uint32_t packet_size,std::uint32_t trigger_delay_us);
    void configure_initial_camera(const CameraSettings& settings);
    std::optional<Peer> controller() const {return owner_;}
private:
    std::array<std::uint8_t,0x1000> bootstrap_{};
    std::string xml_;
    std::optional<Peer> owner_;
    std::uint64_t touched_=0, expirations_=0;
    std::uint32_t timeout_=3000, privilege_=0;
    bool acquiring_=false,core_enabled_=false;
    CameraSettings camera_;
    std::uint64_t completed_triggers_=0,last_trigger_time_=0;
    std::uint16_t last_trigger_id_=0;
    bool have_trigger_id_=false;
    void set32(std::uint32_t address, std::uint32_t value);
    bool copy_memory(std::uint32_t address, std::uint32_t count, Bytes& out) const;
};
}
