/* Actual external Aravis GVSP receiver. No VIC receiver or packet parser linked. */
#include <arv.h>
#include <stdio.h>
#include <stdlib.h>

static void require(gboolean condition,const char *message) {
    if(!condition) {fprintf(stderr,"FAIL: %s\n",message);exit(1);}
}
static void checked(GError **error) {
    if(*error) {fprintf(stderr,"FAIL: Aravis: %s\n",(*error)->message);exit(1);}
}
int main(int argc,char **argv) {
    GError *error=NULL;
    unsigned total=0;
    setvbuf(stdout,NULL,_IONBF,0);
    require(argc==3,"Usage: g02-aravis-consumer <camera-ip> <sample.pgm>");
    arv_disable_interface("Fake");arv_update_device_list();
    gboolean discovered=FALSE;
    for(unsigned i=0;i<arv_get_n_devices();++i) {
        if(g_strcmp0(arv_get_device_serial_nbr(i),"VICGE000001")==0 &&
           g_strcmp0(arv_get_device_protocol(i),"GigEVision")==0 &&
           g_strcmp0(arv_get_device_address(i),argv[1])==0) {
            printf("DISCOVERED %s %s\n",arv_get_device_id(i),arv_get_device_address(i));discovered=TRUE;
        }
    }
    require(discovered,"VICGE000001 GigE device was not discovered");
    for(unsigned cycle=0;cycle<2;++cycle) {
        ArvCamera *camera=arv_camera_new(argv[1],&error);checked(&error);
        require(camera!=NULL,"camera open returned NULL");
        require(ARV_IS_GV_DEVICE(arv_camera_get_device(camera)),"not a GigE device");
        printf("OPENED cycle=%u\n",cycle);
        gint x,y,width,height;
        arv_camera_get_region(camera,&x,&y,&width,&height,&error);checked(&error);
        require(x==0 && y==0 && width==640 && height==480,"unexpected region");
        require(arv_camera_get_pixel_format(camera,&error)==ARV_PIXEL_FORMAT_MONO_8,"unexpected format");checked(&error);
        const guint payload=arv_camera_get_payload(camera,&error);checked(&error);
        require(payload==640*480,"unexpected payload");
        arv_camera_gv_set_packet_size(camera,cycle?1200:1400,&error);checked(&error);
        ArvStream *stream=arv_camera_create_stream(camera,NULL,NULL,&error);checked(&error);
        require(stream!=NULL,"stream open returned NULL");
        g_object_set(stream,"socket-buffer",ARV_GV_STREAM_SOCKET_BUFFER_FIXED,
                     "socket-buffer-size",8*1024*1024,NULL);
        for(unsigned i=0;i<16;++i) arv_stream_push_buffer(stream,arv_buffer_new_allocate(payload));
        /* A configured channel alone must not produce images. */
        require(arv_stream_timeout_pop_buffer(stream,200000)==NULL,"frame before AcquisitionStart");
        arv_camera_start_acquisition(camera,&error);checked(&error);
        printf("STARTED cycle=%u packet_size=%u\n",cycle,cycle?1200:1400);
        guint64 previous=0,last_timestamp=0;
        unsigned wraps=0,frames=cycle?20:1000;
        for(unsigned n=0;n<frames;++n) {
            ArvBuffer *buffer=arv_stream_timeout_pop_buffer(stream,3000000);
            require(buffer!=NULL,"timed out waiting for a frame");
            if(arv_buffer_get_status(buffer)!=ARV_BUFFER_STATUS_SUCCESS) {
                fprintf(stderr,"FRAME_ERROR status=%d frame_id=%"G_GUINT64_FORMAT" cycle=%u received=%u\n",
                    arv_buffer_get_status(buffer),arv_buffer_get_frame_id(buffer),cycle,n);
                require(FALSE,"incomplete/invalid frame");
            }
            require(arv_buffer_get_image_width(buffer)==640 && arv_buffer_get_image_height(buffer)==480,"bad frame dimensions");
            require(arv_buffer_get_image_pixel_format(buffer)==ARV_PIXEL_FORMAT_MONO_8,"bad frame PFNC");
            size_t bytes=0;const unsigned char *data=arv_buffer_get_image_data(buffer,&bytes);
            require(data!=NULL && bytes==640*480,"bad image length");
            const guint64 id=arv_buffer_get_frame_id(buffer),timestamp=arv_buffer_get_timestamp(buffer);
            require(id>0 && id<=65535 && timestamp>last_timestamp,"bad ID or timestamp");
            if(previous) {
                require(id==(previous==65535?1:previous+1),"frame ID gap");
                if(previous==65535) ++wraps;
            }
            for(unsigned row=0;row<480;++row)
                for(unsigned col=0;col<640;++col)
                    require(data[row*640+col]==((row+col+id)&255),"wrong image pixel");
            if(total==0) {
                FILE *file=fopen(argv[2],"wb");require(file!=NULL,"cannot write sample");
                fprintf(file,"P5\n640 480\n255\n");
                require(fwrite(data,1,bytes,file)==bytes,"sample write failed");fclose(file);
            }
            previous=id;last_timestamp=timestamp;++total;
            arv_stream_push_buffer(stream,buffer);
            if((n+1)%100==0) printf("VALID_FRAMES cycle=%u count=%u all_pixels_checked=1\n",cycle,n+1);
        }
        if(!cycle) require(wraps==1,"classic BlockID wrap was not exercised");
        arv_camera_stop_acquisition(camera,&error);checked(&error);
        g_usleep(150000); // Drain already received pre-stop buffers before testing silence.
        ArvBuffer *queued;
        while((queued=arv_stream_try_pop_buffer(stream))!=NULL) arv_stream_push_buffer(stream,queued);
        require(arv_stream_timeout_pop_buffer(stream,300000)==NULL,"new frame after stop/drain");
        guint64 completed,failed,underruns;
        arv_stream_get_statistics(stream,&completed,&failed,&underruns);
        printf("STOPPED cycle=%u verified_frames=%u completed=%"G_GUINT64_FORMAT" failed=%"G_GUINT64_FORMAT" underruns=%"G_GUINT64_FORMAT"\n",
            cycle,frames,completed,failed,underruns);
        require(failed==0 && underruns==0,"receiver failures/underruns");
        g_object_unref(stream);g_object_unref(camera);
        printf("CLOSED cycle=%u\n",cycle);
    }
    arv_shutdown();
    printf("PASS: external Aravis received %u valid Mono8 frames; all pixels checked; stop/reopen passed\n",total);
    return 0;
}
