param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [Parameter(Mandatory=$true)][string]$Library,
  [Parameter(Mandatory=$true)][string]$LayoutId,
  [switch]$AllowPrototype,
  [string]$ReportPath=''
)
$ErrorActionPreference='Stop'
$src=(Resolve-Path -LiteralPath $InputPath).Path
$root=(Resolve-Path -LiteralPath $Library).Path
$dest=[IO.Path]::GetFullPath($OutputPath)
if($src -eq $dest){throw '动效输出不能覆盖输入'}
if(Test-Path -LiteralPath $dest){throw '输出已存在，请另存新文件'}
if($LayoutId -notmatch '^[a-z0-9][a-z0-9-]*$'){throw '非法组件ID'}
$specPath=Join-Path $root "layouts/$LayoutId/motion.json"
$spec=Get-Content -LiteralPath $specPath -Raw -Encoding utf8|ConvertFrom-Json
if($spec.layout_id -ne $LayoutId -or $spec.preset -notin @('step-reveal','cycle-reveal') -or $spec.effect -ne 'fade') {throw '不支持的动效配置'}
if($spec.status -eq 'prototype' -and -not $AllowPrototype){throw '该动效是原型，请显式传 -AllowPrototype'}
if($spec.status -notin @('prototype','verified')){throw '动效尚未开放'}
$duration=[double]$spec.duration_seconds
if($duration -lt 0.1 -or $duration -gt 1.5){throw '动效时长超出范围'}
$app=New-Object -ComObject PowerPoint.Application
$presentation=$null
$records=@()
try{
  $presentation=$app.Presentations.Open($src,-1,0,0)
  if($presentation.Slides.Count -ne 1){throw '动效原型只接受单页可编辑 PPTX'}
  $slide=$presentation.Slides.Item(1)
  if($slide.TimeLine.MainSequence.Count -gt 0){throw '已有对象动画，停止叠加'}
  $shapeMap=@{}
  foreach($shape in $slide.Shapes){$shapeMap[[string]$shape.Id]=$shape}
  $seen=@{}
  $activeGroups=@()
  foreach($group in @($spec.groups)){
    if(@($group.shape_ids).Count -eq 0){throw '动效分组为空'}
    $present=@($group.shape_ids|Where-Object {$shapeMap.ContainsKey([string]$_)})
    if($present.Count -eq 0){continue}
    if($present.Count -ne @($group.shape_ids).Count){throw "第 $($group.step) 步动效目标只剩部分对象"}
    $activeGroups+=,$group
    foreach($shapeId in @($group.shape_ids)){
      $key=[string]$shapeId
      if(-not $shapeMap.ContainsKey($key)){throw "缺少目标形状 $key"}
      if($seen.ContainsKey($key)){throw "形状重复编组 $key"}
      if(([string]$shapeMap[$key].Name).StartsWith('brand:logo:')){throw 'Logo 不能参与动效'}
      $seen[$key]=$true
    }
  }
  foreach($staticId in @($spec.static_shape_ids)){
    if($seen.ContainsKey([string]$staticId)){throw "静态对象被加入动效 $staticId"}
  }
  $logicalStep=0
  foreach($group in $activeGroups){
    $logicalStep++
    $first=$true
    foreach($shapeId in @($group.shape_ids)){
      $trigger=if($first){1}else{2} # first on click, others with previous
      $effect=$slide.TimeLine.MainSequence.AddEffect($shapeMap[[string]$shapeId],10,0,$trigger) # fade
      $effect.Timing.Duration=$duration
      $effect.Timing.TriggerDelayTime=0
      $records+=@{step=$logicalStep;source_step=[int]$group.step;shape_id=[int]$shapeId;trigger=$trigger;duration_seconds=$duration}
      $first=$false
    }
  }
  New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent)|Out-Null
  $presentation.SaveAs($dest,24)
}finally{
  if($presentation){$presentation.Close()}
  $app.Quit()
}
if(-not $ReportPath){$ReportPath=[IO.Path]::ChangeExtension($dest,'motion.json')}
$report=@{layout_id=$LayoutId;input=$src;output=$dest;status='saved_playback_review_required';steps=@($activeGroups).Count;effects=$records.Count;records=$records;brand_static=$true}
$report|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Output ($report|ConvertTo-Json -Depth 2 -Compress)
