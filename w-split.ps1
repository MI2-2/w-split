$ErrorActionPreference = "SilentlyContinue"
# 使用する外部プログラムの指定
$7zip = "C:\Program Files\7-Zip\7z.exe"
$ralpha = "C:\Program Files (x86)\Ralpha\Ralpha.exe"
# ご使用の環境に応じて上の変数を変更してください。
# Ralphaのiniファイルは C:\Program Files (x86)\Ralpha\ini においてください。

# 対象ファイルのパスを取得
$cp = Split-Path $args[0] -Parent

foreach ( $arg in $args ) {

# 対象ファイルのあるパスに移動
Set-Location $cp

# ファイル名に半角スペースやブラケットがあるとうまく動かないので一時的にファイル名を rename_tmp に変更
# 元のファイル名は $org_name に保存
$org_name = [System.IO.Path]::GetFileNameWithoutExtension(${arg});
$tmp_name = "rename_tmp" + [System.IO.Path]::GetExtension(${arg});
Copy-Item -LiteralPath ${arg} -Destination $tmp_name

# 元ファイルはゴミ箱に移動。
Add-Type -AssemblyName Microsoft.VisualBasic
[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("${arg}",'OnlyErrorDialogs','SendToRecycleBin')

# rename_tmp の入った変数 $tmp_name をファイルオブジェクトに変換
$tmp_name = Get-ChildItem ${tmp_name} | get-item

# 作業用一時フォルダの準備
$tempDir = New-TemporaryFile | ForEach-Object { Remove-Item $_; mkdir $_ }

# ファイルの解凍
Write-Host "ファイル解凍中"
Start-Process -FilePath $7zip -ArgumentList "e $tmp_name -o$tempDir" -PassThru -Wait -nonewwindow

# 解凍したファイルの一覧を取得
$files = Get-ChildItem -file $tempDir
Write-Host "ファイルトリミング中"
# 最初の1ファイルだけ中心トリミング
foreach ($file in $files)
{
  $file = $file.FullName
  Start-Process -FilePath $ralpha -ArgumentList "/ini=Center.ini $file" -PassThru -Wait -nonewwindow
  # 初回のループで抜ける
  break
}
# 右ページだけ処理
Start-Process -FilePath $ralpha -ArgumentList "/ini=Right.ini $tempDir" -PassThru -Wait -nonewwindow
# 左ページだけ処理
Start-Process -FilePath $ralpha -ArgumentList "/ini=Left.ini $tempDir" -PassThru -Wait -nonewwindow

# 一時フォルダに展開されたresizeフォルダをエクスプローラーで開く
$img_dir = Join-Path $tempDir.FullName resize
Start-Process explorer -ArgumentList $img_dir -PassThru -Wait

write-host 不要ファイルを削除した後エクスプローラーを閉じてください。
pause

# 連番リネーム
write-host "連番リネーム中"
Set-Location $img_dir
Get-ChildItem -file | sort { [int]($_.Name -replace "\D", "") }, Name | % {$i = 1} {mv $_.Name (("{0:000}" + $_.Extension) -f $i++)}
Set-Location ..

# 余分なフォルダの削除とリネーム
Remove-Item -LiteralPath (Join-Path $tempDir.FullName $org_name) -Recurse -Force
Rename-Item -LiteralPath resize -NewName $org_name

# 再圧縮
Write-Host "ファイル圧縮中"
$zip = $cp + "\" + "$org_name" + ".zip"
$frename = $tempDir.FullName + "\" + "$org_name" + "\"
Start-Process -FilePath $7zip -ArgumentList "a ""${zip}"" ""${frename}""" -PassThru -Wait -nonewwindow
}
# 一時ファイルの掃除
Remove-Item $tmp_name
# 一時フォルダの掃除
$tempDir | ? { Test-Path $_ } | % { ls $_ -File -Recurse | rm; $_} | rmdir -Recurse
pause
