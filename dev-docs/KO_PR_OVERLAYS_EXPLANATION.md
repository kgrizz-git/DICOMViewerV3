# KO Objects, PR Objects, and Embedded Overlays in DICOM

This document explains the three different ways annotations and overlays can be stored in DICOM: Key Object Selection Documents (KO objects), Presentation State files (PR objects), and embedded overlays.

## Overview

DICOM provides multiple mechanisms for storing annotations, measurements, and graphic overlays:

1. **Embedded Overlays**: Stored directly within the image file itself
2. **PR Objects (Presentation State Files)**: Separate DICOM files that reference images and contain graphic annotations and display settings
3. **KO Objects (Key Object Selection Documents)**: Separate DICOM files that reference images and contain measurements/text annotations

All three types are automatically processed by the DICOM Viewer when displaying images.

---

## KO Objects (Key Object Selection Documents)

**KO objects** are separate DICOM files (not image files) that contain references to selected images and annotations/measurements.

### Characteristics

- **SOP Class UID**: `1.2.840.10008.5.1.4.1.1.88.59` (Key Object Selection Document Storage)
- **Purpose**: Store references to "key" images selected from a study, along with annotations and measurements
- **Storage**: Separate DICOM files (metadata files, not image files)
- **Structure**: 
  - References to images via `ContentSequence` and `ReferencedSOPSequence`
  - Annotations and measurements stored in `ContentSequence`
  - Can contain text annotations, measurements with units, and other structured data

### How They Work

1. A Key Object file references one or more images through `ContentSequence`
2. Each referenced image is identified by its SOP Instance UID
3. Annotations are stored in the `ContentSequence` with:
   - Concept names (type of annotation)
   - Text values
   - Numeric measurements with units
   - References to the images they apply to

### Example Use Cases

- Radiologists selecting "key images" from a study
- Storing measurements (e.g., tumor size, distance measurements)
- Adding text annotations to specific images
- Creating a summary document of important findings

---

## PR Objects (Presentation State Files)

**PR objects** are separate DICOM files that store graphic annotations, display settings, and references to images.

### Characteristics

- **SOP Class UIDs**:
  - `1.2.840.10008.5.1.4.1.1.11.1` (Grayscale Softcopy Presentation State Storage)
  - `1.2.840.10008.5.1.4.1.1.11.2` (Color Softcopy Presentation State Storage)
- **Purpose**: Store how images should be displayed (window/level, zoom, pan, rotation) and graphic annotations
- **Storage**: Separate DICOM files
- **Structure**:
  - Graphic annotations in `GraphicAnnotationSequence` (text, lines, circles, ellipses, points)
  - Display settings (window/level, zoom, pan, rotation)
  - References to images at image-level (`ReferencedImageSequence`) or series-level (`ReferencedSeriesSequence`)

### Graphic Annotation Types

PR objects can contain various graphic annotation types:

- **TEXT**: Text annotations with positioning
- **POLYLINE**: Lines and polylines
- **CIRCLE**: Circular annotations
- **ELLIPSE**: Elliptical annotations
- **POINT**: Point markers

Each annotation includes:
- Coordinates (in PIXEL, DISPLAY, or NORMALIZED units)
- Color information
- Layer assignment
- Text content (for TEXT annotations)

### Display Settings

PR objects can also store display settings:

- **Window/Level**: Window center and width values
- **Zoom**: Zoom factor or pixel spacing
- **Pan**: Displayed area top-left corner
- **Rotation**: Image rotation angle

### How They Work

1. A Presentation State file references images either:
   - At the image level (specific SOP Instance UIDs)
   - At the series level (Series Instance UIDs)
2. Graphic annotations are stored in `GraphicAnnotationSequence`
3. Display settings are stored in various tags (WindowCenter, WindowWidth, DisplayedAreaSelectionSequence, etc.)
4. When an image is displayed, the viewer checks if any Presentation States reference it and applies the annotations and settings

### Example Use Cases

- Storing annotations made by a radiologist (arrows, circles, text)
- Preserving display settings (window/level) for consistent viewing
- Storing measurement graphics (distance lines, ROI markers)
- Maintaining annotation layers for different purposes

---

## Embedded Overlays

**Embedded overlays** are stored directly within the image file itself, not in separate files.

### Characteristics

- **Storage**: Part of the image DICOM file
- **Purpose**: Store bitmap overlays or graphic annotations directly with the image
- **Structure**: 
  - OverlayData tags: `(0x60xx, 0x3000)` where `xx` can be `00-1F` (overlay groups 0-31)
  - `GraphicAnnotationSequence` can also be embedded in image files

### OverlayData Tags

Each overlay group (0x6000-0x601F) can contain:

- **OverlayData** (0x60xx, 0x3000): Bitmap data (1-bit per pixel)
- **OverlayRows** (0x60xx, 0x0010): Number of rows in the overlay
- **OverlayColumns** (0x60xx, 0x0011): Number of columns in the overlay
- **OverlayOrigin** (0x60xx, 0x0050): Origin coordinates [row, column] (1-based indexing)
- **OverlayType** (0x60xx, 0x0040): Type of overlay:
  - `G` = Graphic overlay
  - `R` = ROI (Region of Interest) overlay

### Embedded GraphicAnnotationSequence

Image files can also contain `GraphicAnnotationSequence` directly, similar to Presentation State files. This allows graphic annotations to be stored with the image without requiring a separate Presentation State file.

### How They Work

1. Overlay data is stored as bitmap data in OverlayData tags
2. The overlay bitmap is converted to graphics primitives for display
3. OverlayOrigin specifies where the overlay should be positioned on the image
4. Multiple overlays can be stored (up to 32 overlay groups)

### Example Use Cases

- Storing annotations created by the imaging device
- Including ROI markers directly in the image
- Embedding measurement graphics with the image
- Storing overlays that should always be displayed with the image

---

## Relationship and Processing

### How They Work Together

All three annotation types can coexist:

1. **Embedded overlays** are always part of the image file and are automatically present when the image is loaded
2. **PR objects** are separate files that reference images - the viewer matches them to images by SOP Instance UID or Series Instance UID
3. **KO objects** are separate files that reference images - the viewer matches them to images by SOP Instance UID

### Processing Order

When displaying an image, the viewer processes annotations in this order:

1. **Embedded annotations** (from the image file itself)
   - OverlayData tags
   - GraphicAnnotationSequence in the image file
2. **Presentation State annotations** (from separate PR files)
   - Matched by image UID or series UID
   - Graphic annotations from GraphicAnnotationSequence
3. **Key Object annotations** (from separate KO files)
   - Matched by image UID
   - Converted from ContentSequence format to graphic format

### Advantages of Each Approach

| Type | Advantages |
|------|------------|
| **Embedded Overlays** | • Always available with the image<br>• No separate files to manage<br>• Guaranteed to be present |
| **PR Objects** | • Can reference multiple images<br>• Can store display settings<br>• Can be shared across multiple images<br>• Supports series-level references |
| **KO Objects** | • Structured measurement data<br>• Can reference multiple images<br>• Good for key image selection<br>• Structured annotations with units |

### When to Use Each

- **Embedded Overlays**: When annotations should always be part of the image (e.g., device-generated annotations, permanent markers)
- **PR Objects**: When annotations are created by users and may need to be edited, shared, or applied to multiple images
- **KO Objects**: When storing structured measurements and key image selections that need to be searchable and structured

---

## Implementation in DICOM Viewer

The viewer automatically:

1. **Detects** all three types during file organization
2. **Matches** PR and KO objects to images by UID
3. **Parses** annotations from all sources
4. **Displays** all annotations together on the image

The annotation manager (`AnnotationManager`) coordinates this process:

- Checks for embedded annotations in each image
- Looks up Presentation States for the study
- Looks up Key Objects for the study
- Combines all annotations for display

All annotations are converted to a common format for rendering, regardless of their source.

---

## References

- DICOM Standard Part 3: Information Object Definitions
- DICOM Standard Part 10: Media Storage and File Format
- Key Object Selection Document: PS3.3 C.17.6.1
- Grayscale Softcopy Presentation State: PS3.3 A.33.1
- Overlay Plane Module: PS3.3 C.9.2

