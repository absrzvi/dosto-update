Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcFile = 'C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit.docx'
$dstFile = 'C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx'

# Copy to new file
Copy-Item $srcFile $dstFile -Force

# Read
$zip = [System.IO.Compression.ZipFile]::OpenRead($srcFile)
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

Write-Host "XML length: $($xml.Length)"

# Find the paragraph
$anchor = '3D242E5B'
$idx = $xml.IndexOf($anchor)
Write-Host "Anchor at: $idx"

$pstart = $xml.LastIndexOf('<w:p ', $idx)
$pend = $xml.IndexOf('</w:p>', $idx) + 6
Write-Host "Para: $pstart to $pend (len $($pend - $pstart))"

$old = $xml.Substring($pstart, $pend - $pstart)
Write-Host "--- OLD (first 200) ---"
Write-Host $old.Substring(0, [Math]::Min(200, $old.Length))
Write-Host "--- OLD (last 200) ---"
Write-Host $old.Substring([Math]::Max(0, $old.Length - 200))

# Save old for inspection
[System.IO.File]::WriteAllText('C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\old_para.txt', $old, [System.Text.Encoding]::UTF8)
Write-Host "Saved old_para.txt"

# Build the new (correct) paragraph
# The VO insert text (exact as found in the file)
$voText = 'Erweiterter Leistungsumfang (Variation Order) gem&#228;&#223; ND-036 Kap.&#160;6. Nomad liefert das gemeinsame Netzwerk &#252;ber gekoppelte Fahrzeuge sowie das Routing der definierten Dienste, sobald Stadler folgende Eingaben bereitstellt: IP-Schema und Port-Zuweisung der Drittsysteme, Liste der &#252;ber die Mehrfachtraktion zu transportierenden Stadler-VLANs, QoS-Anforderungen sowie erwartete Durchsatzzahlen der Drittsysteme (CCTV, FIS etc.). Zieldatum: 15.&#160;Juni&#160;2026.'

$new = '<w:p w14:paraId="3D242E5B" w14:textId="36DEC313" w:rsidR="009D54C6" w:rsidRPr="009D54C6" w:rsidRDefault="009D54C6" w:rsidP="009D54C6">' +
       '<w:pPr><w:spacing w:before="120" w:after="120"/><w:ind w:left="57"/>' +
       '<w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr></w:pPr>' +
       '<w:del w:id="904" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
       '<w:r><w:rPr><w:lang w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
       '<w:delText>Muss von Stadler definiert werden und in deren Dokumentation beschrieben werden.</w:delText>' +
       '</w:r></w:del>' +
       '<w:ins w:id="905" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
       '<w:r><w:rPr><w:lang w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
       '<w:t xml:space="preserve">' + $voText + '</w:t>' +
       '</w:r></w:ins>' +
       '</w:p>'

Write-Host "Old len: $($old.Length), New len: $($new.Length)"

$xmlNew = $xml.Replace($old, $new)

if ($xmlNew -eq $xml) {
    Write-Host "ERROR: Replace had no effect!"
    exit 1
} else {
    Write-Host "Replace succeeded! Delta: $($xmlNew.Length - $xml.Length) chars"
}

# Write back to fixed docx
$zipDst = [System.IO.Compression.ZipFile]::Open($dstFile, [System.IO.Compression.ZipArchiveMode]::Update)
$entryDst = $zipDst.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$stream = $entryDst.Open()
$stream.SetLength(0)
$writer = [System.IO.StreamWriter]::new($stream, [System.Text.Encoding]::UTF8)
$writer.Write($xmlNew)
$writer.Flush()
$stream.Close()
$zipDst.Dispose()

Write-Host "Done! Written to $dstFile"
