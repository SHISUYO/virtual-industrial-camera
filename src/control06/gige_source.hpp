#pragma once
#include "engine.hpp"
#include <filesystem>
#include <fstream>
#include <iterator>
// Only included by the new 06 GigE build. G05/Sandbox executables are retained.
inline void load_source_config(const std::string& path,tap_poc::Config& config){
    std::ifstream file(std::filesystem::u8path(path),std::ios::binary|std::ios::ate);
    if(!file || file.tellg()<=0 || file.tellg()>16384)throw std::runtime_error("Missing/oversized source configuration");
    file.seekg(0);const std::string input((std::istreambuf_iterator<char>(file)),{});
    vic06::Engine validated;validated.command(3,input);auto settings=vic06::parse(validated.command(2,"{}"));auto f=settings["config"];
    const std::string kinds[]{"pattern","image","sequence","video"};const std::string kind=f["source_kind"];unsigned i=0;while(i<4 && kinds[i]!=kind)++i;
    config.source.kind=static_cast<vic::SourceOptions::Kind>(i);config.source.path=std::string(f["path"]);config.source.fit=int(f["fit"])!=0;
    config.identity.user_name=std::string(f["name"]);config.identity.model=std::string(f["model"]);config.identity.serial=std::string(f["serial"]);
    config.initial_camera.width=int(f["width"]);config.initial_camera.height=int(f["height"]);config.initial_camera.pixel_format=int(f["pixel_format"]);
    config.initial_camera.fps_milli=int(f["fps_milli"]);config.initial_camera.trigger_mode=int(f["trigger_mode"])!=0;config.initial_camera.trigger_delay_us=int(f["delay_us"]);
}
