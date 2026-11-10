param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$OutputDir,
  [int]$Width=1280,
  [int]$Height=720
)
$ErrorActionPreference='Stop'
$src=(Resolve-Path -LiteralPath $InputPath).Path
$dst=[IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $dst | Out-Null
$app=New-Object -ComObject PowerPoint.Application
try {
  $presentation=$app.Presentations.Open($src,-1,0,0)
  try {
    for($i=1;$i -le $presentation.Slides.Count;$i++) {
      $target=Join-Path $dst ('P{0:D3}.png' -f $i)
      $presentation.Slides.Item($i).Export($target,'PNG',$Width,$Height)
    }
    Write-Output ('exported='+$presentation.Slides.Count)
  } finally { $presentation.Close() }
} finally { $app.Quit() }
