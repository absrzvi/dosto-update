Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

# 1. Check Internetzugang section - is "Abstimmung ausstehend!" still there?
$abstimmung = $xml.Contains('Abstimmung ausstehend')
Write-Host "Abstimmung ausstehend still present: $abstimmung"

# 2. Extract the Internetzugang paragraph text
$idx = $xml.IndexOf('Internetzugang</w:t>')
$pstart = $xml.LastIndexOf('<w:p ', $idx)
$pend = $xml.IndexOf('</w:p>', $idx) + 6
# Get next 2 paragraphs after subheading
$afterHeading = $xml.Substring($pend, [Math]::Min(2000, $xml.Length - $pend))
[System.IO.File]::WriteAllText('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\internetzugang_body.txt', $afterHeading, [System.Text.Encoding]::UTF8)
Write-Host "Written internetzugang_body.txt"

# 3. Check pre-DDR caveat - search for DDR or Detailed Design
$ddrPresent = $xml.Contains('Detailed Design Review') -or $xml.Contains('DDR')
Write-Host "DDR/pre-DDR caveat present: $ddrPresent"

# 4. Check for coupler 1Gbps constraint mention
$gbpsPresent = $xml.Contains('1 Gbps') -or $xml.Contains('1Gbps') -or $xml.Contains('1G') -or $xml.Contains('Bandbreite')
Write-Host "1Gbps/bandwidth mention present: $gbpsPresent"

# 5. Check document version/revision info - look for version field
$idx2 = $xml.IndexOf('v2.1')
Write-Host "v2.1 found: $($idx2 -ge 0)"

# 6. Check if ND-036 reference is in the doc
$nd036 = $xml.Contains('ND-036') -or $xml.Contains('ND-BID')
Write-Host "ND-036 reference present: $nd036"

# 7. Check for CCU election mechanism
$ccu = $xml.Contains('CCU') -and ($xml.Contains('Redundanz') -or $xml.Contains('redundan') -or $xml.Contains('election') -or $xml.Contains('Wahl'))
Write-Host "CCU redundancy/election text present: $ccu"

# 8. Show the VO scope paragraph we just added
$idx3 = $xml.IndexOf('00000906')
$pstart3 = $xml.LastIndexOf('<w:p ', $idx3)
$pend3 = $xml.IndexOf('</w:p>', $pstart3) + 6
$voPara = $xml.Substring($pstart3, $pend3 - $pstart3)
# Strip XML tags for readability
$voText = [regex]::Replace($voPara, '<[^>]+>', '')
Write-Host "`n=== VO scope para text ==="
Write-Host $voText
