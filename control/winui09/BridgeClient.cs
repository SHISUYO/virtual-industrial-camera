using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;

namespace VICControl.WinUI;

// Thin JSON-line transport. Camera ownership, validation, and IPC remain in the existing Python services.
public sealed class BridgeClient : IDisposable
{
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly Process _process;
    private long _id;

    public BridgeClient()
    {
        string folder = AppContext.BaseDirectory;
        string packaged = Path.Combine(folder, "bridge", "VICBridge.exe");
        ProcessStartInfo start;
        if (File.Exists(packaged))
            start = new ProcessStartInfo(packaged);
        else
        {
            string? root = FindRoot(folder);
            if (root is null) throw new FileNotFoundException("VICBridge.exe 不存在，也找不到源代码开发环境。", packaged);
            string python = Path.Combine(root, "out", "g05", "venv", "Scripts", "python.exe");
            if (!File.Exists(python)) throw new FileNotFoundException("未找到开发环境 Python，请运行独立发布包。", python);
            start = new ProcessStartInfo(python, "-u " + JsonSerializer.Serialize(Path.Combine(root, "control", "winui_bridge09.py")))
            {
                WorkingDirectory = root
            };
        }
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardInput = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.StandardOutputEncoding = System.Text.Encoding.UTF8;
        start.StandardInputEncoding = System.Text.Encoding.UTF8;
        _process = Process.Start(start) ?? throw new InvalidOperationException("无法启动 VIC 后台桥接程序。");
    }

    private static string? FindRoot(string folder)
    {
        for (DirectoryInfo? dir = new(folder); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "control", "winui_bridge09.py"))) return dir.FullName;
        return null;
    }

    public async Task<JsonNode?> CallAsync(string op, object? value = null)
    {
        await _gate.WaitAsync();
        try
        {
            long id = Interlocked.Increment(ref _id);
            string message = JsonSerializer.Serialize(new { id, op, value });
            await _process.StandardInput.WriteLineAsync(message);
            await _process.StandardInput.FlushAsync();
            string? line = await _process.StandardOutput.ReadLineAsync();
            if (line is null)
                throw new IOException("后台桥接程序已退出。" + await _process.StandardError.ReadToEndAsync());
            JsonNode reply = JsonNode.Parse(line) ?? throw new InvalidDataException("后台返回空 JSON。");
            if (reply["id"]?.GetValue<long>() != id) throw new InvalidDataException("后台响应 ID 不匹配。");
            if (reply["ok"]?.GetValue<bool>() != true)
                throw new InvalidOperationException(reply["error"]?.ToString() ?? "后台操作失败。");
            return reply["result"]?.DeepClone();
        }
        finally { _gate.Release(); }
    }

    public void Dispose()
    {
        try { _process.StandardInput.Close(); } catch { }
        _process.Dispose();
        _gate.Dispose();
    }
}
