#include "core/camera.hpp"
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>
#include <algorithm>
#include <deque>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <stdexcept>

namespace vic {
namespace {
cv::Mat read_image(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary|std::ios::ate);
    if(!file || file.tellg()<=0 || file.tellg()>256*1024*1024) throw std::runtime_error("Missing/empty/oversized image: "+path.u8string());
    const auto size=static_cast<std::size_t>(file.tellg());
    std::vector<unsigned char> data(size);file.seekg(0);file.read(reinterpret_cast<char*>(data.data()),static_cast<std::streamsize>(size));
    cv::Mat image=cv::imdecode(data,cv::IMREAD_COLOR);
    if(image.empty() || image.total()>64*1024*1024) throw std::runtime_error("Cannot decode image: "+path.u8string());
    return image;
}
bool image_extension(std::filesystem::path path) {
    auto ext=path.extension().string();
    std::transform(ext.begin(),ext.end(),ext.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});
    return ext==".png" || ext==".jpg" || ext==".jpeg" || ext==".bmp";
}
}
struct CameraCore::Impl {
    SourceOptions options;
    CameraSettings state;
    std::vector<std::filesystem::path> paths;
    cv::Mat still;
    std::pair<std::uint32_t,std::uint32_t> dimensions{640,480};
    cv::VideoCapture video;
    std::size_t index=0;
    std::uint64_t deadline=0,seen=0,completed=0;
    std::deque<std::pair<std::uint64_t,std::uint64_t>> triggers;
    explicit Impl(SourceOptions o):options(std::move(o)) {
        const auto path=std::filesystem::u8path(options.path);
        if(options.kind==SourceOptions::Kind::Image) {
            if(!image_extension(path)) throw std::runtime_error("Image requires JPG/PNG/BMP");
            still=read_image(path);
            dimensions={static_cast<std::uint32_t>(still.cols),static_cast<std::uint32_t>(still.rows)};
        } else if(options.kind==SourceOptions::Kind::Sequence) {
            for(const auto& entry:std::filesystem::directory_iterator(path)) {
                if(entry.is_regular_file() && image_extension(entry.path())) {
                    if(paths.size()>=10000) throw std::runtime_error("Sequence exceeds 10000 files");
                    paths.push_back(entry.path());
                }
            }
            std::sort(paths.begin(),paths.end());
            if(paths.empty()) throw std::runtime_error("Sequence has no JPG/PNG/BMP files");
            for(const auto& item:paths) {
                const auto image=read_image(item); // Validate without retaining all images.
                if(item==paths.front())dimensions={static_cast<std::uint32_t>(image.cols),static_cast<std::uint32_t>(image.rows)};
            }
        } else if(options.kind==SourceOptions::Kind::Video) {
            if(!std::filesystem::is_regular_file(path)) throw std::runtime_error("Missing video: "+options.path);
            if(!video.open(options.path,cv::CAP_FFMPEG)) throw std::runtime_error("Cannot open video: "+options.path);
            cv::Mat first;
            if(!video.read(first) || first.empty()) throw std::runtime_error("Cannot decode first video frame");
            if(first.total()>64*1024*1024)throw std::runtime_error("Video frame too large");
            dimensions={static_cast<std::uint32_t>(first.cols),static_cast<std::uint32_t>(first.rows)};
            video.release();
        }
    }
    void reset() {index=0;video.release();}
    cv::Mat source() {
        if(options.kind==SourceOptions::Kind::Image) return still;
        if(options.kind==SourceOptions::Kind::Sequence) {
            auto frame=read_image(paths[index]);index=(index+1)%paths.size();return frame;
        }
        if(!video.isOpened() && !video.open(options.path,cv::CAP_FFMPEG)) throw std::runtime_error("Video reopen failed");
        cv::Mat frame;
        if(!video.read(frame) || frame.empty()) {
            video.release();
            if(!video.open(options.path,cv::CAP_FFMPEG) || !video.read(frame) || frame.empty()) throw std::runtime_error("Video loop/decode failed");
        }
        if(frame.total()>64*1024*1024) throw std::runtime_error("Video frame too large");
        return frame;
    }
};
CameraCore::CameraCore(SourceOptions options):impl_(std::make_unique<Impl>(std::move(options))) {}
CameraCore::~CameraCore()=default;
std::pair<std::uint32_t,std::uint32_t> CameraCore::source_dimensions() const {return impl_->dimensions;}
void CameraCore::configure(const CameraSettings& s,std::uint64_t now) {
    if(!s.width || s.width>max_dimension || !s.height || s.height>max_dimension ||
       (s.pixel_format!=pfnc_mono8 && s.pixel_format!=pfnc_rgb8) || s.fps_milli<1000 || s.fps_milli>60000 || s.trigger_delay_us>5000000)
        throw std::invalid_argument("Invalid camera settings");
    auto& p=*impl_;
    const bool reset=!s.acquiring || !p.state.acquiring || s.generation!=p.state.generation;
    if(reset) {
        p.triggers.clear();p.seen=s.trigger_sequence;p.completed=p.seen;p.deadline=now;
        // Folder position belongs to the loaded source, not an acquisition run.
        // Start/Stop (including a consumer reconnect) must not rewind it.
        // Video keeps its existing restart behaviour.
        if(s.acquiring && p.options.kind!=SourceOptions::Kind::Sequence) p.reset();
    } else if(s.trigger_sequence!=p.seen) {
        const auto count=s.trigger_sequence-p.seen;
        if(!s.trigger_mode || count>16 || p.triggers.size()+count>16) throw std::logic_error("Trigger queue overflow");
        for(std::uint64_t i=1;i<=count;++i) p.triggers.emplace_back(now+std::uint64_t(s.trigger_delay_us)*1000,p.seen+i);
        p.seen=s.trigger_sequence;
    }
    p.state=s;
}
std::uint64_t CameraCore::completed_triggers() const {return impl_->completed;}
std::optional<Frame> CameraCore::next_frame(std::uint16_t block,std::uint64_t now) {
    auto& p=*impl_;const auto& s=p.state;
    if(!s.acquiring) return std::nullopt;
    if(s.trigger_mode) {
        if(p.triggers.empty() || now<p.triggers.front().first) return std::nullopt;
    } else if(now<p.deadline) return std::nullopt;
    Frame frame{s,now,{}};frame.pixels.resize(s.payload());
    if(p.options.kind==SourceOptions::Kind::Pattern) {
        for(std::uint32_t y=0;y<s.height;++y) for(std::uint32_t x=0;x<s.width;++x) {
            auto offset=(std::size_t(y)*s.width+x)*(s.pixel_format==pfnc_rgb8?3:1);
            if(s.pixel_format==pfnc_mono8) frame.pixels[offset]=std::uint8_t(x+y+block);
            else {frame.pixels[offset]=std::uint8_t(x+block);frame.pixels[offset+1]=std::uint8_t(y+block);frame.pixels[offset+2]=std::uint8_t(x+y+block);}
        }
    } else {
        const auto input=p.source();cv::Mat resized,bgr,converted;
        const int w=static_cast<int>(s.width),h=static_cast<int>(s.height);
        if(p.options.fit) {
            const double scale=std::min(double(w)/input.cols,double(h)/input.rows);
            const int rw=std::max(1,static_cast<int>(input.cols*scale)),rh=std::max(1,static_cast<int>(input.rows*scale));
            cv::resize(input,resized,cv::Size(rw,rh),0,0,cv::INTER_NEAREST);
            bgr=cv::Mat::zeros(h,w,CV_8UC3);resized.copyTo(bgr(cv::Rect((w-rw)/2,(h-rh)/2,rw,rh)));
        } else cv::resize(input,bgr,cv::Size(w,h),0,0,cv::INTER_NEAREST);
        cv::cvtColor(bgr,converted,s.pixel_format==pfnc_rgb8?cv::COLOR_BGR2RGB:cv::COLOR_BGR2GRAY);
        if(!converted.isContinuous() || converted.total()*converted.elemSize()!=frame.pixels.size()) throw std::runtime_error("Unexpected converted image layout");
        std::copy(converted.data,converted.data+frame.pixels.size(),frame.pixels.begin());
    }
    if(s.trigger_mode) {p.completed=p.triggers.front().second;p.triggers.pop_front();}
    else p.deadline=std::max(p.deadline+1000000000000ull/s.fps_milli,now+1);
    return frame;
}
}
