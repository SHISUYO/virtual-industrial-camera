/* Actual Aravis GVSP receiver; expected pixels are computed independently. */
#include <arv.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static GError *error=NULL;
static void require(gboolean value,const char* text) {if(!value){fprintf(stderr,"FAIL: %s\n",text);exit(1);}}
static void checked(void) {if(error){fprintf(stderr,"FAIL: Aravis: %s\n",error->message);exit(1);}}
static void integer(ArvCamera* camera,const char* name,gint64 value) {arv_camera_set_integer(camera,name,value,&error);checked();}
static void string(ArvCamera* camera,const char* name,const char* value) {arv_camera_set_string(camera,name,value,&error);checked();}
static void floating(ArvCamera* camera,const char* name,double value) {arv_camera_set_float(camera,name,value,&error);checked();}
static void silence(ArvStream* stream,guint64 usec) {require(arv_stream_timeout_pop_buffer(stream,usec)==NULL,"unexpected frame during silence");}
static void verify(ArvBuffer* buffer,const char* source,unsigned index,unsigned width,unsigned height,gboolean rgb) {
    require(buffer && arv_buffer_get_status(buffer)==ARV_BUFFER_STATUS_SUCCESS,"missing/incomplete frame");
    require(arv_buffer_get_image_width(buffer)==(int)width && arv_buffer_get_image_height(buffer)==(int)height,"frame dimensions");
    require(arv_buffer_get_image_pixel_format(buffer)==(rgb?ARV_PIXEL_FORMAT_RGB_8_PACKED:ARV_PIXEL_FORMAT_MONO_8),"frame PFNC");
    size_t size=0;const unsigned char* pixels=arv_buffer_get_image_data(buffer,&size);
    require(pixels && size==width*height*(rgb?3:1),"frame payload size");
    unsigned id=(unsigned)arv_buffer_get_frame_id(buffer);
    for(unsigned y=0;y<height;++y) for(unsigned x=0;x<width;++x) {
        unsigned r=255,g=0,b=0;
        if(strcmp(source,"pattern")==0) {r=(x+id)&255;g=(y+id)&255;b=(x+y+id)&255;}
        else if(strcmp(source,"sequence")==0) {
            r=(index%2==0 && y>=8 && y<40)?255:0;g=(index%2==1 && x>=20 && x<44)?255:0;
        } else if(strcmp(source,"video")==0) {r=index%2?0:255;g=index%2?255:0;}
        else if(strcmp(source,"jpg")==0) r=254;
        size_t offset=(y*width+x)*(rgb?3:1);
        if(rgb) require(pixels[offset]==r && pixels[offset+1]==g && pixels[offset+2]==b,"RGB source pixels/order/padding");
        else {
            unsigned mono=strcmp(source,"pattern")==0?((x+y+id)&255):(r?76:(g?150:0));
            require(pixels[offset]==mono,"Mono source pixels/padding");
        }
    }
}
static void stop(ArvCamera* camera,ArvStream* stream) {
    arv_camera_stop_acquisition(camera,&error);checked();g_usleep(100000);
    ArvBuffer* b;while((b=arv_stream_try_pop_buffer(stream))) arv_stream_push_buffer(stream,b);
    silence(stream,200000);
    guint64 completed,failed,underruns;arv_stream_get_statistics(stream,&completed,&failed,&underruns);
    require(failed==0 && underruns==0,"receiver failures/underruns");
    printf("STOPPED completed=%"G_GUINT64_FORMAT" failed=%"G_GUINT64_FORMAT" underruns=%"G_GUINT64_FORMAT"\n",completed,failed,underruns);
}
int main(int argc,char** argv) {
    setvbuf(stdout,NULL,_IONBF,0);require(argc==4,"Usage: g03-aravis-consumer <ip> <source-kind> <sample.pnm>");
    const char* source=argv[2];gboolean sequence=strcmp(source,"sequence")==0;
    arv_disable_interface("Fake");arv_update_device_list();gboolean discovered=FALSE;
    for(unsigned i=0;i<arv_get_n_devices();++i) if(g_strcmp0(arv_get_device_serial_nbr(i),"VICGE000001")==0 && g_strcmp0(arv_get_device_address(i),argv[1])==0 && g_strcmp0(arv_get_device_protocol(i),"GigEVision")==0) discovered=TRUE;
    require(discovered,"discovery");printf("DISCOVERED source=%s\n",source);
    unsigned total=0;
    /* Reopen between Mono, RGB, and software-trigger runs; also restart in trigger mode. */
    for(unsigned cycle=0;cycle<3;++cycle) {
        ArvCamera* camera=arv_camera_new(argv[1],&error);checked();require(camera!=NULL,"open");
        printf("OPENED cycle=%u\n",cycle);
        gboolean rgb=cycle!=0;unsigned width=sequence?64:(cycle==1?80:64),height=sequence?48:(cycle==1?60:48);
        const double fps=cycle==0?10:20;
        integer(camera,"Width",width);integer(camera,"Height",height);
        arv_camera_set_pixel_format_from_string(camera,rgb?"RGB8":"Mono8",&error);checked();
        floating(camera,"AcquisitionFrameRate",fps);string(camera,"TriggerMode",cycle==2?"On":"Off");floating(camera,"TriggerDelay",cycle==2?100000:0);
        guint payload=arv_camera_get_payload(camera,&error);checked();require(payload==width*height*(rgb?3:1),"PayloadSize parameter");
        require(arv_camera_get_frame_rate(camera,&error)==fps,"FPS readback");checked();
        arv_camera_gv_set_packet_size(camera,cycle==1?1200:1400,&error);checked();
        ArvStream* stream=arv_camera_create_stream(camera,NULL,NULL,&error);checked();require(stream!=NULL,"stream");
        g_object_set(stream,"socket-buffer",ARV_GV_STREAM_SOCKET_BUFFER_FIXED,"socket-buffer-size",8*1024*1024,NULL);
        for(unsigned i=0;i<16;++i) arv_stream_push_buffer(stream,arv_buffer_new_allocate(payload));
        silence(stream,100000);arv_camera_start_acquisition(camera,&error);checked();
        printf("STARTED cycle=%u %ux%u %s payload=%u fps=%.0f trigger=%s\n",cycle,width,height,rgb?"RGB8":"Mono8",payload,fps,cycle==2?"On":"Off");
        const unsigned count=cycle==2?8:20;guint64 previous_stamp=0,first_stamp=0;unsigned previous_id=0;
        if(cycle==2) silence(stream,200000);
        for(unsigned n=0;n<count;++n) {
            if(cycle==2) {
                arv_camera_software_trigger(camera,&error);checked();silence(stream,50000); // 100ms configured delay.
            }
            ArvBuffer* buffer=arv_stream_timeout_pop_buffer(stream,3000000);
            verify(buffer,source,n,width,height,rgb);
            guint64 stamp=arv_buffer_get_timestamp(buffer);unsigned id=(unsigned)arv_buffer_get_frame_id(buffer);
            require(stamp>previous_stamp && id>0 && id<=65535,"timestamp/BlockID");
            if(previous_id) require(id==(previous_id==65535?1:previous_id+1),"frame ID gap");
            if(!n) first_stamp=stamp;
            previous_stamp=stamp;previous_id=id;++total;
            if(cycle==1 && n==0) {
                size_t bytes;const void* pixels=arv_buffer_get_image_data(buffer,&bytes);FILE* out=fopen(argv[3],"wb");require(out!=NULL,"save received image");
                fprintf(out,"P6\n%u %u\n255\n",width,height);require(fwrite(pixels,1,bytes,out)==bytes,"image write");fclose(out);
            }
            arv_stream_push_buffer(stream,buffer);
            if(cycle==2) silence(stream,50000); // One accepted command produces exactly one image.
        }
        if(cycle<2) {
            double observed=19.0e9/(previous_stamp-first_stamp);require(observed>fps*.85 && observed<fps*1.15,"actual FPS differs from configured FPS");
            printf("VALID_FRAMES count=%u all_pixels_checked=1 observed_fps=%.3f\n",count,observed);
        } else printf("VALID_FRAMES count=%u all_pixels_checked=1 software_trigger_and_delay=PASS\n",count);
        stop(camera,stream);
        if(cycle==2) {
            /* Cancel a trigger with a 300ms delay, restart, and require no stale frame. */
            floating(camera,"TriggerDelay",300000);arv_camera_start_acquisition(camera,&error);checked();
            arv_camera_software_trigger(camera,&error);checked();arv_camera_stop_acquisition(camera,&error);checked();
            arv_camera_start_acquisition(camera,&error);checked();silence(stream,450000);
            arv_camera_software_trigger(camera,&error);checked();
            ArvBuffer* restarted=arv_stream_timeout_pop_buffer(stream,2000000);verify(restarted,source,0,width,height,rgb);++total;arv_stream_push_buffer(stream,restarted);
            stop(camera,stream);printf("RESTARTED trigger_cancel=PASS new_trigger=PASS\n");
        }
        g_object_unref(stream);g_object_unref(camera);printf("CLOSED cycle=%u\n",cycle);
    }
    arv_shutdown();printf("PASS: G03 external Aravis source=%s verified_frames=%u pixels/FPS/trigger/stop/reopen\n",source,total);return 0;
}
