param(
 [Parameter(Mandatory=$true)][string]$Manifest,
 [Parameter(Mandatory=$true)][string]$OutputPath,
 [string]$RenderDirectory='',
 [string]$PythonExe='python'
)
$ErrorActionPreference='Stop'
$mf=(Resolve-Path -LiteralPath $Manifest).Path;$base=Split-Path $mf -Parent
$plan=Get-Content -LiteralPath $mf -Raw|ConvertFrom-Json
$items=@($plan.slides);if($items.Count -lt 1){throw '清单没有页面'}
$dest=[IO.Path]::GetFullPath($OutputPath);if(Test-Path -LiteralPath $dest){throw '输出文件已存在，请另存新文件'}
$inputs=@();foreach($item in $items){$fp=[string]$item.path;if(-not [IO.Path]::IsPathRooted($fp)){$fp=Join-Path $base $fp};$fp=(Resolve-Path -LiteralPath $fp).Path;if($fp -eq $dest){throw '输出不能覆盖输入'};$inputs+=@{path=$fp;layout_id=$item.layout_id;source_stamp=$item.source_stamp}}
New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent)|Out-Null
if($RenderDirectory){$RenderDirectory=[IO.Path]::GetFullPath($RenderDirectory);New-Item -ItemType Directory -Force -Path $RenderDirectory|Out-Null}
$app=New-Object -ComObject PowerPoint.Application;$app.DisplayAlerts=1;$baseline=$app.Presentations.Count;$result=$null;$records=@()
try{
 $result=$app.Presentations.Add(0)
 foreach($item in $inputs){
  $src=$null
  try{
   $src=$app.Presentations.Open($item.path,-1,0,0)
   if($src.Slides.Count -ne 1){throw '每个输入必须是已填充的单页组件'}
   if($plan.require_template_source -or $item.source_stamp){
    $prefix="epoint:$($item.layout_id):$($plan.theme):"
    if($plan.library_commit -cnotmatch '^[0-9a-f]{40}$' -or -not $item.source_stamp -or -not $item.source_stamp.StartsWith($prefix) -or -not $item.source_stamp.EndsWith(":$($plan.library_commit)") -or $src.Slides.Item(1).Name -cne $item.source_stamp){
     throw "单页组件来源与清单不符 $($item.path)"
    }
   }
   if($result.Slides.Count -eq 0){$result.PageSetup.SlideWidth=$src.PageSetup.SlideWidth;$result.PageSetup.SlideHeight=$src.PageSetup.SlideHeight}
   elseif([Math]::Abs($result.PageSetup.SlideWidth-$src.PageSetup.SlideWidth) -gt 0.5 -or [Math]::Abs($result.PageSetup.SlideHeight-$src.PageSetup.SlideHeight) -gt 0.5){throw '组件画布尺寸不一致，请先适配'}
   $at=$result.Slides.Count;$inserted=$result.Slides.InsertFromFile($item.path,$at,1,1)
   if($inserted -ne 1){throw '插入页数异常'}
   $d=$result.Designs.Clone($src.Slides.Item(1).Design)
   $new=$result.Slides.Item($at+1);$new.Design=$d
   if($item.source_stamp){$new.Name="$($item.source_stamp):$($at+1)"}
   # The source templates contain empty transition nodes and timed advances.
   # Reset them before any independently designed deck transition is applied.
   $new.SlideShowTransition.EntryEffect=0
   $new.SlideShowTransition.AdvanceOnTime=$false
   $new.SlideShowTransition.AdvanceOnClick=$true
   $layoutIndex=$src.Slides.Item(1).CustomLayout.Index
   if($layoutIndex -le $d.SlideMaster.CustomLayouts.Count){$new.CustomLayout=$d.SlideMaster.CustomLayouts.Item($layoutIndex)}
   # InsertFromFile and reattaching the cloned design can discard an explicit
   # slide background. Restore the filled source page's solid background only
   # when it has one; inherited template backgrounds remain untouched.
   if($src.Slides.Item(1).Background.Fill.Type -eq 1){
    $new.Background.Fill.Solid()
    $new.Background.Fill.ForeColor.RGB=$src.Slides.Item(1).Background.Fill.ForeColor.RGB
   }
   # PowerPoint can remap placeholder geometry when it attaches a cloned layout.
   # Reattaching a cloned layout can reposition native placeholders. Their
   # geometry can be restored, but PowerPoint may still render placeholder
   # text using the cloned layout's text anchor. For a shifted single-run
   # placeholder, move its text into a normal editable textbox at the source
   # coordinates, then clear the displaced placeholder.
   foreach($sourceShape in $src.Slides.Item(1).Shapes){
    if($sourceShape.Type -ne 14 -and -not ([string]$sourceShape.Name).StartsWith('field:')){continue}
    foreach($targetShape in $new.Shapes){
     if($targetShape.Id -eq $sourceShape.Id -and $targetShape.Name -eq $sourceShape.Name){
      $shifted=([Math]::Abs($targetShape.Left-$sourceShape.Left) -gt 0.5 -or [Math]::Abs($targetShape.Top-$sourceShape.Top) -gt 0.5 -or [Math]::Abs($targetShape.Width-$sourceShape.Width) -gt 0.5 -or [Math]::Abs($targetShape.Height-$sourceShape.Height) -gt 0.5)
      if($shifted -and $sourceShape.Type -eq 14 -and $sourceShape.HasTextFrame -and $sourceShape.TextFrame.HasText){
       $sourceText=$sourceShape.TextFrame.TextRange
       if($sourceText.Runs().Count -ne 1){throw "占位框含复杂富文本，不能自动恢复：$($item.path) $($sourceShape.Name)"}
       # The source badge/background may live on the cloned layout. Move its
       # matching placeholder as well, otherwise the text and badge separate.
       $layoutMatch=$null
       foreach($layoutShape in $new.CustomLayout.Shapes){
        if($layoutShape.Type -eq 14 -and [Math]::Abs($layoutShape.Left-$sourceShape.Left) -lt 1 -and [Math]::Abs($layoutShape.Width-$sourceShape.Width) -lt 1 -and [Math]::Abs($layoutShape.Height-$sourceShape.Height) -lt 1){$layoutMatch=$layoutShape;break}
       }
       # Some verified source pages use a placeholder whose visual backing is
       # on the slide rather than in its custom layout. Restore the text even
       # when there is no matching layout placeholder to move.
       if($layoutMatch){
        $layoutMatch.Left=$sourceShape.Left;$layoutMatch.Top=$sourceShape.Top
        $layoutMatch.Width=$sourceShape.Width;$layoutMatch.Height=$sourceShape.Height
       }
       $recovered=$new.Shapes.AddTextbox(1,$sourceShape.Left,$sourceShape.Top,$sourceShape.Width,$sourceShape.Height)
       $recovered.Name="field:recovered:$($sourceShape.Id)"
       $recovered.TextFrame.TextRange.Text=$sourceText.Text
       $recovered.TextFrame.MarginLeft=$sourceShape.TextFrame.MarginLeft
       $recovered.TextFrame.MarginRight=$sourceShape.TextFrame.MarginRight
       $recovered.TextFrame.MarginTop=$sourceShape.TextFrame.MarginTop
       $recovered.TextFrame.MarginBottom=$sourceShape.TextFrame.MarginBottom
       $recovered.TextFrame.VerticalAnchor=$sourceShape.TextFrame.VerticalAnchor
       $recovered.TextFrame.WordWrap=$sourceShape.TextFrame.WordWrap
       $recovered.TextFrame.TextRange.ParagraphFormat.Alignment=$sourceText.ParagraphFormat.Alignment
       $recovered.TextFrame.TextRange.Font.Name=$sourceText.Font.Name
       $recovered.TextFrame.TextRange.Font.Size=$sourceText.Font.Size
       $recovered.TextFrame.TextRange.Font.Bold=$sourceText.Font.Bold
       $recovered.TextFrame.TextRange.Font.Color.RGB=$sourceText.Font.Color.RGB
       $targetShape.TextFrame.TextRange.Text=''
      }
      $targetShape.Left=$sourceShape.Left;$targetShape.Top=$sourceShape.Top
      $targetShape.Width=$sourceShape.Width;$targetShape.Height=$sourceShape.Height
      break
     }
    }
   }
   # A brand placeholder on the cloned layout may reappear behind the actual Logo.
   $hasLogo=$false
   foreach($shape in $new.Shapes){if(([string]$shape.Name).StartsWith('brand:logo:')){$hasLogo=$true;break}}
   if($hasLogo){
    foreach($shape in $new.CustomLayout.Shapes){
     if($shape.HasTextFrame -and $shape.TextFrame.HasText){
      $value=([string]$shape.TextFrame.TextRange.Text).Trim()
      if($value -in @('公司名','品牌名称','[品牌名称]')){$shape.TextFrame.TextRange.Text=''}
     }
    }
   }
   $records+=@{page=$at+1;input=$item.path;layout_id=$item.layout_id;source_stamp=$item.source_stamp;source_sha256=(Get-FileHash -LiteralPath $item.path -Algorithm SHA256).Hash;source_format_preserved=$true}
  }finally{if($src){$src.Close()}}
 }
 $result.SaveAs($dest,24)
}finally{if($result){$result.Close()};if($baseline -eq 0){$app.Quit()}}
& $PythonExe (Join-Path $PSScriptRoot 'restore_recovered_geometry.py') --input $dest --manifest $mf
if($LASTEXITCODE -ne 0){throw '合并后占位框文字位置恢复失败'}
& $PythonExe (Join-Path $PSScriptRoot 'normalize_fonts.py') --input $dest --out $dest
if($LASTEXITCODE -ne 0){throw '合并后字体归一失败'}
$themeReport=[IO.Path]::ChangeExtension($dest,'theme.json')
& $PythonExe (Join-Path $PSScriptRoot 'audit_theme_integrity.py') --input $dest --manifest $mf --report $themeReport
$themeSourceConsistent=($LASTEXITCODE -eq 0)
if(-not $themeSourceConsistent){Write-Warning "合并后的母版主题与来源不同；组件颜色独立性检查将决定是否可交付。详见 $themeReport"}
$colorReport=[IO.Path]::ChangeExtension($dest,'colors.json')
& $PythonExe (Join-Path $PSScriptRoot 'audit_component_color_independence.py') --input $dest --report $colorReport
if($LASTEXITCODE -ne 0){throw "合并后的组件仍引用母版主题色槽；详见 $colorReport"}
$mediaReport=[IO.Path]::ChangeExtension($dest,'media.json')
& $PythonExe (Join-Path $PSScriptRoot 'repair_svg_fallbacks.py') --input $dest --manifest $mf --report $mediaReport
if($LASTEXITCODE -ne 0){throw '合并后图片主引用修复失败；请查看媒体检查报告'}
$media=Get-Content -LiteralPath $mediaReport -Raw -Encoding utf8|ConvertFrom-Json
$fontReport=[IO.Path]::ChangeExtension($dest,'fonts.json')
& $PythonExe (Join-Path $PSScriptRoot 'audit_fonts.py') --input $dest --report $fontReport
if($LASTEXITCODE -ne 0){throw "成稿字体不符合中文微软雅黑、英文及数字 Arial 的规则；详见 $fontReport"}
$logoReport=[IO.Path]::ChangeExtension($dest,'logo.json')
& $PythonExe (Join-Path $PSScriptRoot 'audit_logo.py') --input $dest --theme $plan.theme --require-every-slide --report $logoReport
if($LASTEXITCODE -ne 0){throw "成稿 Logo 数量或所选风格外观不合格；详见 $logoReport"}
if($RenderDirectory){
 $renderApp=New-Object -ComObject PowerPoint.Application
 try{
  $renderDeck=$renderApp.Presentations.Open($dest,$true,$false,$false)
  try{foreach($slide in $renderDeck.Slides){$slide.Export((Join-Path $RenderDirectory ('P{0:D3}.png' -f $slide.SlideIndex)),'PNG',1280,720)}}finally{$renderDeck.Close()}
 }finally{$renderApp.Quit()}
}
$report=@{manifest=$mf;output=$dest;slides=$records;slide_count=$records.Count;editable_pptx=$true;rendered=[bool]$RenderDirectory;theme_integrity_report=$themeReport;theme_source_consistent=$themeSourceConsistent;color_independence_report=$colorReport;media_fallback_report=$mediaReport;font_report=$fontReport;logo_report=$logoReport;restored_image_references=$media.restored;visual_qa='not_run';collision_qa='not_run';limitations=@('合并不代表内容与排版验收通过；还需检查文字、关系、数据和配图')}
$report|ConvertTo-Json -Depth 8|Set-Content -LiteralPath ([IO.Path]::ChangeExtension($dest,'assembly.json')) -Encoding utf8
Write-Output ('Assembled '+$records.Count+' editable slides')

