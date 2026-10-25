using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Text.Json.Nodes;
using System.Threading.Tasks;
using Microsoft.UI;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.Storage.Pickers;
using Windows.Storage.Streams;
using WinRT.Interop;

namespace VICControl.WinUI;

public sealed partial class MainWindow : Window
{
    public ObservableCollection<Metric> Metrics { get; } = new()
    {
        new("本地平均 FPS", "\uE9D9", new SolidColorBrush(Colors.SeaGreen)),
        new("提交 FPS", "\uE9D9", new SolidColorBrush(Colors.DodgerBlue)),
        new("本地 FrameID", "\uE81E", new SolidColorBrush(Colors.MediumPurple)),
        new("本地产生帧", "\uE8A5", new SolidColorBrush(Colors.SeaGreen)),
        new("模拟丢帧", "\uE814", new SolidColorBrush(Colors.IndianRed)),
        new("触发延迟", "\uE823", new SolidColorBrush(Colors.Goldenrod)),
        new("Packet Size", "\uE81E", new SolidColorBrush(Colors.DodgerBlue)),
        new("VisionPro 连接", "\uE71B", new SolidColorBrush(Colors.SeaGreen)),
    };
    private BridgeClient? bridge;
    private readonly DispatcherTimer timer = new() { Interval = TimeSpan.FromMilliseconds(900) };
    private readonly DispatcherTimer frameTimer = new() { Interval = TimeSpan.FromMilliseconds(100) };
    private bool busy, polling, framePolling, engineAcquiring, loaded;
    private long lastFrame;
    private string lastLogText = "";

    public MainWindow()
    {
        InitializeComponent();
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1600, 900));
        Navigation.RequestedTheme = ElementTheme.Light;
        Navigation.SelectedItem = NavOverview;
        Navigation.SelectionChanged += (_, e) => ShowPage((e.SelectedItem as NavigationViewItem)?.Tag?.ToString() ?? "overview");
        StartCameraButton.Click += async (_, _) => await Act("publish", true, "GigE 相机已发布；请在 VisionPro 分别验证发现、打开、参数和有效图像。");
        StopCameraButton.Click += async (_, _) => await Act("stop_camera", false, "GigE 相机已停止。");
        StartEngineButton.Click += async (_, _) => await Act("start_engine", false, "本地 Engine 已启动。");
        StopEngineButton.Click += async (_, _) => await Act("stop_engine", false, "本地 Engine 已关闭。");
        ReconnectButton.Click += async (_, _) => { lastFrame = 0; await Refresh(); };
        ApplyButton.Click += async (_, _) => await Act("apply", true, "本地配置已应用。");
        BeginButton.Click += async (_, _) => await Act("begin", false, "本地采集已开始。");
        EndButton.Click += async (_, _) => await Act("end", false, "本地采集已停止。");
        TriggerButton.Click += async (_, _) => await Act("trigger", false, "软件触发已发送。");
        ApplyPreviewButton.Click += async (_, _) => await Act("apply_and_preview", true, "当前来源已应用并开始本地预览。");
        ApplyRuntimeButton.Click += async (_, _) => await Run(async () => { await Bridge().CallAsync("runtime", new { fps_milli = (int)FpsInput.Value * 1000, delay_us = (int)DelayInput.Value * 1000, drop_percent = (int)DropInput.Value, seed = (int)SeedInput.Value }); Message("运行参数已应用。"); });
        ProbeButton.Click += async (_, _) => await Probe();
        BrowseFileButton.Click += async (_, _) => await Choose(false);
        BrowseFolderButton.Click += async (_, _) => await Choose(true);
        EditSourceButton.Click += (_, _) => Navigation.SelectedItem = NavSource;
        EditAcquireButton.Click += (_, _) => Navigation.SelectedItem = NavAcquire;
        ExportTopButton.Click += async (_, _) => await Export();
        ExportLogsButton.Click += async (_, _) => await Export();
        ClearLogsButton.Click += (_, _) => ServiceLog.Text = "";
        DarkModeSwitch.Toggled += (_, _) => Navigation.RequestedTheme = DarkModeSwitch.IsOn ? ElementTheme.Dark : ElementTheme.Light;
        timer.Tick += async (_, _) => await Refresh();
        frameTimer.Tick += async (_, _) => await UpdateFrame();
        timer.Start();
        frameTimer.Start();
        _ = Initialize();
    }
    private BridgeClient Bridge() => bridge ?? throw new InvalidOperationException("后台桥接尚未启动。");
    private static string S(JsonNode? node, string fallback = "—") => node?.ToString() ?? fallback;
    private static long N(JsonNode? node) => long.TryParse(node?.ToString(), out long n) ? n : 0;
    private static double D(JsonNode? node) => double.TryParse(node?.ToString(), System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out double n) ? n : 0;
    private static bool B(JsonNode? node) => node?.ToString() is "1" or "true" or "True";
    private async Task Initialize() { try { bridge = new BridgeClient(); await Refresh(); } catch (Exception e) { Error(e); } }
    private void ShowPage(string page)
    {
        OverviewPage.Visibility = page == "overview" ? Visibility.Visible : Visibility.Collapsed;
        CameraPage.Visibility = page == "camera" ? Visibility.Visible : Visibility.Collapsed;
        SourcePage.Visibility = page == "source" ? Visibility.Visible : Visibility.Collapsed;
        AcquirePage.Visibility = page == "acquire" ? Visibility.Visible : Visibility.Collapsed;
        MonitorPage.Visibility = page == "monitor" ? Visibility.Visible : Visibility.Collapsed;
        LogsPage.Visibility = page == "logs" ? Visibility.Visible : Visibility.Collapsed;
        SettingsPage.Visibility = page == "settings" ? Visibility.Visible : Visibility.Collapsed;
    }
    private async Task Refresh()
    {
        if (busy || polling || bridge is null) return;
        polling = true;
        try
        {
            JsonNode? status = await bridge.CallAsync("status");
            if (status is null) return;
            if (!loaded) { Load(status["config"]); loaded = true; }
            Paint(status);
        }
        catch (Exception e) { Error(e); }
        finally { polling = false; }
    }
    private async Task UpdateFrame()
    {
        if (busy || framePolling || !engineAcquiring || bridge is null) return;
        framePolling = true;
        try
        {
            JsonNode? frame = await bridge.CallAsync("frame", new { after = lastFrame });
            if (frame is not null && N(frame["frame_id"]) > lastFrame)
            {
                lastFrame = N(frame["frame_id"]);
                byte[] data = Convert.FromBase64String(S(frame["jpeg"], ""));
                using InMemoryRandomAccessStream stream = new();
                using (DataWriter writer = new(stream)) { writer.WriteBytes(data); await writer.StoreAsync(); writer.DetachStream(); }
                stream.Seek(0);
                BitmapImage bitmap = new();
                await bitmap.SetSourceAsync(stream);
                PreviewImage.Source = bitmap;
                PreviewPlaceholder.Visibility = Visibility.Collapsed;
                PreviewStatus.Text = "●  本地预览";
                PreviewDetails.Text = $"本地帧 {lastFrame} · {S(frame["width"])} × {S(frame["height"])}。VisionPro 结果请在 VisionPro 查看。";
            }
        }
        catch (Exception e) { Error(e); }
        finally { framePolling = false; }
    }
    private void Paint(JsonNode status)
    {
        bool local = B(status["engine_alive"]), published = B(status["camera_alive"]);
        JsonNode? state = status["engine"];
        JsonNode? config = published ? status["published"] : local ? state?["config"] : status["config"];
        CameraName.Text = S(config?["model"], "VIC 相机");
        CameraState.Text = published ? "●  GigE 已发布" : "●  GigE 未发布";
        CameraState.Foreground = new SolidColorBrush(published ? Colors.SeaGreen : Colors.SlateGray);
        SidebarStatus.Text = local ? "●  本地 Engine 运行中" : "●  本地 Engine 未运行";
        CameraIpValue.Text = published ? S(status["camera_ip"]) : "—";
        AdapterValue.Text = published ? S(status["adapter"]?["name"], "VIC-PoC-TAP") : "待发布";
        PixelValue.Text = N(config?["pixel_format"]) == 0x02180014 ? "RGB8" : "Mono8";
        SizeValue.Text = $"{S(config?["width"])} × {S(config?["height"])}";
        FpsValue.Text = $"{D(config?["fps_milli"]) / 1000:g} FPS";
        PacketSummary.Text = published ? $"{S(status["packet_size"])} B" : "1400 B（发布时）";
        DelaySummary.Text = $"{D(config?["delay_us"]) / 1000:g} ms";
        SourceSummary.Text = S(config?["source_kind"], "pattern");
        Metrics[0].Value = local ? D(state?["average_fps"]).ToString("F2") : "—";
        Metrics[1].Value = "未提供";
        Metrics[2].Value = local ? S(state?["frame_id"]) : "—";
        Metrics[3].Value = local ? S(state?["generated"]) : "—";
        Metrics[4].Value = local ? S(state?["simulated_dropped"]) : "—";
        Metrics[5].Value = $"{D(config?["delay_us"]) / 1000:g} ms";
        Metrics[6].Value = published ? S(status["packet_size"]) : "—";
        Metrics[7].Value = "未提供";
        MonitorDetails.Text = local ? $"本地 Engine：{(B(state?["acquiring"]) ? "采集中" : "空闲")} · 已生成 {S(state?["generated"])} 帧 · 模拟丢帧 {S(state?["simulated_dropped"])}。\nGigE 后台：{(published ? "已发布" : "未发布")}。有效图像需在 VisionPro 验证。" : "本地 Engine 未运行。";
        StartCameraButton.IsEnabled = !published; StopCameraButton.IsEnabled = published;
        StartEngineButton.IsEnabled = !local; StopEngineButton.IsEnabled = local;
        ApplyButton.IsEnabled = local && !B(state?["acquiring"]) && !published;
        BeginButton.IsEnabled = local && !B(state?["acquiring"]);
        EndButton.IsEnabled = local && B(state?["acquiring"]);
        TriggerButton.IsEnabled = local && B(state?["acquiring"]) && N(state?["config"]?["trigger_mode"]) == 1;
        ApplyRuntimeButton.IsEnabled = local && !published;
        string logs = S(status["engine_log"], "") + "\n" + S(status["camera_log"], "");
        if (logs != lastLogText)
        {
            if (logs.StartsWith(lastLogText, StringComparison.Ordinal)) ServiceLog.Text += logs[lastLogText.Length..];
            else ServiceLog.Text = logs;
            lastLogText = logs;
            if (AutoScrollSwitch.IsOn) ServiceLog.SelectionStart = ServiceLog.Text.Length;
        }
        bool acquiring = B(state?["acquiring"]), editable = !published && !acquiring;
        engineAcquiring = local && acquiring;
        foreach (Control control in new Control[] { NameInput, ModelInput, SerialInput, SourceKindInput, SourcePathInput,
            BrowseFileButton, BrowseFolderButton, FitInput, AutoSizeInput, ProbeButton, ApplyPreviewButton,
            WidthInput, HeightInput, PixelInput, TriggerInput }) control.IsEnabled = editable;
        PreviewStatus.Text = local && acquiring ? (PreviewImage.Source is null ? "●  等待帧" : "●  本地预览") : "●  未采集";
        if (PreviewImage.Source is null)
            PreviewDetails.Text = local ? (acquiring ? "Engine 正在采集，等待图像帧。" : "Engine 已连接，尚未开始采集。") : "本地 Engine 未运行。VisionPro 图像结果请在 VisionPro 查看。";
    }
    private void Load(JsonNode? config)
    {
        if (config is null) return;
        NameInput.Text = S(config["name"], "VIC Camera 01"); ModelInput.Text = S(config["model"], "VIC-1000"); SerialInput.Text = S(config["serial"], "VIC000001");
        SourcePathInput.Text = S(config["path"], "");
        SourceKindInput.SelectedIndex = S(config["source_kind"], "pattern") switch { "image" => 1, "sequence" => 2, "video" => 3, _ => 0 };
        FitInput.IsChecked = N(config["fit"]) != 0;
        WidthInput.Value = N(config["width"]); HeightInput.Value = N(config["height"]); FpsInput.Value = D(config["fps_milli"]) / 1000;
        PixelInput.SelectedIndex = N(config["pixel_format"]) == 0x02180014 ? 1 : 0;
        TriggerInput.SelectedIndex = N(config["trigger_mode"]) == 1 ? 1 : 0;
        DelayInput.Value = D(config["delay_us"]) / 1000; DropInput.Value = D(config["drop_percent"]); SeedInput.Value = D(config["seed"]);
    }
    private object Config()
    {
        string kind = (SourceKindInput.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "pattern", path = SourcePathInput.Text.Trim();
        if (kind == "pattern" && path.Length > 0)
        {
            if (new[] { ".png", ".jpg", ".jpeg", ".bmp" }.Contains(Path.GetExtension(path).ToLowerInvariant())) kind = "image";
            else throw new InvalidOperationException("测试图模式不能指定该路径，请选择图片、文件夹或视频来源。");
        }
        if (kind != "pattern" && !File.Exists(path) && !Directory.Exists(path)) throw new FileNotFoundException("图像源不存在：" + path);
        foreach (double number in new[] { WidthInput.Value, HeightInput.Value, FpsInput.Value, DelayInput.Value, DropInput.Value, SeedInput.Value })
            if (double.IsNaN(number)) throw new InvalidOperationException("请检查采集参数中的数字输入。");
        return new { name = NameInput.Text.Trim(), model = ModelInput.Text.Trim(), serial = SerialInput.Text.Trim(),
            source_kind = kind, path, fit = FitInput.IsChecked == true ? 1 : 0, width = (int)WidthInput.Value, height = (int)HeightInput.Value,
            pixel_format = PixelInput.SelectedIndex == 1 ? 0x02180014 : 0x01080001,
            fps_milli = (int)(FpsInput.Value * 1000), trigger_mode = TriggerInput.SelectedIndex == 1 ? 1 : 0,
            delay_us = (int)(DelayInput.Value * 1000), drop_percent = (int)DropInput.Value, seed = (int)SeedInput.Value };
    }
    private async Task Act(string op, bool sendConfig, string message) => await Run(async () =>
    {
        if (sendConfig) await Bridge().CallAsync("set_config", Config());
        await Bridge().CallAsync(op);
        if (op is "apply" or "apply_and_preview") { lastFrame = 0; PreviewImage.Source = null; PreviewPlaceholder.Visibility = Visibility.Visible; }
        Message(message);
    });
    private async Task Run(Func<Task> work)
    {
        if (busy) { Message("请等待当前操作完成。"); return; }
        busy = true;
        try { await work(); } catch (Exception e) { Error(e); }
        finally { busy = false; await Refresh(); }
    }
    private async Task Probe() => await Run(async () =>
    {
        await Bridge().CallAsync("set_config", Config());
        JsonNode? size = await Bridge().CallAsync("probe");
        if (size is not null) { WidthInput.Value = N(size["width"]); HeightInput.Value = N(size["height"]); Message($"已读取原始分辨率 {WidthInput.Value:g} × {HeightInput.Value:g}。"); }
    });
    private async Task Choose(bool folder)
    {
        try
        {
            if (folder)
            {
                FolderPicker picker = new(); picker.FileTypeFilter.Add("*");
                InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
                var item = await picker.PickSingleFolderAsync();
                if (item is null) return;
                SourcePathInput.Text = item.Path; SourceKindInput.SelectedIndex = 2;
            }
            else
            {
                FileOpenPicker picker = new();
                foreach (string ext in new[] { ".png", ".jpg", ".jpeg", ".bmp", ".avi", ".mp4", ".mkv", ".mov", ".wmv" }) picker.FileTypeFilter.Add(ext);
                InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
                var item = await picker.PickSingleFileAsync();
                if (item is null) return;
                SourcePathInput.Text = item.Path;
                SourceKindInput.SelectedIndex = new[] { ".png", ".jpg", ".jpeg", ".bmp" }.Contains(Path.GetExtension(item.Path).ToLowerInvariant()) ? 1 : 3;
            }
            if (AutoSizeInput.IsChecked == true) await Probe();
        }
        catch (Exception e) { Error(e); }
    }
    private async Task Export()
    {
        try
        {
            FileSavePicker picker = new();
            picker.FileTypeChoices.Add("ZIP 诊断包", new[] { ".zip" }); picker.SuggestedFileName = "VIC09-diagnostics";
            InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
            var file = await picker.PickSaveFileAsync();
            if (file is not null) await Run(async () => { await Bridge().CallAsync("export", file.Path); Message("诊断日志已导出：" + file.Path); });
        }
        catch (Exception e) { Error(e); }
    }
    private void Message(string text) { StatusBar.Severity = InfoBarSeverity.Informational; StatusBar.Message = text; StatusBar.IsOpen = true; }
    private void Error(Exception e) { StatusBar.Severity = InfoBarSeverity.Error; StatusBar.Message = e.Message; StatusBar.IsOpen = true; }
}
