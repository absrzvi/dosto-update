Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

$openCount = ([regex]::Matches($xml, '<w:del ')).Count
$closeCount = ([regex]::Matches($xml, '</w:del>')).Count
Write-Host "w:del open=$openCount close=$closeCount (should match)"
Write-Host "904_placeholder present: $($xml.Contains('904_placeholder'))"
Write-Host "Para 00000906 present: $($xml.Contains('00000906'))"

$idx = $xml.IndexOf('3D242E5B')
$pstart = $xml.LastIndexOf('<w:p ', $idx)
$pend = $xml.IndexOf('</w:p>', $idx) + 6
$para = $xml.Substring($pstart, $pend - $pstart)
Write-Host "Cell has proper w:del open: $($para.Contains('<w:del '))"
Write-Host "Cell has delText: $($para.Contains('delText'))"
Write-Host "Cell ends with /w:p: $($para.EndsWith('</w:p>'))"
Write-Host "Cell length: $($para.Length)"
