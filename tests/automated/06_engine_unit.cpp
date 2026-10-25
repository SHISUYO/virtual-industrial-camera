#include "control06/engine.hpp"
#include <iostream>
#include <thread>
static void check(bool ok,const char* error){if(!ok)throw std::runtime_error(error);}
int main(){try{
    vic06::Engine engine;
    auto state=vic06::parse(engine.command(3,"{\"width\":8,\"height\":6,\"pixel_format\":35127316,\"fps_milli\":60000}"));
    check(int(state["config"]["width"])==8,"Configuration not reflected");
    engine.command(4,"{}");unsigned received=0;
    engine.tick([&](const vic::Frame& frame,std::uint64_t id){check(id==1 && frame.pixels.size()==144,"Frame layout/id");check(frame.pixels[0]==1 && frame.pixels[1]==1 && frame.pixels[2]==1,"RGB byte order");++received;return true;});
    check(received==1,"No actual Core frame");
    bool refused=false;try{engine.command(3,"{\"name\":\"changed\"}");}catch(...){refused=true;}check(refused,"Live identity change accepted");
    engine.command(7,"{\"fps_milli\":30000,\"drop_percent\":100}");
    std::this_thread::sleep_for(std::chrono::milliseconds(40));engine.tick([&](const vic::Frame&,std::uint64_t){throw std::runtime_error("Fault frame reached preview");return false;});
    state=vic06::parse(engine.command(2,"{}"));check(std::string(state["simulated_dropped"])=="1","Drop not counted");
    engine.command(5,"{}");engine.command(3,"{\"width\":8,\"height\":6,\"trigger_mode\":1,\"drop_percent\":0,\"delay_us\":20000}");state=vic06::parse(engine.command(2,"{}"));check(std::string(state["source_frame_floor"])==std::string(state["frame_id"]),"Source generation floor lost");engine.command(4,"{}");
    check(!engine.tick([](const vic::Frame&,std::uint64_t){return true;}),"Untriggered frame produced");engine.command(6,"{}");
    check(!engine.tick([](const vic::Frame&,std::uint64_t){return true;}),"Delayed trigger produced too early");engine.command(5,"{}");std::this_thread::sleep_for(std::chrono::milliseconds(30));
    check(!engine.tick([](const vic::Frame&,std::uint64_t){return true;}),"Stopped trigger delivered");
    refused=false;try{engine.command(3,"{\"width\":0}");}catch(...){refused=true;}check(refused,"Invalid resolution accepted");
    state=vic06::parse(engine.command(2,"{}"));check(int(state["config"]["width"])==8,"Invalid configuration partially committed");
    std::cout<<"PASS: real Core frames, RGB layout, atomic config, live ownership guard, runtime FPS/drop, trigger delay/cancel\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
