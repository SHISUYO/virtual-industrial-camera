using System.ComponentModel;
using Microsoft.UI.Xaml.Media;

namespace VICControl.WinUI;

public sealed class Metric : INotifyPropertyChanged
{
    private string _value = "—";
    public string Title { get; }
    public string Glyph { get; }
    public Brush Accent { get; }
    public string Value
    {
        get => _value;
        set { if (_value != value) { _value = value; PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Value))); } }
    }
    public event PropertyChangedEventHandler? PropertyChanged;
    public Metric(string title, string glyph, Brush accent) => (Title, Glyph, Accent) = (title, glyph, accent);
}
