param(
 [Parameter(Mandatory=$true)][string]$InputPath,
 [Parameter(Mandatory=$true)][string]$ReportPath,
 [int[]]$Slides=@(),
 [string]$RenderDirectory='',
 [switch]$ReflowDecorations,
 [string]$OutputPath='',
 [double]$TolerancePt=3
)
$ErrorActionPreference='Stop'
$inputFile=(Resolve-Path -LiteralPath $InputPath).Path
if($ReflowDecorations -and -not $OutputPath){throw '调整装饰必须提供新OutputPath，保留原稿'}
if($OutputPath -and [IO.Path]::GetFullPath($OutputPath) -eq $inputFile){throw 'OutputPath不能覆盖输入文件'}
$reportFile=[IO.Path]::GetFullPath($ReportPath)
New-Item -ItemType Directory -Force -Path (Split-Path $reportFile -Parent)|Out-Null
if($RenderDirectory){$RenderDirectory=[IO.Path]::GetFullPath($RenderDirectory);New-Item -ItemType Directory -Force -Path $RenderDirectory|Out-Null}
# PowerPoint renders grouped text into slide coordinates. Do not compare raw child XML coordinates.
$arrowTypes=@(33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,52,53,54,55,56,57,58,59,60,176,177,178)
function Get-Leaves($shapes,$prefix){
 foreach($sh in $shapes){
  if($sh.Type -eq 6){Get-Leaves $sh.GroupItems "$prefix/$($sh.Id)";continue}
  $text=$null
  if($sh.HasTextFrame -eq -1 -and $sh.TextFrame2.HasText -eq -1 -and -not [string]::IsNullOrWhiteSpace($sh.TextFrame2.TextRange.Text)){
   $r=$sh.TextFrame2.TextRange
   $text=@{value=$r.Text;left=[double]$r.BoundLeft;top=[double]$r.BoundTop;right=[double]($r.BoundLeft+$r.BoundWidth);bottom=[double]($r.BoundTop+$r.BoundHeight)}
  }
  $arrow=$false
  if($sh.Type -eq 1){$arrow=$arrowTypes -contains [int]$sh.AutoShapeType}
  if($sh.Type -eq 9){$arrow=($sh.Line.BeginArrowheadStyle -ne 1 -or $sh.Line.EndArrowheadStyle -ne 1)}
  [pscustomobject]@{com=$sh;path="$prefix/$($sh.Id)";id=$sh.Id;name=$sh.Name;type=$sh.Type;arrow=$arrow;text=$text;left=[double]$sh.Left;top=[double]$sh.Top;right=[double]($sh.Left+$sh.Width);bottom=[double]($sh.Top+$sh.Height)}
 }
}
$app=New-Object -ComObject PowerPoint.Application
$app.DisplayAlerts=1
$issues=@();$adjustments=@();$checked=@();$counts=@{text_shapes=0;arrow_shapes=0}
try{
 $p=$app.Presentations.Open($inputFile,-1,0,0)
 try{
  foreach($slide in $p.Slides){
   if($Slides.Count -gt 0 -and $Slides -notcontains $slide.SlideIndex){continue}
   $items=@(Get-Leaves $slide.Shapes ([string]$slide.SlideIndex))
   if($ReflowDecorations){
    foreach($decoration in @($items|Where-Object {$_.name -like 'decoration:after:*'})){
     $anchorName=$decoration.name.Substring('decoration:after:'.Length)
     $anchor=@($items|Where-Object {$_.name -eq $anchorName -and $null -ne $_.text})
     if($anchor.Count -ne 1){throw "装饰锚点不唯一：$anchorName"}
     $left=$anchor[0].text.right+12
     if($left+$decoration.com.Width -gt $p.PageSetup.SlideWidth-36){throw '标题过长，装饰无法保持安全间距；请拆分或改版'}
     $decoration.com.Left=$left
     $adjustments+=@{slide=$slide.SlideIndex;shape=$decoration.id;anchor=$anchorName;gap_pt=12;left=$left}
    }
    $items=@(Get-Leaves $slide.Shapes ([string]$slide.SlideIndex))
   }
   $textItems=@($items|Where-Object {$null -ne $_.text});$arrows=@($items|Where-Object {$_.arrow})
   $counts.text_shapes+=$textItems.Count;$counts.arrow_shapes+=$arrows.Count
   foreach($a in $textItems){
    $b=$a.text
    if($b.left -lt $a.left-$TolerancePt -or $b.right -gt $a.right+$TolerancePt -or $b.top -lt $a.top-$TolerancePt -or $b.bottom -gt $a.bottom+$TolerancePt){
     $issues+=@{kind='text_ink_outside_shape';slide=$slide.SlideIndex;shape=$a.id;path=$a.path;text=$b.value;ink=$b;box=@($a.left,$a.top,$a.right,$a.bottom)}
    }
    foreach($arrow in $arrows){
     if($a.path -eq $arrow.path){continue}
     $overlapX=[Math]::Min($b.right,$arrow.right)-[Math]::Max($b.left,$arrow.left)
     $overlapY=[Math]::Min($b.bottom,$arrow.bottom)-[Math]::Max($b.top,$arrow.top)
     if($overlapX -gt $TolerancePt -and $overlapY -gt $TolerancePt){
      # A text box wholly contained in an arrow is often the arrow's intended label.
      $inside=($a.left -ge $arrow.left-$TolerancePt -and $a.right -le $arrow.right+$TolerancePt -and $a.top -ge $arrow.top-$TolerancePt -and $a.bottom -le $arrow.bottom+$TolerancePt)
      if(-not $inside){$issues+=@{kind='text_arrow_collision';slide=$slide.SlideIndex;shape=$a.id;path=$a.path;text=$b.value;obstacle=$arrow.id;obstacle_name=$arrow.name;overlap_pt=@($overlapX,$overlapY);ink=$b;obstacle_box=@($arrow.left,$arrow.top,$arrow.right,$arrow.bottom)}}
     }
    }
   }
   if($RenderDirectory){$slide.Export((Join-Path $RenderDirectory ('P{0:D2}.png' -f $slide.SlideIndex)),'PNG',1600,900)}
   $checked+=$slide.SlideIndex
  }
  if($OutputPath){$outputFile=[IO.Path]::GetFullPath($OutputPath);New-Item -ItemType Directory -Force -Path (Split-Path $outputFile -Parent)|Out-Null;$p.SaveAs($outputFile,24)}
 }finally{$p.Close()}
}finally{$app.Quit()}
$report=@{input=$inputFile;output=$OutputPath;checks=@('recursive_group_text_bounds','text_ink_outside_shape','text_arrow_collision');adjustments=$adjustments;checked_slides=$checked;counts=$counts;issues=$issues;passed=($issues.Count -eq 0);limitations=@('箭头碰撞使用边界框筛查，斜线与曲线结果需目视复核','不检测图片、表格或图表对象内部文字，也不判断语义关系；不代替逐页视觉检查')}
$report|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $reportFile -Encoding utf8
Write-Output ('Checked '+$checked.Count+' slides; issues: '+$issues.Count)
if($issues.Count -gt 0){exit 2}
exit 0
