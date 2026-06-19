Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

# Find the bookmarkStart for _Toc229775509 (Internetzugang section body)
$search = '_Toc229775509'
$positions = @()
$pos = 0
while ($true) {
    $idx = $xml.IndexOf($search, $pos)
    if ($idx -lt 0) { break }
    $positions += $idx
    $pos = $idx + 1
}
Write-Host "Found $($positions.Count) occurrences of _Toc229775509"

# Body occurrence = last one with bookmarkStart (not hyperlink)
foreach ($p in $positions) {
    $context = $xml.Substring([Math]::Max(0, $p - 50), 80)
    Write-Host "  at $p context: $context"
}

# Get the body section - last occurrence should be the bookmarkStart in body
$bodyIdx = $positions[-1]
$pstart = $xml.LastIndexOf('<w:p ', $bodyIdx)
$pend = $xml.IndexOf('</w:p>', $bodyIdx) + 6

# Extract next 1500 chars after heading paragraph
$bodyText = $xml.Substring($pend, [Math]::Min(1500, $xml.Length - $pend))
# Strip XML tags
$stripped = [regex]::Replace($bodyText, '<[^>]+>', '')
Write-Host "`n=== Internetzugang body (stripped) ==="
Write-Host $stripped.Substring(0, [Math]::Min(800, $stripped.Length))
