using System;
using Cognex.VisionPro;

// Independent consumer implementation using the installed Cognex SDK sample API.
// Enumeration only: never controls or disconnects unrelated hardware.
class G00VisionProDiscovery {
    [STAThread]
    static int Main(string[] args) {
        Console.OutputEncoding = System.Text.Encoding.UTF8;
        try {
            Console.WriteLine("Cognex SDK: " + typeof(CogFrameGrabbers).Assembly.FullName);
            var devices = new CogFrameGrabbers();
            Console.WriteLine("FrameGrabberCount=" + devices.Count);
            bool targetFound = false;
            foreach (ICogFrameGrabber device in devices) {
                Console.WriteLine("Name=" + device.Name + "; Serial=" + device.SerialNumber);
                foreach (string format in device.AvailableVideoFormats) Console.WriteLine("Format=" + format);
                if (device.SerialNumber != "VICG00") continue;
                targetFound = true;
                if (args.Length == 1 && args[0] == "--acquire") {
                    try {
                        Console.WriteLine("TARGET_SELECTED serial=VICG00");
                        var fifo = device.CreateAcqFifo("Generic GigEVision (Mono)",
                            CogAcqFifoPixelFormatConstants.Format8Grey, 0, false);
                        fifo.Timeout = 5000;
                        Console.WriteLine("FIFO_CREATED target=VICG00 (device opened)");
                        for (int i = 0; i < 5; ++i) {
                            int trigger;
                            Console.WriteLine("ACQUISITION_REQUEST=" + i);
                            var image = fifo.Acquire(out trigger);
                            if (image == null || image.Width != 640 || image.Height != 480)
                                throw new Exception("Unexpected image dimensions");
                            Console.WriteLine("IMAGE_RECEIVED " + image.Width + "x" + image.Height + "; type=" + image.GetType().FullName);
                        }
                    } finally { device.Disconnect(false); }
                } else { device.Disconnect(false); }
            }
            Console.WriteLine("Probe completed. Acquisition only attempted when --acquire and target serial matched.");
            return targetFound ? 0 : 2;
        } catch (Exception error) {
            Console.Error.WriteLine(error.ToString());
            return 1;
        }
    }
}
