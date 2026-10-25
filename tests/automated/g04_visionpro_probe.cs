using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using Cognex.VisionPro;

// Native installed Cognex GigE consumer. Controls only VICGE000001.
class G04VisionProProbe {
    static void Verify(ICogImage image,bool rgb,string folder,int index) {
        ICogImage8PixelMemory r=null,g=null,b=null;
        try {
            if(rgb) ((CogImage24PlanarColor)image).Get24PlanarColorPixelMemory(CogImageDataModeConstants.Read,0,0,image.Width,image.Height,out r,out g,out b);
            else r=((CogImage8Grey)image).Get8GreyPixelMemory(CogImageDataModeConstants.Read,0,0,image.Width,image.Height);
            byte[] red=new byte[image.Width],green=new byte[image.Width],blue=new byte[image.Width];
            using(var saved=new MemoryStream()) {
                byte[] header=System.Text.Encoding.ASCII.GetBytes((rgb?"P6":"P5")+"\n"+image.Width+" "+image.Height+"\n255\n");saved.Write(header,0,header.Length);
                int seed=Marshal.ReadByte(r.Scan0);
                for(int y=0;y<image.Height;y++) {
                    Marshal.Copy(IntPtr.Add(r.Scan0,y*r.Stride),red,0,red.Length);
                    if(rgb) {Marshal.Copy(IntPtr.Add(g.Scan0,y*g.Stride),green,0,green.Length);Marshal.Copy(IntPtr.Add(b.Scan0,y*b.Stride),blue,0,blue.Length);}
                    for(int x=0;x<image.Width;x++) {
                        if(red[x]!=((x+(rgb?0:y)+seed)&255) || (rgb && (green[x]!=((y+seed)&255) || blue[x]!=((x+y+seed)&255)))) throw new Exception("Pixel mismatch at "+x+","+y);
                        saved.WriteByte(red[x]);if(rgb) {saved.WriteByte(green[x]);saved.WriteByte(blue[x]);}
                    }
                }
                if(index==0 && folder!=null) File.WriteAllBytes(Path.Combine(folder,rgb?"sample.ppm":"sample.pgm"),saved.ToArray());
                Console.WriteLine("VALID_FRAME="+index+" seed="+seed+" all_pixels_checked=1");
            }
        } finally {if(r!=null)r.Dispose();if(g!=null)g.Dispose();if(b!=null)b.Dispose();}
    }
    [STAThread]
    static int Main(string[] args) {
        Console.OutputEncoding=System.Text.Encoding.UTF8;
        ICogFrameGrabber target=null;
        try {
            string mode=args.Length>0?args[0]:"discover";
            Console.WriteLine("SDK="+typeof(CogFrameGrabbers).Assembly.FullName);
            var devices=new CogFrameGrabbers();
            Console.WriteLine("FRAMEGRABBERS="+devices.Count);
            foreach(ICogFrameGrabber device in devices) {
                Console.WriteLine("DEVICE name="+device.Name+" serial="+device.SerialNumber);
                if(device.SerialNumber=="VICGE000001") target=device;
            }
            if(target==null) {Console.WriteLine("FAIL: discovered VICGE000001");return 2;}
            Console.WriteLine("PASS: discovered VICGE000001");
            foreach(string format in target.AvailableVideoFormats) Console.WriteLine("VIDEO_FORMAT="+format);
            if(mode=="discover") return 0;
            var access=target.OwnedGigEAccess;
            Console.WriteLine("GIGE_IP="+access.CurrentIPAddress+" HOST_IP="+access.HostIPAddress);
            if(args.Length>2 && access.CurrentIPAddress.ToString()!=args[2]) throw new Exception("Discovered camera IP differs from the isolated guest");
            foreach(string name in new[]{"DeviceVendorName","DeviceModelName","DeviceSerialNumber","Width","Height","PixelFormat","PayloadSize","TriggerMode"})
                Console.WriteLine("FEATURE "+name+"="+access.GetFeature(name));
            if(args.Length>1) File.WriteAllText(Path.Combine(args[1],"cognex-device.xml"),access.GetXMLFromCamera());
            Console.WriteLine("PASS: GenICam XML/features");
            foreach(string value in access.GetValidEnumValues("PixelFormat")) Console.WriteLine("PIXEL_FORMAT="+value);
            if(mode=="features") return 0;
            if(mode=="rgb") {access.SetFeature("PixelFormat","RGB8"); foreach(string format in target.AvailableVideoFormats) Console.WriteLine("RGB_VIDEO_FORMAT="+format);}
            bool rgb=mode=="rgb";
            string selected=null;
            foreach(string format in target.AvailableVideoFormats)
                if(format==(rgb?"Generic GigEVision (RGB8)":"Generic GigEVision (Mono)")) selected=format;
            if(selected==null) throw new Exception("Requested native video format is unavailable");
            var fifo=target.CreateAcqFifo(selected,rgb?CogAcqFifoPixelFormatConstants.Format3Plane:CogAcqFifoPixelFormatConstants.Format8Grey,0,false);
            fifo.Timeout=3000;
            if(mode=="continuous") fifo.OwnedTriggerParams.TriggerModel=CogAcqTriggerModelConstants.FreeRun;
            if(mode=="software") fifo.OwnedTriggerParams.TriggerModel=CogAcqTriggerModelConstants.Semi;
            Console.WriteLine("TRIGGER_MODEL="+fifo.OwnedTriggerParams.TriggerModel+" ENABLED="+fifo.OwnedTriggerParams.TriggerEnabled);
            Console.WriteLine("PASS: FIFO_CREATED format="+selected);
            for(int i=0;i<3;i++) {
                int trigger;Console.WriteLine("ACQUISITION_REQUEST="+i);
                ICogImage image;
                if(mode=="continuous") {int ticket;image=fifo.CompleteAcquire(-1,out ticket,out trigger);}
                else if(mode=="software") {
                    fifo.Prepare();
                    int requested=fifo.StartAcquire();
                    var deadline=DateTime.UtcNow.AddSeconds(2);
                    while(access.GetFeature("AcquisitionStatusRegister")=="0") {
                        if(DateTime.UtcNow>deadline) throw new Exception("Camera acquisition did not start before software trigger");
                        Thread.Sleep(10);
                    }
                    Console.WriteLine("SOFTWARE_CAMERA_MODE="+access.GetFeature("TriggerMode"));
                    access.ExecuteCommand("TriggerSoftware");
                    Console.WriteLine("TRIGGER_SOFTWARE_EXECUTED");
                    int ticket;image=fifo.CompleteAcquire(requested,out ticket,out trigger);
                } else image=fifo.Acquire(out trigger);
                if(image==null || image.Width!=640 || image.Height!=480) throw new Exception("Image dimensions differ from camera");
                Console.WriteLine("IMAGE_RECEIVED="+image.Width+"x"+image.Height+" type="+image.GetType().FullName);
                try {Verify(image,rgb,args.Length>1?args[1]:null,i);}
                finally {var disposable=image as IDisposable;if(disposable!=null)disposable.Dispose();}
            }
            Console.WriteLine("PASS: native Cognex valid frames; all pixels checked");return 0;
        } catch(Exception error) {
            Console.Error.WriteLine(error.ToString());return 1;
        } finally {
            if(target!=null) try {target.Disconnect(false);Console.WriteLine("TARGET_DISCONNECTED");} catch(Exception e) {Console.Error.WriteLine("Disconnect: "+e.Message);}
        }
    }
}
