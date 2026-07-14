$files = @(
    'resources/help/quick_start_guide.html',
    'resources/help/fusion_technical_doc.html'
)

$cp1252 = [System.Text.Encoding]::GetEncoding(1252)
$utf8 = [System.Text.UTF8Encoding]::new($false)

foreach ($file in $files) {
    $content = [System.IO.File]::ReadAllText($file)
    $fixed = [System.Text.Encoding]::UTF8.GetString($cp1252.GetBytes($content))
    $fixed = $fixed.Replace(
        '<h2>Table of Contents</h2>',
        '<h2 id="table-of-contents">Table of Contents</h2>'
    )
    [System.IO.File]::WriteAllText($file, $fixed, $utf8)
}

Write-Output 'help html re-encoded'
