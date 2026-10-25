#include "gige/gvcp.hpp"
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>

namespace vic {
std::uint16_t get16(const std::uint8_t* p) { return static_cast<std::uint16_t>((p[0]<<8)|p[1]); }
std::uint32_t get32(const std::uint8_t* p) {
    return (std::uint32_t(p[0])<<24)|(std::uint32_t(p[1])<<16)|(std::uint32_t(p[2])<<8)|p[3];
}
void put16(Bytes& b, std::uint16_t n) { b.push_back(std::uint8_t(n>>8)); b.push_back(std::uint8_t(n)); }
void put32(Bytes& b, std::uint32_t n) { put16(b,std::uint16_t(n>>16)); put16(b,std::uint16_t(n)); }
namespace {
void validate_string(const std::string& s, std::size_t max) {
    if(s.empty() || s.size()>max || std::any_of(s.begin(),s.end(),[](unsigned char c){return c<32 || c>126;}))
        throw std::runtime_error("Identity must be nonempty printable ASCII within the bootstrap field length");
}
std::string escaped(const std::string& s) {
    std::string out;
    for(char c:s) {
        switch(c) {
            case '&':out+="&amp;";break; case '<':out+="&lt;";break;
            case '>':out+="&gt;";break; case '\"':out+="&quot;";break;
            case '\'':out+="&apos;";break; default:out+=c;
        }
    }
    return out;
}
std::string identifier(const std::string& text) {
    auto letter=[](char c){return (c>='a' && c<='z') || (c>='A' && c<='Z');};
    std::string out=(!text.empty() && letter(text[0]))?"":"VIC_";
    for(char c:text) out+=(letter(c) || (c>='0' && c<='9') || c=='_')?c:'_';
    return out;
}
std::string make_xml(const Identity& id,bool enable_core) {
    std::ostringstream s;
    s << "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
      << "<RegisterDescription xmlns=\"http://www.genicam.org/GenApi/Version_1_1\""
      << " ModelName=\"" << escaped(identifier(id.model)) << "\" VendorName=\"" << escaped(identifier(id.vendor))
      << "\" StandardNameSpace=\"None\" SchemaMajorVersion=\"1\" SchemaMinorVersion=\"1\""
      << " SchemaSubMinorVersion=\"0\" MajorVersion=\"0\" MinorVersion=\"4\" SubMinorVersion=\"0\""
      << " ProductGuid=\"35F84E7B-D824-45A9-B1EF-9579D64951A3\" VersionGuid=\"8AE7631F-83B0-4B14-B69A-0010FB4E27AE\">\n"
      << "<Category Name=\"Root\" NameSpace=\"Standard\"><pFeature>DeviceControl</pFeature><pFeature>ImageFormatControl</pFeature><pFeature>AcquisitionControl</pFeature><pFeature>TransportLayerControl</pFeature></Category>\n"
      << "<Category Name=\"DeviceControl\" NameSpace=\"Standard\">";
    const char* names[]={"DeviceVendorName","DeviceModelName","DeviceVersion","DeviceManufacturerInfo","DeviceSerialNumber","DeviceID","DeviceUserID"};
    const unsigned addresses[]={0x48,0x68,0x88,0xa8,0xd8,0xd8,0xe8};
    const unsigned lengths[]={32,32,32,48,16,16,16};
    for(const auto* name:names) s<<"<pFeature>"<<name<<"</pFeature>";
    s<<"</Category>\n";
    for(unsigned i=0;i<7;++i)
        s<<"<StringReg Name=\""<<names[i]<<"\" NameSpace=\"Standard\"><Address>"<<addresses[i]
         <<"</Address><Length>"<<lengths[i]<<"</Length><AccessMode>RO</AccessMode><pPort>Device</pPort></StringReg>\n";
    s<<"<Category Name=\"TransportLayerControl\" NameSpace=\"Standard\"><pFeature>GevHeartbeatTimeout</pFeature><pFeature>PayloadSize</pFeature><pFeature>GevSCDA</pFeature><pFeature>GevSCPHostPort</pFeature><pFeature>GevSCPSPacketSize</pFeature></Category>\n"
     <<"<Integer Name=\"GevHeartbeatTimeout\" NameSpace=\"Standard\"><pValue>HeartbeatRegister</pValue><Min>100</Min><Max>60000</Max><Inc>1</Inc></Integer>\n"
     <<"<IntReg Name=\"HeartbeatRegister\" NameSpace=\"Custom\"><Address>2360</Address><Length>4</Length><AccessMode>RW</AccessMode><pPort>Device</pPort><Cachable>NoCache</Cachable><Sign>Unsigned</Sign><Endianess>BigEndian</Endianess></IntReg>\n"
     ;
    auto reg=[&](const char* name,unsigned address,const char* access) {
        s<<"<IntReg Name=\""<<name<<"\" NameSpace=\"Custom\"><Address>"<<address<<"</Address><Length>4</Length><AccessMode>"<<access
         <<"</AccessMode><pPort>Device</pPort><Cachable>NoCache</Cachable><Sign>Unsigned</Sign><Endianess>BigEndian</Endianess></IntReg>\n";
    };
    if(!enable_core) {
    s<<"<Category Name=\"ImageFormatControl\" NameSpace=\"Standard\"><pFeature>Width</pFeature><pFeature>Height</pFeature><pFeature>PixelFormat</pFeature></Category>\n"
     <<"<Integer Name=\"Width\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>640</Value><Min>640</Min><Max>640</Max></Integer>\n"
     <<"<Integer Name=\"Height\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>480</Value><Min>480</Min><Max>480</Max></Integer>\n"
     <<"<Integer Name=\"OffsetX\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>0</Value></Integer><Integer Name=\"OffsetY\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>0</Value></Integer>\n"
     <<"<Integer Name=\"PayloadSize\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>307200</Value></Integer>\n"
     <<"<Enumeration Name=\"PixelFormat\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><EnumEntry Name=\"Mono8\" NameSpace=\"Standard\"><Value>17301505</Value></EnumEntry><Value>17301505</Value></Enumeration>\n"
     <<"<Category Name=\"AcquisitionControl\" NameSpace=\"Standard\"><pFeature>AcquisitionMode</pFeature><pFeature>AcquisitionStart</pFeature><pFeature>AcquisitionStop</pFeature><pFeature>AcquisitionFrameRate</pFeature></Category>\n"
     <<"<Enumeration Name=\"AcquisitionMode\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><EnumEntry Name=\"Continuous\" NameSpace=\"Standard\"><Value>1</Value></EnumEntry><Value>1</Value></Enumeration>\n"
     <<"<Float Name=\"AcquisitionFrameRate\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>30.0</Value><Min>30.0</Min><Max>30.0</Max></Float>\n"
     <<"<Command Name=\"AcquisitionStart\" NameSpace=\"Standard\"><pValue>AcquisitionCommand</pValue><CommandValue>1</CommandValue></Command>\n"
     <<"<Command Name=\"AcquisitionStop\" NameSpace=\"Standard\"><pValue>AcquisitionCommand</pValue><CommandValue>0</CommandValue></Command>\n";
    } else {
        s<<"<Category Name=\"ImageFormatControl\" NameSpace=\"Standard\"><pFeature>Width</pFeature><pFeature>Height</pFeature><pFeature>PixelFormat</pFeature></Category>\n";
        auto integer=[&](const char* name,const char* target,unsigned min,unsigned max) {
            s<<"<Integer Name=\""<<name<<"\" NameSpace=\"Standard\"><pIsLocked>AcquisitionStatusRegister</pIsLocked><pValue>"<<target<<"</pValue><Min>"<<min<<"</Min><Max>"<<max<<"</Max><Inc>1</Inc></Integer>\n";
        };
        integer("Width","WidthRegister",1,max_dimension);integer("Height","HeightRegister",1,max_dimension);
        s<<"<Integer Name=\"OffsetX\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>0</Value></Integer><Integer Name=\"OffsetY\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><Value>0</Value></Integer>\n"
         <<"<Integer Name=\"PayloadSize\" NameSpace=\"Standard\"><pValue>PayloadRegister</pValue></Integer>\n"
         <<"<Enumeration Name=\"PixelFormat\" NameSpace=\"Standard\"><pIsLocked>AcquisitionStatusRegister</pIsLocked><EnumEntry Name=\"Mono8\" NameSpace=\"Standard\"><Value>17301505</Value></EnumEntry><EnumEntry Name=\"RGB8\" NameSpace=\"Standard\"><Value>35127316</Value></EnumEntry><EnumEntry Name=\"RGB8Packed\" NameSpace=\"Custom\"><Value>35127316</Value></EnumEntry><pValue>PixelFormatRegister</pValue></Enumeration>\n"
         <<"<Category Name=\"AcquisitionControl\" NameSpace=\"Standard\"><pFeature>AcquisitionMode</pFeature><pFeature>AcquisitionStart</pFeature><pFeature>AcquisitionStop</pFeature><pFeature>AcquisitionFrameRate</pFeature><pFeature>TriggerSelector</pFeature><pFeature>TriggerMode</pFeature><pFeature>TriggerSource</pFeature><pFeature>TriggerSoftware</pFeature><pFeature>TriggerDelay</pFeature></Category>\n"
         <<"<Enumeration Name=\"AcquisitionMode\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><EnumEntry Name=\"Continuous\" NameSpace=\"Standard\"><Value>1</Value></EnumEntry><Value>1</Value></Enumeration>\n"
         <<"<Float Name=\"AcquisitionFrameRate\" NameSpace=\"Standard\"><pIsLocked>AcquisitionStatusRegister</pIsLocked><pValue>FrameRateConverter</pValue><Min>1</Min><Max>60</Max><Unit>Hz</Unit></Float>\n"
         <<"<Converter Name=\"FrameRateConverter\"><FormulaTo>FROM*1000</FormulaTo><FormulaFrom>TO/1000.0</FormulaFrom><pValue>FrameRateRegister</pValue></Converter>\n"
         <<"<Enumeration Name=\"TriggerSelector\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><EnumEntry Name=\"FrameStart\" NameSpace=\"Standard\"><Value>0</Value></EnumEntry><Value>0</Value></Enumeration>\n"
         <<"<Enumeration Name=\"TriggerSource\" NameSpace=\"Standard\"><ImposedAccessMode>RO</ImposedAccessMode><EnumEntry Name=\"Software\" NameSpace=\"Standard\"><Value>0</Value></EnumEntry><Value>0</Value></Enumeration>\n"
         <<"<Enumeration Name=\"TriggerMode\" NameSpace=\"Standard\"><pIsLocked>AcquisitionStatusRegister</pIsLocked><EnumEntry Name=\"Off\" NameSpace=\"Standard\"><Value>0</Value></EnumEntry><EnumEntry Name=\"On\" NameSpace=\"Standard\"><Value>1</Value></EnumEntry><pValue>TriggerModeRegister</pValue></Enumeration>\n"
         <<"<Float Name=\"TriggerDelay\" NameSpace=\"Standard\"><pIsLocked>AcquisitionStatusRegister</pIsLocked><pValue>TriggerDelayConverter</pValue><Min>0</Min><Max>5000000</Max><Unit>us</Unit></Float>\n"
         <<"<Converter Name=\"TriggerDelayConverter\"><FormulaTo>FROM</FormulaTo><FormulaFrom>TO</FormulaFrom><pValue>TriggerDelayRegister</pValue></Converter>\n"
         <<"<Command Name=\"AcquisitionStart\" NameSpace=\"Standard\"><pValue>AcquisitionCommand</pValue><CommandValue>1</CommandValue></Command>\n"
         <<"<Command Name=\"AcquisitionStop\" NameSpace=\"Standard\"><pValue>AcquisitionCommand</pValue><CommandValue>0</CommandValue></Command>\n"
         <<"<Command Name=\"TriggerSoftware\" NameSpace=\"Standard\"><pValue>SoftwareTriggerRegister</pValue><CommandValue>1</CommandValue></Command>\n";
        reg("WidthRegister",0x20004,"RW");reg("HeightRegister",0x20008,"RW");reg("PixelFormatRegister",0x2000c,"RW");
        reg("FrameRateRegister",0x20010,"RW");reg("TriggerModeRegister",0x20014,"RW");reg("SoftwareTriggerRegister",0x20018,"WO");
        reg("TriggerDelayRegister",0x2001c,"RW");reg("PayloadRegister",0x20020,"RO");reg("AcquisitionStatusRegister",0x20024,"RO");
    }
    reg("AcquisitionCommand",wire::acquisition,"WO");
    s<<"<Integer Name=\"GevSCDA\" NameSpace=\"Standard\"><pValue>DestinationRegister</pValue></Integer>\n"
     <<"<Integer Name=\"GevSCPHostPort\" NameSpace=\"Standard\"><pValue>DestinationPortRegister</pValue><Min>0</Min><Max>65535</Max></Integer>\n"
     <<"<Integer Name=\"GevSCPSPacketSize\" NameSpace=\"Standard\"><pValue>PacketSizeRegister</pValue><Min>220</Min><Max>1500</Max><Inc>4</Inc></Integer>\n"
     <<"<MaskedIntReg Name=\"PacketSizeRegister\" NameSpace=\"Custom\"><Address>3332</Address><Length>4</Length><AccessMode>RW</AccessMode><pPort>Device</pPort><Cachable>NoCache</Cachable><LSB>31</LSB><MSB>16</MSB><Sign>Unsigned</Sign><Endianess>BigEndian</Endianess></MaskedIntReg>\n";
    reg("DestinationRegister",0xd18,"RW");reg("DestinationPortRegister",0xd00,"RW");
    s<<"<Integer Name=\"TLParamsLocked\"><Value>0</Value><Min>0</Min><Max>1</Max></Integer>\n"
     <<"<Port Name=\"Device\" NameSpace=\"Standard\"/></RegisterDescription>\n";
    return s.str();
}
}
Identity load_identity(const std::string& path) {
    std::ifstream file(path);
    if(!file) throw std::runtime_error("Cannot open identity config: "+path);
    std::map<std::string,std::string> values;
    std::string line;
    while(std::getline(file,line)) {
        if(!line.empty() && line.back()=='\r') line.pop_back();
        if(line.empty() || line[0]=='#') continue;
        auto sep=line.find('=');
        if(sep==std::string::npos || !values.emplace(line.substr(0,sep),line.substr(sep+1)).second)
            throw std::runtime_error("Invalid or duplicate identity key");
    }
    if(values.size()!=4 || !values.count("vendor") || !values.count("model") || !values.count("serial") || !values.count("user_name"))
        throw std::runtime_error("Config requires exactly vendor, model, serial, user_name");
    Identity id{values.at("vendor"),values.at("model"),values.at("serial"),values.at("user_name")};
    validate_string(id.vendor,31); validate_string(id.model,31);
    validate_string(id.serial,15); validate_string(id.user_name,15);
    return id;
}
void Gvcp::set32(std::uint32_t a, std::uint32_t n) {
    bootstrap_.at(a)=std::uint8_t(n>>24);bootstrap_.at(a+1)=std::uint8_t(n>>16);
    bootstrap_.at(a+2)=std::uint8_t(n>>8);bootstrap_.at(a+3)=std::uint8_t(n);
}
void Gvcp::configure_initial_stream(std::uint32_t packet_size,std::uint32_t delay) {
    if(owner_ || acquiring_)throw std::runtime_error("Local defaults require an uncontrolled idle camera");
    if(packet_size<220 || packet_size>1500 || packet_size%4 || delay>5000000)throw std::invalid_argument("Invalid initial stream settings");
    set32(0xd04,packet_size);camera_.trigger_delay_us=delay;
}
void Gvcp::configure_initial_camera(const CameraSettings& settings) {
    if(owner_ || acquiring_ || settings.acquiring || settings.trigger_sequence)throw std::runtime_error("Initial camera defaults require an uncontrolled idle camera");
    CameraCore validation;validation.configure(settings,0);camera_=settings;
}
Gvcp::Gvcp(Identity id, Network net,bool enable_core):xml_(make_xml(id,enable_core)),core_enabled_(enable_core) {
    validate_string(id.vendor,31);validate_string(id.model,31);
    validate_string(id.serial,15);validate_string(id.user_name,15);
    set32(0,0x00010002); // Implemented classic bootstrap version 1.2; normative audit pending.
    set32(4,0x80000000); // Big-endian register data.
    set32(8,(std::uint32_t(net.mac[0])<<8)|net.mac[1]);
    set32(12,(std::uint32_t(net.mac[2])<<24)|(std::uint32_t(net.mac[3])<<16)|(std::uint32_t(net.mac[4])<<8)|net.mac[5]);
    set32(0x10,0);set32(0x14,0); // Host-managed IP, no camera-side IP configuration services.
    set32(0x24,net.ip);set32(0x34,net.mask);set32(0x44,net.gateway);
    auto text=[this](unsigned a,const std::string& value){ std::copy(value.begin(),value.end(),bootstrap_.begin()+a); };
    text(0x48,id.vendor);text(0x68,id.model);text(0x88,enable_core?"G04-0.4.0":"G02-0.2.0");
    text(0xa8,enable_core?"G04 VIC Core Mono8/RGB8 and software trigger":"G02 Mono8 test image; 640x480 at 30 FPS");text(0xd8,id.serial);text(0xe8,id.user_name);
    std::ostringstream url;url<<(enable_core?"Local:VIC_G04.xml;":"Local:VIC_G02.xml;")<<std::hex<<wire::xml_base<<';'<<xml_.size();
    text(0x200,url.str());set32(0x600,1);set32(0x900,0);set32(0x904,1);
    set32(0xd04,1400);set32(0x93c,0);set32(0x940,1000000000); // Timestamp ticks are nanoseconds.
    set32(0x934,0xc0000002); // Serial/user-name and implemented WriteMem support.
    set32(wire::heartbeat,timeout_);set32(wire::privilege,0);
}
void Gvcp::expire(std::uint64_t now) {
    if(owner_ && now-touched_>=timeout_) {
        owner_.reset();privilege_=0;acquiring_=false;set32(wire::privilege,0);++expirations_;completed_triggers_=camera_.trigger_sequence;have_trigger_id_=false;
    }
}
StreamSettings Gvcp::stream_settings() const {
    const auto size=get32(bootstrap_.data()+0xd04);
    auto camera=camera_;camera.acquiring=acquiring_;
    return {acquiring_,get32(bootstrap_.data()+0xd18),get32(bootstrap_.data()+0xd00),size&0xffff,(size&0x40000000)!=0,camera};
}
bool Gvcp::copy_memory(std::uint32_t a,std::uint32_t n,Bytes& out) const {
    if(core_enabled_ && a>=0x20004 && std::uint64_t(a)+n<=0x20028 && n%4==0) {
        for(unsigned off=0;off<n;off+=4) {
            std::uint32_t value=0;
            switch(a+off) {
                case 0x20004:value=camera_.width;break;case 0x20008:value=camera_.height;break;
                case 0x2000c:value=camera_.pixel_format;break;case 0x20010:value=camera_.fps_milli;break;
                case 0x20014:value=camera_.trigger_mode?1:0;break;case 0x20018:break;
                case 0x2001c:value=camera_.trigger_delay_us;break;case 0x20020:value=static_cast<std::uint32_t>(camera_.payload());break;
                case 0x20024:value=acquiring_?1:0;break;default:return false;
            }
            put32(out,value);
        }
        return true;
    }
    if(a==wire::acquisition && n==4) {put32(out,acquiring_?1u:0u);return true;}
    if(a<bootstrap_.size() && std::uint64_t(a)+n<=bootstrap_.size()) {
        out.insert(out.end(),bootstrap_.begin()+a,bootstrap_.begin()+a+n);return true;
    }
    const std::uint64_t end=std::uint64_t(wire::xml_base)+((xml_.size()+3)&~std::size_t(3));
    if(a>=wire::xml_base && std::uint64_t(a)+n<=end) {
        for(std::uint32_t i=0;i<n;++i) {
            auto offset=std::size_t(a-wire::xml_base)+i;
            out.push_back(offset<xml_.size()?std::uint8_t(xml_[offset]):0);
        }
        return true;
    }
    return false;
}
std::optional<Bytes> Gvcp::process(const Bytes& p,Peer peer,std::uint64_t now) {
    expire(now);
    if(p.size()<8 || p[0]!=0x42) return std::nullopt;
    const auto command=get16(p.data()+2), length=get16(p.data()+4), id=get16(p.data()+6);
    auto reply=[&](std::uint16_t status,const Bytes& data=Bytes{}) -> std::optional<Bytes> {
        if(!(p[1]&1) && command!=wire::discovery) return std::nullopt;
        Bytes r;put16(r,status);put16(r,std::uint16_t(command+1));put16(r,std::uint16_t(data.size()));put16(r,id);
        r.insert(r.end(),data.begin(),data.end());return r;
    };
    if(length>(command==0x86?516:512) || p.size()!=std::size_t(length)+8) return reply(wire::invalid_header);
    const auto allowed=command==wire::discovery?0x11:0x01;
    if(p[1]&~allowed) return reply(wire::invalid_parameter);
    const bool mine=owner_ && *owner_==peer;
    auto touch=[&](){ if(owner_ && *owner_==peer) touched_=now; };
    if(command==wire::discovery) {
        if(length) return reply(wire::invalid_parameter);
        return reply(wire::ok,Bytes(bootstrap_.begin(),bootstrap_.begin()+0xf8));
    }
    if(command==0x86) {
        // Standard WriteMem layout: address followed by aligned bytes.
        // Validate on a temporary state so a later invalid word cannot partially write.
        if(length<8 || length%4) return reply(wire::invalid_parameter);
        const auto address=get32(p.data()+8);
        if(address%4) return reply(wire::bad_alignment);
        if(std::uint64_t(address)+length-4>0x100000000ull) return reply(wire::invalid_access);
        Gvcp candidate=*this;
        for(unsigned off=12;off<p.size();off+=4) {
            Bytes write{0x42,1};put16(write,wire::write_reg);put16(write,8);put16(write,id);
            put32(write,address+off-12);put32(write,get32(p.data()+off));
            const auto result=candidate.process(write,peer,now);
            if(!result || get16(result->data())!=0) return reply(result?get16(result->data()):wire::invalid_access);
        }
        *this=std::move(candidate);
        Bytes data;put32(data,address);return reply(wire::ok,data);
    }
    if(command==wire::read_reg || command==wire::read_mem) {
        if(owner_ && privilege_==1 && !mine) return reply(wire::access_denied);
        Bytes data;
        if(command==wire::read_reg) {
            if(!length || length%4) return reply(wire::invalid_parameter);
            for(unsigned off=8;off<p.size();off+=4) {
                auto a=get32(p.data()+off);
                if(a%4) return reply(wire::bad_alignment);
                if(!copy_memory(a,4,data)) return reply(wire::invalid_access);
            }
        } else {
            if(length!=8 || get16(p.data()+12)!=0) return reply(wire::invalid_parameter);
            auto a=get32(p.data()+8);auto n=get16(p.data()+14);
            if(a%4 || n%4) return reply(wire::bad_alignment);
            // Cognex requests 536-byte XML chunks. Beckhoff's official GVCP
            // ReadMemory API documents this aligned limit (see G04 report).
            if(!n || n>536) return reply(wire::invalid_parameter);
            put32(data,a);
            if(!copy_memory(a,n,data)) return reply(wire::invalid_access);
        }
        touch();return reply(wire::ok,data);
    }
    if(command==wire::write_reg) {
        if(!length || length%8) return reply(wire::invalid_parameter);
        for(unsigned off=8;off<p.size();off+=8) {
            auto a=get32(p.data()+off), value=get32(p.data()+off+4);
            if(a%4) return reply(wire::bad_alignment);
            if(a!=wire::privilege && !mine) return reply(wire::access_denied);
            if(a==wire::privilege) {
                if(length!=8 || value>2) return reply(wire::invalid_parameter);
                if(owner_ && !mine) return reply(wire::access_denied);
            } else if(a==wire::heartbeat) {
                if(value<100 || value>60000) return reply(wire::invalid_parameter);
            } else if(a==wire::acquisition) {
                if(length!=8 || value>1) return reply(wire::invalid_parameter);
                if(value && (!stream_settings().destination || !stream_settings().port)) return reply(wire::invalid_parameter);
            } else if(core_enabled_ && a>=0x20004 && a<=0x20024) {
                if(a==0x20020 || a==0x20024) return reply(wire::write_protect);
                if(a==0x20018) {
                    if(length!=8 || value!=1 || !acquiring_ || !camera_.trigger_mode) return reply(wire::invalid_parameter);
                    const bool duplicate=have_trigger_id_ && id==last_trigger_id_ && now-last_trigger_time_<1000;
                    if(!duplicate && camera_.trigger_sequence-completed_triggers_>=16) return reply(wire::invalid_parameter);
                } else {
                    if(acquiring_) return reply(wire::access_denied);
                    if((a==0x20004 && (!value || value>max_dimension)) || (a==0x20008 && (!value || value>max_dimension)) ||
                       (a==0x2000c && value!=pfnc_mono8 && value!=pfnc_rgb8) ||
                       (a==0x20010 && (value<1000 || value>60000)) || (a==0x20014 && value>1) ||
                       (a==0x2001c && value>5000000)) return reply(wire::invalid_parameter);
                }
            } else if(a==0xd00) {
                if(value>65535) return reply(wire::invalid_parameter);
                if(acquiring_ && value) return reply(wire::access_denied);
            } else if(a==0xd18) {
                if(value && ((value>>24)==0 || (value>>24)>=224 || value==0xffffffffu)) return reply(wire::invalid_parameter);
                if(acquiring_) return reply(wire::access_denied);
            } else if(a==0xd04) {
                const auto size=value&0xffff;
                // Classic IDs only. Unsupported test-packet/endianness flags are rejected.
                if((value&~0x4000ffffu) || size<220 || size>1500 || size%4) return reply(wire::invalid_parameter);
                if(acquiring_) return reply(wire::access_denied);
            } else return reply(a<bootstrap_.size()?wire::write_protect:wire::invalid_access);
        }
        // Prevalidate the complete batch; invalid writes cannot partially alter state.
        for(unsigned off=8;off<p.size();off+=8) {
            auto a=get32(p.data()+off), value=get32(p.data()+off+4);
            if(a==wire::privilege) {
                privilege_=value;
                if(value) owner_=peer;else {owner_.reset();acquiring_=false;have_trigger_id_=false;}
            } else if(a==wire::heartbeat) timeout_=value;
            else if(a==wire::acquisition) {
                if(value && !acquiring_) ++camera_.generation;
                acquiring_=value!=0;
            }
            else if(core_enabled_ && a>=0x20004 && a<=0x20024) {
                switch(a) {
                    case 0x20004:camera_.width=value;break;case 0x20008:camera_.height=value;break;
                    case 0x2000c:camera_.pixel_format=value;break;case 0x20010:camera_.fps_milli=value;break;
                    case 0x20014:camera_.trigger_mode=value!=0;break;case 0x2001c:camera_.trigger_delay_us=value;break;
                    case 0x20018:
                        if(!(have_trigger_id_ && id==last_trigger_id_ && now-last_trigger_time_<1000)) ++camera_.trigger_sequence;
                        have_trigger_id_=true;last_trigger_id_=id;last_trigger_time_=now;break;
                }
            }
            else if(a==0xd00 && !value) acquiring_=false;
            if(a<bootstrap_.size()) set32(a,value);
        }
        if(!acquiring_) {completed_triggers_=camera_.trigger_sequence;have_trigger_id_=false;}
        touch();Bytes data;put32(data,length/8);return reply(wire::ok,data);
    }
    return reply(wire::not_implemented);
}
}
