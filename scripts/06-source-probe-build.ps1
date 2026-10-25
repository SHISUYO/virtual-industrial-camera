# Reuse the installed SDK API usage, retaining the original G04 source/binary.
# Raw capture NEVER prints VALID_FRAME or claims pixel validation. Python verifies.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$out=Join-Path $root 'out/06-fix'
$source=Get-Content (Join-Path $root 'tests/automated/g04_visionpro_probe.cs') -Raw
$source=$source.Replace('G04VisionProProbe','VIC06SourceProbe')
$source=$source.Replace('mode=="rgb"','mode.StartsWith("rgb")').Replace('mode=="continuous"','(mode=="continuous" || mode=="rgb-continuous")').Replace('mode=="software"','mode.EndsWith("software")')
$source=$source.Replace('device.SerialNumber=="VICGE000001"','device.SerialNumber==(args.Length>3?args[3]:"VICGE000001")')
$pixelLine='                        if(red[x]!=((x+(rgb?0:y)+seed)&255) || (rgb && (green[x]!=((y+seed)&255) || blue[x]!=((x+y+seed)&255)))) throw new Exception("Pixel mismatch at "+x+","+y);'
if(!$source.Contains($pixelLine)){throw 'Original probe changed; review capture derivation first'}
$source=$source.Replace($pixelLine,'                        // Raw SDK pixels; independent whole-frame verification runs in Python.')
$source=$source.Replace('if(index==0 && folder!=null) File.WriteAllBytes(Path.Combine(folder,rgb?"sample.ppm":"sample.pgm"),saved.ToArray());','if(folder!=null) File.WriteAllBytes(Path.Combine(folder,"frame-"+index+(rgb?".ppm":".pgm")),saved.ToArray());')
$source=$source.Replace('"VALID_FRAME="+index+" seed="+seed+" all_pixels_checked=1"','"FRAME_CAPTURED="+index+" raw_pixels_saved=1"')
$source=$source.Replace('image==null || image.Width!=640 || image.Height!=480','image==null || image.Width<=0 || image.Height<=0')
$source=$source.Replace('PASS: native Cognex valid frames; all pixels checked','CAPTURE COMPLETE: raw frames saved; pixel validation pending')
$source | Set-Content (Join-Path $out 'source-probe.cs') -Encoding UTF8
$assemblies='C:/Program Files/Cognex/VisionPro/ReferencedAssemblies'
$response=@"
/nologo
/platform:x64
/r:"$assemblies/Cognex.VisionPro.dll"
/r:"$assemblies/Cognex.VisionPro.Core.dll"
/out:source-probe.exe
source-probe.cs
"@
$response.Replace('\','/') | Set-Content (Join-Path $out 'source-probe.rsp') -Encoding UTF8
Push-Location $out
try {
    & C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe '@source-probe.rsp'
    if($LASTEXITCODE -ne 0){throw 'Source SDK probe build failed'}
} finally {Pop-Location}
