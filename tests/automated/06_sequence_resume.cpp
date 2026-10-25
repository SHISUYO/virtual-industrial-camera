#include "core/camera.hpp"
#include "gige/gvcp.hpp"
#include <opencv2/imgcodecs.hpp>
#include <filesystem>
#include <iostream>
#include <stdexcept>
using namespace vic;
static void check(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
static Bytes command(std::uint16_t id,std::initializer_list<std::uint32_t> words){
    Bytes p{0x42,1};put16(p,wire::write_reg);put16(p,static_cast<std::uint16_t>(words.size()*4));put16(p,id);
    for(auto word:words)put32(p,word);return p;
}
int main(int argc,char** argv){try{
    const auto dir=argc==3?std::filesystem::path(argv[2]):std::filesystem::path("sequence-resume-fixtures");
    std::filesystem::create_directories(dir);
    for(int i=1;i<=4;++i)check(cv::imwrite((dir/(std::to_string(i)+".jpg")).string(),cv::Mat(48,64,CV_8UC3,cv::Scalar(i*40,i*40,i*40))),"Fixture write");
    if(argc==3){std::cout<<"PASS: four numbered JPG fixtures\n";return 0;}
    CameraCore core({SourceOptions::Kind::Sequence,dir.string(),true});
    CameraSettings s;s.width=64;s.height=48;s.fps_milli=1000;s.trigger_mode=true;
    std::uint64_t now=0;unsigned block=0;
    auto start=[&]{s.acquiring=true;++s.generation;core.configure(s,++now);check(!core.next_frame(1,now),"Start consumed an untriggered image");};
    auto stop=[&]{s.acquiring=false;core.configure(s,++now);check(!core.next_frame(1,now),"Stopped source advanced");};
    auto frame=[&](unsigned expected){
        ++s.trigger_sequence;core.configure(s,++now);auto f=core.next_frame(static_cast<std::uint16_t>(++block),now);
        check(f.has_value(),"Triggered frame absent");
        for(auto pixel:f->pixels)check(pixel==expected*40,"Sequence cursor reset/skipped/wrong pixels");
        check(!core.next_frame(1,++now),"One trigger consumed multiple images");
    };
    // Exactly the user workflow: repeated start/trigger/stop, wrap, stop at3 ->4.
    for(unsigned i=0;i<7;++i){start();frame(i%4+1);stop();}
    start();frame(4);frame(1);frame(2);frame(3);stop();start();frame(4);
    // An accepted but cancelled delayed trigger must not consume the next image.
    s.trigger_delay_us=100000;++s.trigger_sequence;core.configure(s,++now);
    check(!core.next_frame(1,now),"Delay ignored");stop();start();s.trigger_delay_us=0;frame(1);stop();
    // Parameter/generation changes preserve cursor; output conversion stays correct.
    s.pixel_format=pfnc_rgb8;start();frame(2);stop();
    // A newly loaded source starts at1, independent of the old source cursor.
    CameraCore fresh({SourceOptions::Kind::Sequence,dir.string(),true});s.acquiring=true;fresh.configure(s,++now);++s.trigger_sequence;fresh.configure(s,++now);
    auto first=fresh.next_frame(1,now);check(first && first->pixels.front()==40,"Reload did not start at first image");
    CameraCore single({SourceOptions::Kind::Sequence,dir.string(),true});
    s.trigger_mode=false;s.pixel_format=pfnc_mono8;
    for(unsigned i=0;i<9;++i){
        s.acquiring=true;++s.generation;single.configure(s,++now);
        auto f=single.next_frame(1,now);check(f && f->pixels.front()==(i%4+1)*40,"Free-run Start/Stop rewound sequence");
        check(!single.next_frame(1,++now),"Free-run emitted before deadline");
        s.acquiring=false;single.configure(s,++now);
    }
    // Actual GVCP acquisition generations + control release/reclaim use same Core.
    Gvcp gvcp({}, {},true);CameraCore remote({SourceOptions::Kind::Sequence,dir.string(),true});Peer peer{0x0acb0001,42};std::uint16_t id=0;
    auto write=[&](std::initializer_list<std::uint32_t> words){auto reply=gvcp.process(command(++id,words),peer,++now);if(!reply || get16(reply->data())!=0)throw std::runtime_error("GVCP command id="+std::to_string(id)+" status="+(reply?std::to_string(get16(reply->data())):"silent"));auto state=gvcp.stream_settings();state.camera.acquiring=state.acquiring;remote.configure(state.camera,now*1000000);};
    write({wire::privilege,2});
    write({0x20004,64,0x20008,48,0x20010,1000,0x20014,1,0xd18,0x0acb0001,0xd00,50000});
    for(unsigned i=0;i<9;++i){
        write({wire::acquisition,1});write({0x20018,1});auto f=remote.next_frame(static_cast<std::uint16_t>(i+1),now*1000000);
        check(f && f->pixels.front()==(i%4+1)*40,"GVCP stop/reconnect reset source");gvcp.set_completed_triggers(remote.completed_triggers());
        write({wire::acquisition,0});write({wire::privilege,0});write({wire::privilege,2});
    }
    std::cout<<"PASS: sequence steps/wrap/stop-resume/cancel/format/reload/GVCP control reconnect\n";return 0;
}catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}}
