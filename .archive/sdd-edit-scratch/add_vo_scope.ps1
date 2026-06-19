Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcFile = 'C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx'

# Read
$zip = [System.IO.Compression.ZipFile]::OpenRead($srcFile)
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

Write-Host "XML length: $($xml.Length)"

# Anchor: end of the ins(903) paragraph (paraId 2E86686E)
$anchor = '<w:p w14:paraId="23ED9A42"'
$idx = $xml.IndexOf($anchor)
Write-Host "Anchor (empty para 23ED9A42) found at: $idx"

if ($idx -lt 0) {
    Write-Host "ERROR: anchor not found"
    exit 1
}

# New paragraph: explicit VO scope exclusion, inserted as tracked change before the empty para
$newPara = '<w:p w14:paraId="00000906" w14:textId="00000906" w:rsidR="009D54C6" w:rsidRDefault="009D54C6" w:rsidP="009D54C6">' +
           '<w:pPr><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr></w:pPr>' +
           '<w:ins w:id="906" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
           '<w:r><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
           '<w:t xml:space="preserve">Nicht im Leistungsumfang (Variation Order gem&#228;&#223; ND-036 Kap.&#160;6): ' +
           'Die folgenden Funktionen sind ausdr&#252;cklich NICHT Bestandteil des Standardangebots von Nomad und werden nur im Rahmen einer gesonderten Variation Order (VO) realisiert: ' +
           '(1)&#160;Aufbau eines gemeinsamen Netzwerks &#252;ber alle gekoppelten Fahrzeuge (Multi-Traction-Netzwerk); ' +
           '(2)&#160;Routing der Stadler-Dienste (CCTV, FIS, AFZ, Sprechstelle etc.) &#252;ber die Kupplungsverbindung; ' +
           '(3)&#160;Redundante CCU-Konfiguration und CCU-&#220;bernahme bei Ausfall; ' +
           '(4)&#160;Routing des Passagier-VLANs (PWLAN) &#252;ber die Kupplung; ' +
           '(5)&#160;Engineering Pages &#252;ber mehrere Fahrzeuge; ' +
           '(6)&#160;NMS-Integration f&#252;r Drittsysteme. ' +
           'Diese Punkte sind abh&#228;ngig von Eingaben, die Stadler bis 15.&#160;Juni&#160;2026 bereitstellt (IP-Schema, VLAN-Liste, QoS-Anforderungen).</w:t>' +
           '</w:r></w:ins>' +
           '</w:p>'

# Insert before the empty paragraph
$xmlNew = $xml.Substring(0, $idx) + $newPara + $xml.Substring($idx)

Write-Host "Old length: $($xml.Length), New length: $($xmlNew.Length)"
Write-Host "Delta: $($xmlNew.Length - $xml.Length) chars"

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
