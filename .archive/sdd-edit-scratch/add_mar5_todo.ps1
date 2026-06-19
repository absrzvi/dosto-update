Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcFile = 'C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx'

$zip = [System.IO.Compression.ZipFile]::OpenRead($srcFile)
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

# Find the "Nomad MAR-Server (mar3be06 – mar3be09)" cell — first occurrence
$anchor = 'Nomad MAR-Server (mar3be06'
$idx = $xml.IndexOf($anchor)
Write-Host "MAR-Server label found at: $idx"

# Find the paragraph containing it
$pstart = $xml.LastIndexOf('<w:p ', $idx)
$pend = $xml.IndexOf('</w:p>', $idx) + 6
$oldPara = $xml.Substring($pstart, $pend - $pstart)
Write-Host "Para length: $($oldPara.Length)"

# Replace the label text with a tracked del+ins marking it as needing update
# Old text run containing the label
$oldText = 'Nomad MAR-Server (mar3be06 &#x2013; mar3be09)'
$oldTextAlt = 'Nomad MAR-Server (mar3be06 ' + [char]0x2013 + ' mar3be09)'

# Check which form is in the file
if ($xml.Contains($oldText)) {
    Write-Host "Found entity-encoded form"
    $foundText = $oldText
} elseif ($xml.Contains($oldTextAlt)) {
    Write-Host "Found unicode form"
    $foundText = $oldTextAlt
} else {
    # Try extracting exact string
    $paraStripped = [regex]::Replace($oldPara, '<[^>]+>', '')
    Write-Host "Raw para text: $paraStripped"
    Write-Host "Could not find exact text form - will do paragraph-level replacement"
    $foundText = $null
}

# Strategy: insert a comment-style tracked insertion after the cell label paragraph
# Add a new paragraph in the same cell with the TODO note as a tracked ins
# Find end of the table cell </w:tc> after our paragraph
$tcEnd = $xml.IndexOf('</w:tc>', $pend)
Write-Host "Cell ends at: $tcEnd"

# Insert a TODO paragraph before </w:tc>
$todoNote = '<w:p w14:paraId="00000911" w14:textId="00000911" w:rsidR="009D54C6" w:rsidRDefault="009D54C6">' +
            '<w:pPr><w:rPr><w:color w:val="FF0000"/><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr></w:pPr>' +
            '<w:ins w:id="911" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
            '<w:r><w:rPr><w:b/><w:color w:val="FF0000"/><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
            '<w:t xml:space="preserve">TODO: MAR3-Hostnamen (mar3be06&#x2013;mar3be09) durch MAR5-Backend-Hostnamen ersetzen. MAR5-Hostnamen bei R&amp;D erfragen und hier aktualisieren.</w:t>' +
            '</w:r></w:ins>' +
            '</w:p>'

$xmlNew = $xml.Substring(0, $tcEnd) + $todoNote + $xml.Substring($tcEnd)
Write-Host "Delta: $($xmlNew.Length - $xml.Length)"

# Write back
$zipDst = [System.IO.Compression.ZipFile]::Open($srcFile, [System.IO.Compression.ZipArchiveMode]::Update)
$entryDst = $zipDst.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$stream = $entryDst.Open()
$stream.SetLength(0)
$writer = [System.IO.StreamWriter]::new($stream, [System.Text.Encoding]::UTF8)
$writer.Write($xmlNew)
$writer.Flush()
$stream.Close()
$zipDst.Dispose()

Write-Host "Done!"
