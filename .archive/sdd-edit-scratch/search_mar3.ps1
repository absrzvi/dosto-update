Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

foreach ($term in @('MAR3', 'mar3', 'Mar3', 'MAR 3', 'mar 3')) {
    $pos = 0
    $count = 0
    while ($true) {
        $idx = $xml.IndexOf($term, $pos)
        if ($idx -lt 0) { break }
        $count++
        # Find enclosing row
        $trStart = $xml.LastIndexOf('<w:tr ', $idx)
        $trEnd = $xml.IndexOf('</w:tr>', $idx) + 7
        $row = $xml.Substring($trStart, $trEnd - $trStart)
        $stripped = [regex]::Replace($row, '<[^>]+>', ' ')
        $stripped = [regex]::Replace($stripped, '\s+', ' ').Trim()
        Write-Host "FOUND '$term' occurrence $count at $idx :"
        Write-Host $stripped
        Write-Host "---"
        $pos = $idx + 1
    }
    if ($count -eq 0) { Write-Host "NOT FOUND: $term" }
}
