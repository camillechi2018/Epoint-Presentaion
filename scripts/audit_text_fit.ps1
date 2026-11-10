param(
  [Parameter(Mandatory=$true)][string[]]$InputPath,
  [string]$ReportPath='',
  [double]$TolerancePt=3
)
$ErrorActionPreference='Stop'
function Visit-Shape($shape,$prefix){
  if($shape.Type -eq 6){
    foreach($child in $shape.GroupItems){Visit-Shape $child "$prefix/$($shape.Id)"}
    return
  }
  if($shape.HasTextFrame -ne -1 -or $shape.TextFrame.HasText -ne -1){return}
  $range=$shape.TextFrame2.TextRange
  $actualH=[double]$range.BoundHeight
  $actualW=[double]$range.BoundWidth
  $boxH=[double]$shape.Height
  $boxW=[double]$shape.Width
  if($actualH -le 0 -or $actualW -le 0){return}
  $text=[string]$range.Text
  if($text.Trim() -match '^\|+$'){return}
  # PowerPoint reports an axis-aligned BoundHeight for rotated text. Comparing
  # that value with the unrotated textbox height produces false overflow hits.
  $rotated=([math]::Abs([double]$shape.Rotation) -gt 0.1)
  $records.Add(@{
    path=$prefix;shape_id=[int]$shape.Id;shape_name=[string]$shape.Name;text=$text;
    actual_width_pt=[math]::Round($actualW,2);actual_height_pt=[math]::Round($actualH,2);
    box_width_pt=[math]::Round($boxW,2);box_height_pt=[math]::Round($boxH,2);
    rotated_text_skipped=$rotated;rotation_deg=[math]::Round([double]$shape.Rotation,2);
    width_overflow=(-not $rotated -and $actualW -gt $boxW + $TolerancePt);
    height_overflow=(-not $rotated -and $actualH -gt $boxH + $TolerancePt)
  })|Out-Null
}
$app=New-Object -ComObject PowerPoint.Application
$results=@()
try{
  foreach($path in $InputPath){
    $resolved=(Resolve-Path -LiteralPath $path).Path
    $presentation=$app.Presentations.Open($resolved,-1,0,0)
    try{
      $records=[System.Collections.Generic.List[object]]::new()
      foreach($slide in $presentation.Slides){foreach($shape in $slide.Shapes){Visit-Shape $shape 'slide'}}
      $errors=@($records|Where-Object {$_.height_overflow -or $_.width_overflow})
      $results+=@{input=$resolved;slide_count=$presentation.Slides.Count;
        text_count=$records.Count;rotated_text_skipped_count=@($records|Where-Object {$_.rotated_text_skipped}).Count;
        overflow_count=$errors.Count;overflows=$errors}
    }finally{$presentation.Close()}
  }
}finally{$app.Quit()}
$report=@{passed=(@($results|Where-Object {$_.overflow_count -gt 0}).Count -eq 0);
  inputs=$results.Count;results=$results}
if($ReportPath){$report|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $ReportPath -Encoding utf8}
$report|ConvertTo-Json -Depth 5
if(-not $report.passed){exit 2}
