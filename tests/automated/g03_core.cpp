#include "core/camera.hpp"
#include "gige/gvcp.hpp"
#include <opencv2/imgcodecs.hpp>
#include <opencv2/videoio.hpp>
#include <filesystem>
#include <iostream>
#include <stdexcept>

using namespace vic;
static void check(bool value,const char* message) {if(!value) throw std::runtime_error(message);}
static void fixtures(const std::filesystem::path& dir) {
    std::filesystem::create_directories(dir/"sequence");
    const cv::Mat red(48,64,CV_8UC3,cv::Scalar(0,0,255)),green(48,64,CV_8UC3,cv::Scalar(0,255,0));
    for(const auto* ext:{"png","jpg","bmp"}) check(cv::imwrite((dir/(std::string("red.")+ext)).string(),red),"Fixture write");
    check(cv::imwrite((dir/"sequence/000.png").string(),cv::Mat(32,64,CV_8UC3,cv::Scalar(0,0,255))),"Sequence red");
    check(cv::imwrite((dir/"sequence/001.bmp").string(),cv::Mat(64,32,CV_8UC3,cv::Scalar(0,255,0))),"Sequence green");
    cv::VideoWriter video((dir/"colors.avi").string(),cv::CAP_FFMPEG,cv::VideoWriter::fourcc('F','F','V','1'),10,cv::Size(64,48));
    check(video.isOpened(),"FFV1 video writer unavailable");video.write(red);video.write(green);video.release();
}
static Bytes command(std::uint16_t id,std::initializer_list<std::uint32_t> words) {
    Bytes p{0x42,1};put16(p,wire::write_reg);put16(p,static_cast<std::uint16_t>(words.size()*4));put16(p,id);
    for(auto w:words) put32(p,w);return p;
}
int main(int argc,char** argv) {
    try {
        const auto dir=argc==3 && std::string(argv[1])=="--fixtures"?std::filesystem::path(argv[2]):std::filesystem::path("core-fixtures");
        fixtures(dir);
        if(argc==3) {std::cout<<"PASS: fixtures (PNG/JPG/BMP/sequence/FFV1 video)\n";return 0;}
        CameraCore core;CameraSettings s;s.width=64;s.height=48;s.acquiring=true;
        core.configure(s,0);auto first=core.next_frame(1,0);check(first && first->pixels.size()==3072,"Pattern payload");
        check(!core.next_frame(2,33333332),"FPS emitted early");check(core.next_frame(2,33333333).has_value(),"FPS missed due frame");
        s.acquiring=false;core.configure(s,40000000);check(!core.next_frame(3,99999999),"Stop did not stop");
        s.pixel_format=pfnc_rgb8;s.trigger_mode=true;s.trigger_delay_us=100000;s.acquiring=true;++s.generation;
        core.configure(s,100000000);check(!core.next_frame(3,200000000),"Untriggered frame");
        ++s.trigger_sequence;core.configure(s,200000000);check(!core.next_frame(3,299999999),"Trigger delay ignored");
        auto triggered=core.next_frame(3,300000000);check(triggered && triggered->pixels.size()==9216,"Triggered RGB payload");
        check(triggered->pixels[0]==3 && triggered->pixels[1]==3 && triggered->pixels[2]==3 && triggered->pixels[3]==4 && triggered->pixels[4]==3,"RGB byte order");
        check(!core.next_frame(4,400000000),"One trigger emitted multiple frames");
        ++s.trigger_sequence;core.configure(s,400000000);s.acquiring=false;core.configure(s,400000001);
        s.acquiring=true;++s.generation;core.configure(s,500000000);check(!core.next_frame(4,900000000),"Cancelled trigger survived restart");
        s.trigger_sequence+=16;core.configure(s,900000000);
        bool rejected=false;try {++s.trigger_sequence;core.configure(s,900000000);}catch(const std::logic_error&){rejected=true;}
        check(rejected,"Trigger queue unbounded");
        // Retained frames own their data after later frames are produced.
        check(first->pixels[0]==1 && first->pixels[1]==2,"Frame ownership overwritten");
        for(const auto* name:{"red.png","red.jpg","red.bmp"}) {
            CameraCore image({SourceOptions::Kind::Image,(dir/name).string(),true});
            CameraSettings c;c.width=80;c.height=60;c.pixel_format=pfnc_rgb8;c.acquiring=true;image.configure(c,0);
            auto f=image.next_frame(1,0);check(f && f->pixels.size()==14400 && f->pixels[0]>=254 && f->pixels[1]==0 && f->pixels[2]==0,"Image decoder/RGB conversion");
            c.acquiring=false;image.configure(c,1);c.pixel_format=pfnc_mono8;c.acquiring=true;++c.generation;image.configure(c,2);
            auto mono=image.next_frame(2,2);check(mono && mono->pixels[0]==76,"Mono luminance");
        }
        CameraSettings c;c.width=64;c.height=48;c.pixel_format=pfnc_rgb8;c.acquiring=true;
        CameraCore sequence({SourceOptions::Kind::Sequence,(dir/"sequence").string(),true});sequence.configure(c,0);
        for(unsigned i=0;i<4;++i) {
            auto f=sequence.next_frame(static_cast<std::uint16_t>(i+1),i*100000000ull);check(f.has_value(),"Sequence frame missing");
            for(unsigned y=0;y<48;++y) for(unsigned x=0;x<64;++x) {
                const auto offset=(y*64+x)*3;
                const unsigned red=(i%2==0 && y>=8 && y<40)?255:0,green=(i%2==1 && x>=20 && x<44)?255:0;
                check(f->pixels[offset]==red && f->pixels[offset+1]==green && f->pixels[offset+2]==0,"Sequence loop/aspect padding");
            }
        }
        CameraCore video({SourceOptions::Kind::Video,(dir/"colors.avi").string(),true});video.configure(c,0);
        for(unsigned i=0;i<6;++i) {auto f=video.next_frame(static_cast<std::uint16_t>(i+1),i*100000000ull);check(f && f->pixels[0]==(i%2?0:255) && f->pixels[1]==(i%2?255:0),"Video decode/loop");}
        rejected=false;try {CameraCore missing({SourceOptions::Kind::Image,"missing.png",true});}catch(const std::exception&){rejected=true;}check(rejected,"Missing image accepted");
        Gvcp gvcp({}, {},true);Peer peer{1,42};unsigned id=1;
        auto write=[&](std::initializer_list<std::uint32_t> words,std::uint16_t expected){auto r=gvcp.process(command(static_cast<std::uint16_t>(id++),words),peer,1);if(!r || get16(r->data())!=expected) throw std::runtime_error("Core GVCP write status id="+std::to_string(id-1)+" got="+(r?std::to_string(get16(r->data())):"none")+" expected="+std::to_string(expected));};
        write({0xa00,2},0);write({0x20004,80,0x20008,0},wire::invalid_parameter);check(gvcp.stream_settings().camera.width==640,"Partial parameter batch");
        write({0x20004,80,0x20008,60,0x2000c,pfnc_rgb8,0x20010,10000,0x20014,1},0);
        check(gvcp.stream_settings().camera.payload()==14400,"Dynamic payload");write({0xd18,0xac11f001,0xd00,50000},0);write({wire::acquisition,1},0);
        write({0x20004,640},wire::access_denied);write({0x20020,1},wire::write_protect);
        auto trigger=command(static_cast<std::uint16_t>(id++),{0x20018,1});
        auto r=gvcp.process(trigger,peer,1);check(r && get16(r->data())==0,"Trigger rejected");
        r=gvcp.process(trigger,peer,1);check(r && get16(r->data())==0 && gvcp.stream_settings().camera.trigger_sequence==1,"Retransmit duplicated trigger");
        for(unsigned i=1;i<16;++i) write({0x20018,1},0);write({0x20018,1},wire::invalid_parameter);
        write({wire::acquisition,0},0);write({wire::acquisition,1},0);write({0x20018,1},0);
        gvcp.expire(3001);check(!gvcp.stream_settings().acquiring,"Heartbeat did not stop Core");
        std::cout<<"PASS: Core sources/conversion/ownership, FPS, trigger delay/bounds/cancel, GVCP atomic parameters/permissions/retry\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
