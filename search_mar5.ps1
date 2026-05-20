Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

$terms = @('mar5', 'MAR5', 'Mar5', 'mar-5', 'MAR-5', 'migration', 'Migration')
foreach ($term in $terms) {
    $idx = $xml.IndexOf($term)
    if ($idx -ge 0) {
        $ctx = [regex]::Replace($xml.Substring([Math]::Max(0,$idx-100), 300), '<[^>]+>', '')
        Write-Host "FOUND '$term' at $idx :"
        Write-Host $ctx
        Write-Host "---"
    } else {
        Write-Host "NOT FOUND: $term"
    }
}
