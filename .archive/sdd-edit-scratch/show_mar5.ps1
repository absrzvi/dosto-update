Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

$idx = $xml.IndexOf('MAR5')
$start = [Math]::Max(0, $idx - 500)
$extract = $xml.Substring($start, [Math]::Min(1500, $xml.Length - $start))
$stripped = [regex]::Replace($extract, '<[^>]+>', '')
Write-Host "=== Context around MAR5 ==="
Write-Host $stripped
