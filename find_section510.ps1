Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

# Find all occurrences
$search = '_Toc229775508'
$positions = @()
$pos = 0
while ($true) {
    $idx = $xml.IndexOf($search, $pos)
    if ($idx -lt 0) { break }
    $positions += $idx
    $pos = $idx + 1
}
Write-Host "Found $($positions.Count) occurrences at: $($positions -join ', ')"

# 3rd occurrence is likely the body section heading (bookmarkStart)
$bodyIdx = $positions[2]
# Get paragraph containing it
$pstart = $xml.LastIndexOf('<w:p ', $bodyIdx)
$pend = $xml.IndexOf('</w:p>', $pstart) + 6
Write-Host "Heading para: $pstart to $pend"

# Extract 5000 chars after heading paragraph end to see body text
$bodyExtract = $xml.Substring($pend, [Math]::Min(5000, $xml.Length - $pend))
[System.IO.File]::WriteAllText('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\section510_after_heading.txt', $bodyExtract, [System.Text.Encoding]::UTF8)
Write-Host "Written section510_after_heading.txt"
