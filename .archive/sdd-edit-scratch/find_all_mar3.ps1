Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

# Find every occurrence of MAR3 (case variations) and mar3
$terms = @('MAR3', 'mar3')
$allHits = @()
foreach ($term in $terms) {
    $pos = 0
    while ($true) {
        $idx = $xml.IndexOf($term, $pos)
        if ($idx -lt 0) { break }
        $allHits += [PSCustomObject]@{ Term=$term; Idx=$idx }
        $pos = $idx + 1
    }
}
$allHits = $allHits | Sort-Object Idx
Write-Host "Total MAR3/mar3 occurrences: $($allHits.Count)"
Write-Host ""

foreach ($hit in $allHits) {
    # Get surrounding text (strip tags)
    $start = [Math]::Max(0, $hit.Idx - 150)
    $ctx = $xml.Substring($start, [Math]::Min(350, $xml.Length - $start))
    $stripped = [regex]::Replace($ctx, '<[^>]+>', '')
    $stripped = [regex]::Replace($stripped, '\s+', ' ').Trim()
    Write-Host "[$($hit.Term) @ $($hit.Idx)] $stripped"
    Write-Host "---"
}
