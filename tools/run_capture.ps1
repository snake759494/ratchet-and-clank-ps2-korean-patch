param([string]$Iso, [string]$Script, [string]$OutDir)
# Script: "wait:5;key:~;shot:a;..." 형식
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte sc, int f, int e);
[DllImport("user32.dll")] public static extern uint MapVirtualKey(uint c, uint t);
public struct RECT { public int L,T,R,B; } }
"@
New-Item -ItemType Directory -Force $OutDir | Out-Null
$p = Start-Process -FilePath "D:\ps2\pcsx2-v2.2.0-windows-x64-Qt\pcsx2-qt.exe" -ArgumentList '-batch','--',"`"$Iso`"" -PassThru
$w = New-Object -ComObject WScript.Shell
try {
  foreach ($cmd in $Script.Split(';')) {
    $k,$v = $cmd.Split(':',2)
    switch ($k) {
      'wait' { Start-Sleep -Milliseconds ([int]([double]$v*1000)) }
      'key'  { $p.Refresh(); [W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 150
               $vk=[byte]([Convert]::ToInt32($v,16)); $sc=[byte][W]::MapVirtualKey($vk,0)
               [W]::keybd_event($vk,$sc,0,0); Start-Sleep -Milliseconds 180; [W]::keybd_event($vk,$sc,2,0); Start-Sleep -Milliseconds 250 }
      'save' { $p.Refresh(); [W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 150; $w.SendKeys('{F1}'); Start-Sleep -Seconds 4 }
      'slot' { $p.Refresh(); [W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 150; $w.SendKeys('{F2}'); Start-Sleep -Seconds 1 }
      'shot' { [W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 300
        $p.Refresh(); $r = New-Object W+RECT; [W]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
        $bmp = New-Object System.Drawing.Bitmap ($r.R-$r.L), ($r.B-$r.T)
        $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($r.L,$r.T,0,0,$bmp.Size)
        $bmp.Save("$OutDir\$v.png"); $g.Dispose(); $bmp.Dispose() }
    }
  }
} finally { Stop-Process -Name pcsx2-qt -Force -ErrorAction SilentlyContinue; Start-Sleep 2 }
