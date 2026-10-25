/* G00 separate-process Aravis GV consumer; NOT an independent protocol stack. */
#include <arv.h>
#include <stdio.h>

static void check_error(GError **error) {
    if (*error) g_error("API failure: %s", (*error)->message);
}

static void receive(ArvStream *stream, ArvPixelFormat format, guint64 *previous) {
    ArvBuffer *buffer = arv_stream_timeout_pop_buffer(stream, 3000000);
    size_t size = 0;
    const guint8 *data;
    guint64 id;
    g_assert_nonnull(buffer);
    g_assert_cmpint(arv_buffer_get_status(buffer), ==, ARV_BUFFER_STATUS_SUCCESS);
    g_assert_cmpint(arv_buffer_get_image_width(buffer), ==, 640);
    g_assert_cmpint(arv_buffer_get_image_height(buffer), ==, 480);
    g_assert_cmpuint(arv_buffer_get_image_pixel_format(buffer), ==, format);
    data = arv_buffer_get_image_data(buffer, &size);
    g_assert_nonnull(data);
    g_assert_cmpuint(size, ==, 640 * 480 * (format == ARV_PIXEL_FORMAT_MONO_8 ? 1 : 3));
    id = arv_buffer_get_frame_id(buffer);
    g_assert_cmpuint(id, >, 0);
    g_assert_cmpuint(id, !=, *previous);
    g_assert_cmpuint(arv_buffer_get_timestamp(buffer), >, 0);
    if (format == ARV_PIXEL_FORMAT_MONO_8) {
        /* Documented upstream diagonal test pattern at exposure=10000/gain=0. */
        for (unsigned y = 0; y < 480; ++y)
            for (unsigned x = 0; x < 640; ++x)
                g_assert_cmpuint(data[y * 640 + x], ==, (x + y + id) % 255);
    }
    *previous = id;
    arv_stream_push_buffer(stream, buffer);
}

int main(int argc, char **argv) {
    GError *error = NULL;
    ArvCamera *camera;
    const char *name = NULL;
    arv_disable_interface("Fake");
    arv_update_device_list();
    for (unsigned i = 0; i < arv_get_n_devices(); ++i) {
        if (g_strcmp0(arv_get_device_serial_nbr(i), "VICG00") == 0 &&
            g_strcmp0(arv_get_device_protocol(i), "GigEVision") == 0) {
            name = arv_get_device_id(i);
            printf("DISCOVERED %s address=%s protocol=%s\n", name,
                arv_get_device_address(i), arv_get_device_protocol(i));
            break;
        }
    }
    if (argc != 2 || !name) g_error("Expected discovered VICG00 and explicit camera IPv4 argument");
    for (unsigned cycle = 0; cycle < 2; ++cycle) {
        camera = arv_camera_new(argv[1], &error); check_error(&error);
        g_assert_true(ARV_IS_GV_DEVICE(arv_camera_get_device(camera)));
        printf("OPENED cycle=%u\n", cycle);
        arv_camera_set_region(camera, 0, 0, 640, 480, &error); check_error(&error);
        arv_camera_set_exposure_time(camera, 10000, &error); check_error(&error);
        arv_camera_set_gain(camera, 0, &error); check_error(&error);
        arv_camera_set_frame_rate(camera, 10, &error); check_error(&error);
        arv_camera_gv_set_packet_size(camera, 1400, &error); check_error(&error);
        for (unsigned mode = 0; mode < 3; ++mode) {
            ArvPixelFormat format = mode == 1 ? ARV_PIXEL_FORMAT_RGB_8_PACKED : ARV_PIXEL_FORMAT_MONO_8;
            ArvStream *stream;
            guint64 previous = 0;
            arv_camera_set_pixel_format(camera, format, &error); check_error(&error);
            arv_camera_clear_triggers(camera, &error); check_error(&error);
            if (mode == 2) { arv_camera_set_trigger(camera, "Software", &error); check_error(&error); }
            stream = arv_camera_create_stream(camera, NULL, NULL, &error); check_error(&error);
            g_assert_nonnull(stream);
            /* Explicit bounded receive space for the simulator's unpaced UDP bursts.
             * Property names and enum come from upstream arvgvstream.c/.h. */
            g_object_set(stream, "socket-buffer", ARV_GV_STREAM_SOCKET_BUFFER_FIXED,
                "socket-buffer-size", 8 * 1024 * 1024, NULL);
            guint payload = arv_camera_get_payload(camera, &error); check_error(&error);
            for (unsigned b = 0; b < 8; ++b)
                arv_stream_push_buffer(stream, arv_buffer_new_allocate(payload));
            arv_camera_start_acquisition(camera, &error); check_error(&error);
            printf("STARTED cycle=%u mode=%u\n", cycle, mode);
            if (mode == 2) g_assert_null(arv_stream_timeout_pop_buffer(stream, 500000));
            unsigned frames = mode == 2 ? 3 : 30;
            for (unsigned n = 0; n < frames; ++n) {
                if (mode == 2) { arv_camera_software_trigger(camera, &error); check_error(&error); }
                receive(stream, format, &previous);
            }
            if (mode == 2) g_assert_null(arv_stream_timeout_pop_buffer(stream, 500000));
            arv_camera_stop_acquisition(camera, &error); check_error(&error);
            g_object_unref(stream);
            printf("VALID_FRAMES cycle=%u mode=%u count=%u; stopped\n", cycle, mode, frames);
        }
        g_object_unref(camera);
        printf("CLOSED cycle=%u\n", cycle);
    }
    arv_shutdown();
    puts("PASS: discovery/open/continuous Mono8+RGB8/software trigger/stop/reopen");
    return 0;
}
