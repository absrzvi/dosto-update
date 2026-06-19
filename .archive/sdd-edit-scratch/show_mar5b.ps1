Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

$idx = $xml.IndexOf('MAR5')

# Find enclosing table row <w:tr
$trStart = $xml.LastIndexOf('<w:tr ', $idx)
$trEnd = $xml.IndexOf('</w:tr>', $idx) + 7
$row = $xml.Substring($trStart, $trEnd - $trStart)
$stripped = [regex]::Replace($row, '<[^>]+>', ' ')
# collapse whitespace
$stripped = [regex]::Replace($stripped, '\s+', ' ').Trim()
Write-Host "=== Table row containing MAR5 ==="
Write-Host $stripped
Write-Host ""

# Also show the 2 rows before and after for context
$prevTr = $xml.LastIndexOf('<w:tr ', $trStart - 1)
$prevRow = $xml.Substring($prevTr, $trStart - $prevTr)
$prevStripped = [regex]::Replace($prevRow, '<[^>]+>', ' ')
$prevStripped = [regex]::Replace($prevStripped, '\s+', ' ').Trim()
Write-Host "=== Previous row ==="
Write-Host $prevStripped

$nextTrStart = $trEnd
$nextTrEnd = $xml.IndexOf('</w:tr>', $nextTrStart) + 7
$nextRow = $xml.Substring($nextTrStart, $nextTrEnd - $nextTrStart)
$nextStripped = [regex]::Replace($nextRow, '<[^>]+>', ' ')
$nextStripped = [regex]::Replace($nextStripped, '\s+', ' ').Trim()
Write-Host "=== Next row ==="
Write-Host $nextStripped
