#include "control/session.hpp"
#include "gige/gvcp.hpp"
#include "gige/gvsp.hpp"
#include <iostream>
#include <stdexcept>
static void check(bool ok,const char* text){if(!ok)throw std::runtime_error(text);}
int main(){try{
    vic::Gvcp camera({}, {},true);camera.configure_initial_stream(1200,123000);
    check(camera.stream_settings().packet_size==1200 && camera.stream_settings().camera.trigger_delay_us==123000,"Initial settings not reflected");
    bool rejected=false;try{camera.configure_initial_stream(221,0);}catch(...){rejected=true;}check(rejected,"Invalid packet size accepted");
    vic::CameraSettings initial;initial.width=642;initial.height=480;initial.pixel_format=vic::pfnc_rgb8;initial.fps_milli=20000;
    camera.configure_initial_camera(initial);check(camera.stream_settings().camera.width==642 && camera.stream_settings().camera.pixel_format==vic::pfnc_rgb8,"Source startup geometry/PFNC lost");
    initial.acquiring=true;rejected=false;try{camera.configure_initial_camera(initial);}catch(...){rejected=true;}check(rejected,"Acquiring startup settings accepted");
    initial.acquiring=false;initial.width=6000;initial.height=6000;camera.configure_initial_camera(initial);
    check(camera.stream_settings().camera.payload()==108000000,"6000x6000 RGB payload overflow");
    initial.width=6001;rejected=false;try{camera.configure_initial_camera(initial);}catch(...){rejected=true;}check(rejected,"Oversized width accepted");
    unsigned char frame[70]{};frame[12]=8;frame[23]=17;frame[34]=0xc0;frame[46]=3;
    vic_control::PacketFault all(100,7),none(0,7),a(35,91),b(35,91);
    for(unsigned i=0;i<500;++i){check(all.discard(frame,sizeof(frame)),"100% lost a payload selection");check(!none.discard(frame,sizeof(frame)),"Healthy payload dropped");check(a.discard(frame,sizeof(frame))==b.discard(frame,sizeof(frame)),"Seed not reproducible");}
    frame[46]=1;check(!all.discard(frame,sizeof(frame)),"Leader dropped");frame[46]=2;check(!all.discard(frame,sizeof(frame)),"Trailer dropped");frame[46]=3;frame[34]=0x0f;check(!all.discard(frame,sizeof(frame)),"Control packet dropped");
    check(all.dropped==500 && none.dropped==0,"Drop counters incorrect");
    std::cout<<"PASS: startup parameters, invalid packet size, deterministic 0/100/random payload loss, control/leader/trailer preservation\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
