Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcFile = 'C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx'

$zip = [System.IO.Compression.ZipFile]::OpenRead($srcFile)
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

Write-Host "XML length: $($xml.Length)"

# Insert before the empty paragraph 23ED9A42 (which precedes the VO scope para 00000906)
# i.e. insert two new paragraphs before 23ED9A42:
#   Para 1: topology heading-style intro sentence
#   Para 2: detailed explanation
$anchor = '<w:p w14:paraId="23ED9A42"'
$idx = $xml.IndexOf($anchor)
Write-Host "Anchor found at: $idx"

if ($idx -lt 0) {
    Write-Host "ERROR: anchor not found"
    exit 1
}

# Two paragraphs:
# 907 = topology overview sentence
# 908 = detailed RSTP / port-cost explanation
$newParas = '<w:p w14:paraId="00000907" w14:textId="00000907" w:rsidR="009D54C6" w:rsidRDefault="009D54C6" w:rsidP="009D54C6">' +
            '<w:pPr><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr></w:pPr>' +
            '<w:ins w:id="907" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
            '<w:r><w:rPr><w:b/><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
            '<w:t>Netzwerktopologie im Mehrfachtraktionsverband</w:t>' +
            '</w:r></w:ins>' +
            '</w:p>' +
            '<w:p w14:paraId="00000908" w14:textId="00000908" w:rsidR="009D54C6" w:rsidRDefault="009D54C6" w:rsidP="009D54C6">' +
            '<w:pPr><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr></w:pPr>' +
            '<w:ins w:id="908" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
            '<w:r><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
            '<w:t xml:space="preserve">Bei gekoppelten Fahrzeugen entsteht eine Reihentopologie (U-Topologie / Daisy-Chain): Die internen Switch-Ringe der einzelnen Fahrzeuge werden &#252;ber den Frontkupplungsport (e0-2) der Endwagen-Switches (A1 bzw. A3) miteinander verbunden. Es ergibt sich folgende Struktur:</w:t>' +
            '</w:r></w:ins>' +
            '</w:p>' +
            '<w:p w14:paraId="00000909" w14:textId="00000909" w:rsidR="009D54C6" w:rsidRDefault="009D54C6" w:rsidP="009D54C6">' +
            '<w:pPr><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr></w:pPr>' +
            '<w:ins w:id="909" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
            '<w:r><w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
            '<w:t xml:space="preserve">[Fahrzeug A: interner Ring] &#8213; e0-2 &#8213; [Fahrzeug B: interner Ring] &#8213; e0-2 &#8213; [Fahrzeug C: interner Ring]</w:t>' +
            '</w:r></w:ins>' +
            '</w:p>' +
            '<w:p w14:paraId="0000090A" w14:textId="0000090A" w:rsidR="009D54C6" w:rsidRDefault="009D54C6" w:rsidP="009D54C6">' +
            '<w:pPr><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr></w:pPr>' +
            '<w:ins w:id="910" w:author="Claude" w:date="2026-05-15T00:00:00Z">' +
            '<w:r><w:rPr><w:lang w:val="de-DE" w:eastAsia="ja-JP" w:bidi="th-TH"/></w:rPr>' +
            '<w:t xml:space="preserve">Es handelt sich ausdr&#252;cklich um keine Ring-Topologie zwischen den Fahrzeugen. RSTP l&#228;uft transparent &#252;ber die OctiConn-Kupplungsverbindung. Die Kupplungsports (e0-2) erhalten bewusst sehr hohe RSTP-Pfadkosten (A3: train_id &#215; 2&#160;000&#160;000; A1: train_id &#215; 1&#160;000&#160;000), sodass der interne Fahrzeugring als bevorzugter Pfad gew&#228;hlt wird. Der Kupplungspfad wird von RSTP nur dann aktiviert, wenn ein interner Link im Fahrzeug ausf&#228;llt &#8212; er dient als Schutzpfad, nicht als Normalbetriebspfad. Im Normalbetrieb wird der Kupplungsport von RSTP nicht blockiert (er ist der einzige Pfad zwischen den Fahrzeugen), verbleibt jedoch aufgrund der hohen Pfadkosten ohne Einfluss auf die Root-Port-Wahl innerhalb der Fahrzeuge.</w:t>' +
            '</w:r></w:ins>' +
            '</w:p>'

$xmlNew = $xml.Substring(0, $idx) + $newParas + $xml.Substring($idx)

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
