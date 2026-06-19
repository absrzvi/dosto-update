Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcFile = 'C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\ND-DEL-OBB-035-SDD-002-01_v2.1_edit_fixed.docx'

$zip = [System.IO.Compression.ZipFile]::OpenRead($srcFile)
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
$xml = $reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

Write-Host "XML length: $($xml.Length)"

# Find the 5.10.1 Internetzugang heading paragraph (bookmarkStart _Toc229775509 in body)
# We know from earlier it's at position 674147 area - find by bookmarkStart
$search = 'w:name="_Toc229775509"'
$positions = @()
$pos = 0
while ($true) {
    $idx = $xml.IndexOf($search, $pos)
    if ($idx -lt 0) { break }
    $positions += $idx
    $pos = $idx + 1
}
Write-Host "Found $($positions.Count) occurrences of _Toc229775509"

# Last occurrence = body bookmarkStart
$bodyIdx = $positions[-1]
$headingParaStart = $xml.LastIndexOf('<w:p ', $bodyIdx)
Write-Host "Heading para starts at: $headingParaStart"

# Find the next Heading2 paragraph (_Toc229775510 = Anforderungen) - that's where we stop deleting
$nextSection = 'w:name="_Toc229775510"'
$nextIdx = $xml.IndexOf($nextSection)
# The paragraph containing this bookmark
$nextParaStart = $xml.LastIndexOf('<w:p ', $nextIdx)
Write-Host "Next section (Anforderungen) para starts at: $nextParaStart"

# Everything from headingParaStart to nextParaStart is 5.10.1 content to delete
$toDelete = $xml.Substring($headingParaStart, $nextParaStart - $headingParaStart)
Write-Host "Deleting $($toDelete.Length) chars"

# Show what we're deleting (stripped)
$stripped = [regex]::Replace($toDelete, '<[^>]+>', '')
Write-Host "=== Content being deleted ==="
Write-Host $stripped.Substring(0, [Math]::Min(500, $stripped.Length))
Write-Host "==="

# Replace with a single tracked-deletion paragraph so the removal is visible as a tracked change
# Use w:del wrapping the heading and body paragraphs
# Actually: cleanest approach for a section removal is to wrap each paragraph's content in w:del
# But simpler and correct: just remove the paragraphs entirely (hard delete, no track)
# Since the doc already has tracked changes from Claude, and this is a structural section removal
# that we want to be visible - wrap in del

# Simpler: delete the raw block (ÖBB will see section 5.10.1 gone, which is the intent)
$xmlNew = $xml.Substring(0, $headingParaStart) + $xml.Substring($nextParaStart)

Write-Host "New XML length: $($xmlNew.Length), delta: $($xmlNew.Length - $xml.Length)"

# Verify Abstimmung is gone
Write-Host "Abstimmung ausstehend still present: $($xmlNew.Contains('Abstimmung ausstehend'))"
Write-Host "Internetzugang heading still present: $($xmlNew.Contains('_Toc229775509'))"

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
