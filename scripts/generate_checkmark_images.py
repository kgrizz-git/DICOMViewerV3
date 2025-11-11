"""
Generate Checkmark PNG Images for Checkbox Styling

This script generates two 16x16 PNG checkmark images:
- checkbox_checkmark_white.png (for dark theme)
- checkbox_checkmark_black.png (for light theme)

Both images have transparent backgrounds and use the same checkmark path
as the original SVG: M 3,8 L 7,12 L 13,4
"""

from PIL import Image, ImageDraw
from pathlib import Path

# Get project root (parent of scripts directory)
project_root = Path(__file__).parent.parent
resources_dir = project_root / "resources" / "images"
resources_dir.mkdir(parents=True, exist_ok=True)

# Image dimensions
size = 16
stroke_width = 2

# Checkmark path coordinates (same as SVG)
# M 3,8 L 7,12 L 13,4
checkmark_points = [
    (3, 8),   # Start point
    (7, 12),  # Middle point
    (13, 4)   # End point
]

def create_checkmark_image(color: tuple, filename: str):
    """Create a checkmark image with the specified color."""
    # Create transparent image
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw checkmark as lines
    # Line 1: (3,8) to (7,12)
    draw.line([checkmark_points[0], checkmark_points[1]], 
              fill=color, width=stroke_width, joint='round')
    
    # Line 2: (7,12) to (13,4)
    draw.line([checkmark_points[1], checkmark_points[2]], 
              fill=color, width=stroke_width, joint='round')
    
    # Save image
    output_path = resources_dir / filename
    img.save(output_path, 'PNG')
    print(f"Created: {output_path}")

# Generate white checkmark for dark theme
create_checkmark_image((255, 255, 255, 255), "checkbox_checkmark_white.png")

# Generate black checkmark for light theme
create_checkmark_image((0, 0, 0, 255), "checkbox_checkmark_black.png")

print("Checkmark images generated successfully!")

