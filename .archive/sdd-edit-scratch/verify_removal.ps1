Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

Write-Host "Abstimmung ausstehend present: $($xml.Contains('Abstimmung ausstehend'))"
Write-Host "bookmarkStart _Toc229775509 present: $($xml.Contains('w:name=""_Toc229775509""'))"

# Count _Toc229775509 occurrences - should now only be TOC hyperlink refs (2), not bookmarkStart
$search = '_Toc229775509'
$pos = 0; $count = 0
while ($true) {
    $idx = $xml.IndexOf($search, $pos)
    if ($idx -lt 0) { break }
    $ctx = $xml.Substring([Math]::Max(0,$idx-30), 60)
    Write-Host "  occurrence $count at $idx : $ctx"
    $pos = $idx + 1; $count++
}
Write-Host "Total occurrences: $count (should be 2 - both TOC refs only)"

# Verify section 5.10 body flows directly to 5.11 Anforderungen
$idx510 = $xml.IndexOf('_Toc229775508')
# Find last occurrence (body)
$pos = 0; $last510 = -1
while ($true) {
    $idx = $xml.IndexOf('_Toc229775508', $pos)
    if ($idx -lt 0) { break }
    $last510 = $idx; $pos = $idx + 1
}
$pend510 = $xml.IndexOf('</w:p>', $last510) + 6
$next2000 = $xml.Substring($pend510, [Math]::Min(2000, $xml.Length - $pend510))
$stripped = [regex]::Replace($next2000, '<[^>]+>', '')
Write-Host "`n=== Content after 5.10 heading (stripped, 600 chars) ==="
Write-Host $stripped.Substring(0, [Math]::Min(600, $stripped.Length))
