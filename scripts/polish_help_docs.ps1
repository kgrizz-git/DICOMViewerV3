$quick = 'resources/help/quick_start_guide.html'
$fusion = 'resources/help/fusion_technical_doc.html'
$utf8 = [System.Text.UTF8Encoding]::new($false)

$content = [System.IO.File]::ReadAllText($quick)
$content = $content.Replace(
@'<li><a href="#measurements">Measurements</a></li>
                <li><a href="#rois">ROIs (Regions of Interest)</a></li>'@,
@'<li><a href="#measurements">Measurements</a></li>
                <li><a href="#text-arrow-annotations">Text and Arrow Annotations</a></li>
                <li><a href="#rois">ROIs (Regions of Interest)</a></li>'@
)
$content = $content.Replace(' ? ', ' &rarr; ')
$content = $content.Replace('<code>?</code> (Up) for next slice, <code>?</code> (Down) for previous slice', '<code>&uarr;</code> (Up) for next slice, <code>&darr;</code> (Down) for previous slice')
$content = $content.Replace('<code>?</code> (Left) for previous series, <code>?</code> (Right) for next series', '<code>&larr;</code> (Left) for previous series, <code>&rarr;</code> (Right) for next series')
$content = $content.Replace('<strong><code>?</code> / <code>?</code>:</strong> Navigate slices (Up = next, Down = previous)', '<strong><code>&uarr;</code> / <code>&darr;</code>:</strong> Navigate slices (Up = next, Down = previous)')
$content = $content.Replace('<strong><code>?</code> / <code>?</code>:</strong> Navigate series (Left = previous, Right = next)', '<strong><code>&larr;</code> / <code>&rarr;</code>:</strong> Navigate series (Left = previous, Right = next)')
$content = $content.Replace('Export ROI Statistics�', 'Export ROI Statistics...')
$content = $content.Replace('Export Tag Presets�', 'Export Tag Presets...')
$content = $content.Replace('Import Tag Presets�', 'Import Tag Presets...')
$content = $content.Replace('Export�', 'Export...')
$content = $content.Replace('Import�', 'Import...')
$content = $content.Replace('1.5�, 2�, 4�', '1.5&times;, 2&times;, 4&times;')
$content = [regex]::Replace(
    $content,
    '(?s)\s*<h2 id="image-fusion">Image Fusion</h2>\s*<p><strong>Note:</strong> Image fusion is a feature that has been added and is continuing to be refined\..*?(?=<h2 id="window-level">)',
    "`r`n"
)
[System.IO.File]::WriteAllText($quick, $content, $utf8)

$content = [System.IO.File]::ReadAllText($fusion)
$content = $content.Replace(' ? ', ' &rarr; ')
$content = $content.Replace("`r`n                                                      ?`r`n", "`r`n                                                      &darr;`r`n")
$content = $content.Replace('<strong>Opacity (a)</strong>', '<strong>Opacity (&alpha;)</strong>')
$content = $content.Replace('fused = base � (1 - a�mask) + overlay � (a�mask)', 'fused = base &times; (1 - &alpha;&times;mask) + overlay &times; (&alpha;&times;mask)')
$content = $content.Replace('overlay = array1 � (1 - weight) + array2 � weight', 'overlay = array1 &times; (1 - weight) + array2 &times; weight')
$content = $content.Replace('Alpha blend: <code>fused = base � (1 - a�mask) + overlay � (a�mask)</code>', 'Alpha blend: <code>fused = base &times; (1 - &alpha;&times;mask) + overlay &times; (&alpha;&times;mask)</code>')
$content = $content.Replace('��', '&asymp;&plusmn;')
$content = $content.Replace('�0 voxels in Z', '&asymp;0 voxels in Z')
$content = $content.Replace('�0.5 pixels in x/y (rounding)', '&plusmn;0.5 pixels in x/y (rounding)')
$content = $content.Replace('�0.1-0.5 mm', '&plusmn;0.1-0.5 mm')
$content = $content.Replace('�0.1-0.5 pixels', '&plusmn;0.1-0.5 pixels')
$content = $content.Replace('�1-2 mm', '&plusmn;1-2 mm')
$content = $content.Replace('�0.5 mm precision', '&plusmn;0.5 mm precision')
$content = $content.Replace('�0.25 mm precision', '&plusmn;0.25 mm precision')
$content = $content.Replace('0.5�1.0', '0.5-1.0')
$content = $content.Replace('0.5�1.5', '0.5-1.5')
$content = $content.Replace('1.0�2.5', '1.0-2.5')
$content = $content.Replace('0.5�0.9', '0.5-0.9')
$content = $content.Replace('0.3�0.4', '0.3-0.4')
$content = $content.Replace('0.5�0.7', '0.5-0.7')
$content = $content.Replace('0.1�0.5', '0.1-0.5')
$content = $content.Replace('0.6�1.0', '0.6-1.0')
$content = $content.Replace('1.0�1.5', '1.0-1.5')
$content = $content.Replace('10�30%', '10-30%')
$content = $content.Replace('mm�cm', 'mm to cm')
$content = $content.Replace('2-4� single slice size', '2-4&times; single slice size')
$content = $content.Replace('2� volume size', '2&times; volume size')
$content = $content.Replace('0.1�', '0.1&deg;')
[System.IO.File]::WriteAllText($fusion, $content, $utf8)

Write-Output 'help docs polished'
