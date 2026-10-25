#pragma once
#include "core/camera.hpp"
#include <opencv2/core.hpp>
#include <chrono>
#include <functional>
#include <mutex>
#include <stdexcept>

namespace vic06 {
inline std::uint64_t now_ns(){return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
struct Config {
    std::string name="VIC Camera 01",model="VIC-1000",serial="VIC000001";
    vic::SourceOptions source;
    vic::CameraSettings camera;
    unsigned drop=0,seed=1;
};
inline std::string json(const std::function<void(cv::FileStorage&)>& write){cv::FileStorage f("",cv::FileStorage::WRITE|cv::FileStorage::MEMORY|cv::FileStorage::FORMAT_JSON);write(f);return f.releaseAndGetString();}
inline cv::FileStorage parse(const std::string& text){return cv::FileStorage(text.empty()?"{}":text,cv::FileStorage::READ|cv::FileStorage::MEMORY|cv::FileStorage::FORMAT_JSON);}
inline int number(const cv::FileStorage& f,const char* key,int fallback){const auto n=f[key];if(n.empty())return fallback;if(!n.isInt())throw std::invalid_argument(std::string("Integer required: ")+key);return int(n);}
inline std::string text(const cv::FileStorage& f,const char* key,std::string fallback){const auto n=f[key];if(n.empty())return fallback;if(!n.isString())throw std::invalid_argument(std::string("Text required: ")+key);return std::string(n);}
inline void write_config(cv::FileStorage& f,const Config& c){
    const char* kinds[]{"pattern","image","sequence","video"};
    f<<"name"<<c.name<<"model"<<c.model<<"serial"<<c.serial<<"source_kind"<<kinds[static_cast<unsigned>(c.source.kind)]<<"path"<<c.source.path<<"fit"<<int(c.source.fit)
     <<"width"<<int(c.camera.width)<<"height"<<int(c.camera.height)<<"pixel_format"<<int(c.camera.pixel_format)<<"fps_milli"<<int(c.camera.fps_milli)
     <<"trigger_mode"<<int(c.camera.trigger_mode)<<"delay_us"<<int(c.camera.trigger_delay_us)<<"drop_percent"<<int(c.drop)<<"seed"<<int(c.seed);
}
class Engine {
    mutable std::mutex lock_;
    Config config_;
    std::unique_ptr<vic::CameraCore> core_=std::make_unique<vic::CameraCore>();
    std::uint64_t frame_id_=0,generated_=0,dropped_=0,previewed_=0,preview_skipped_=0,started_=0,last_tick_=0,source_frame_floor_=0;
    std::uint32_t random_=1;
    std::string last_error_;
    static void validate(const Config& c){
        if(c.name.empty() || c.name.size()>31 || c.model.empty() || c.model.size()>31 || c.serial.empty() || c.serial.size()>15 || c.source.path.size()>4096)throw std::invalid_argument("Identity/path is empty or exceeds UTF-8 length limit");
        if(c.drop>100 || !c.seed || c.seed>0x7fffffffu)throw std::invalid_argument("Invalid fault percentage/seed");
        vic::CameraCore check;check.configure(c.camera,now_ns());
    }
    std::string status_locked() const {return json([&](cv::FileStorage& f){
        const auto elapsed=started_?(config_.camera.acquiring?now_ns():last_tick_)-started_:0;
        f<<"build"<<"06-0.6.5"<<"sequence_resume"<<1<<"max_width"<<int(vic::max_dimension)<<"max_height"<<int(vic::max_dimension)<<"acquiring"<<int(config_.camera.acquiring)<<"frame_id"<<std::to_string(frame_id_)<<"generated"<<std::to_string(generated_)
         <<"source_frame_floor"<<std::to_string(source_frame_floor_)
         <<"simulated_dropped"<<std::to_string(dropped_)<<"previewed"<<std::to_string(previewed_)<<"preview_skipped"<<std::to_string(preview_skipped_)
         <<"average_fps"<<(elapsed?double(generated_)*1e9/double(elapsed):0.0)<<"consumer_connected"<<0<<"consumer_frames"<<0
         <<"consumer_status"<<"BLOCKED: GenTL Producer not implemented"<<"error"<<last_error_<<"config"<<"{";write_config(f,config_);f<<"}";
    });}
public:
    // Calls are serialized with frame production. There is no transport/CTI
    // implementation here; previewed counts are never Consumer deliveries.
    std::string command(unsigned command,const std::string& payload){
        std::lock_guard<std::mutex> guard(lock_);auto candidate=config_;auto f=parse(payload);const auto now=now_ns();
        if(command==2)return status_locked();
        if(command==8){const auto dimensions=core_->source_dimensions();return json([&](cv::FileStorage& out){out<<"width"<<int(dimensions.first)<<"height"<<int(dimensions.second);});}
        if(command==3){
            if(config_.camera.acquiring)throw std::runtime_error("Stop acquisition before changing identity/source/format");
            candidate.name=text(f,"name",candidate.name);candidate.model=text(f,"model",candidate.model);candidate.serial=text(f,"serial",candidate.serial);
            const auto kind=text(f,"source_kind","pattern");const std::string kinds[]{"pattern","image","sequence","video"};unsigned i=0;while(i<4 && kinds[i]!=kind)++i;
            if(i==4)throw std::invalid_argument("Unknown source kind");candidate.source.kind=static_cast<vic::SourceOptions::Kind>(i);
            candidate.source.path=text(f,"path","");candidate.source.fit=number(f,"fit",1)!=0;
            candidate.camera.width=number(f,"width",int(candidate.camera.width));candidate.camera.height=number(f,"height",int(candidate.camera.height));candidate.camera.pixel_format=number(f,"pixel_format",int(candidate.camera.pixel_format));
            candidate.camera.trigger_mode=number(f,"trigger_mode",0)!=0;
        }
        if(command==3 || command==7){
            candidate.camera.fps_milli=number(f,"fps_milli",int(candidate.camera.fps_milli));candidate.camera.trigger_delay_us=number(f,"delay_us",int(candidate.camera.trigger_delay_us));
            candidate.drop=number(f,"drop_percent",int(candidate.drop));candidate.seed=number(f,"seed",int(candidate.seed));validate(candidate);
            if(command==3){auto next=std::make_unique<vic::CameraCore>(candidate.source);next->configure(candidate.camera,now);core_.swap(next);source_frame_floor_=frame_id_;}
            else core_->configure(candidate.camera,now);
            if(candidate.seed!=config_.seed || command==3)random_=candidate.seed;
            config_=candidate;last_error_.clear();
        }else if(command==4){
            if(!config_.camera.acquiring){candidate.camera.acquiring=true;++candidate.camera.generation;core_->configure(candidate.camera,now);config_=candidate;generated_=dropped_=previewed_=preview_skipped_=0;started_=now;last_tick_=now;last_error_.clear();}
        }else if(command==5){candidate.camera.acquiring=false;core_->configure(candidate.camera,now);config_=candidate;last_tick_=now;}
        else if(command==6){
            if(!candidate.camera.acquiring || !candidate.camera.trigger_mode)throw std::runtime_error("Start software-trigger acquisition first");
            ++candidate.camera.trigger_sequence;core_->configure(candidate.camera,now);config_=candidate;
        }else throw std::invalid_argument("Unsupported Engine command");
        return status_locked();
    }
    bool tick(const std::function<bool(const vic::Frame&,std::uint64_t)>& preview){
        std::lock_guard<std::mutex> guard(lock_);
        try{
            const auto now=now_ns();auto frame=core_->next_frame(static_cast<std::uint16_t>((frame_id_%65535)+1),now);if(!frame)return false;
            ++frame_id_;++generated_;random_^=random_<<13;random_^=random_>>17;random_^=random_<<5;
            if(random_%100<config_.drop){++dropped_;return true;}
            if(preview(*frame,frame_id_))++previewed_;else ++preview_skipped_;return true;
        }catch(const std::exception& e){last_error_=e.what();last_tick_=now_ns();config_.camera.acquiring=false;core_->configure(config_.camera,last_tick_);return false;}
    }
};
}
