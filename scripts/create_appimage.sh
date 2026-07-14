#!/bin/bash
#
# create_appimage.sh
#
# Automated script to create an AppImage from a PyInstaller build for DICOM Viewer V3
#
# This script:
# 1. Downloads AppImageTool if not present
# 2. Creates the AppDir structure
# 3. Copies the PyInstaller build
# 4. Creates the desktop entry file
# 5. Copies the application icon
# 6. Creates the AppRun script
# 7. Builds the AppImage
#
# Usage:
#   ./scripts/create_appimage.sh [version]
#
# Arguments:
#   version: Optional version string (e.g., "3.0.0"). If not provided, uses "latest"
#
# Requirements:
#   - PyInstaller build must exist in dist/DICOMViewerV3/
#   - Icon must exist at resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png
#   - Run from project root directory
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Configuration
APP_NAME="DICOMViewerV3"
VERSION="${1:-latest}"
ARCH="x86_64"
APPIMAGE_NAME="${APP_NAME}-${VERSION}-${ARCH}.AppImage"

# Directories
APPDIR="${PROJECT_ROOT}/AppDir"
DIST_DIR="${PROJECT_ROOT}/dist/${APP_NAME}"
ICON_SOURCE="${PROJECT_ROOT}/resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
APPIMAGETOOL="${PROJECT_ROOT}/appimagetool-x86_64.AppImage"

# Functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running from project root
if [ ! -f "DICOMViewerV3.spec" ]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

# Check if PyInstaller build exists
if [ ! -d "${DIST_DIR}" ]; then
    print_error "PyInstaller build not found at ${DIST_DIR}"
    print_info "Please run: pyinstaller DICOMViewerV3.spec"
    exit 1
fi

# Check if executable exists
if [ ! -f "${DIST_DIR}/${APP_NAME}" ]; then
    print_error "Executable not found at ${DIST_DIR}/${APP_NAME}"
    exit 1
fi

# Check if icon exists
if [ ! -f "${ICON_SOURCE}" ]; then
    print_error "Icon not found at ${ICON_SOURCE}"
    exit 1
fi

print_info "Starting AppImage creation for ${APP_NAME} version ${VERSION}"

# Step 1: Download AppImageTool if not present
print_info "Step 1: Checking for AppImageTool..."
if [ ! -f "${APPIMAGETOOL}" ]; then
    print_info "Downloading AppImageTool..."
    wget -q "${APPIMAGETOOL_URL}" -O "${APPIMAGETOOL}"
    chmod +x "${APPIMAGETOOL}"
    print_info "AppImageTool downloaded successfully"
else
    print_info "AppImageTool already present"
fi

# Step 2: Clean up old AppDir if it exists
if [ -d "${APPDIR}" ]; then
    print_warn "Removing existing AppDir..."
    rm -rf "${APPDIR}"
fi

# Step 3: Create AppDir structure
print_info "Step 2: Creating AppDir structure..."
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/128x128/apps"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/512x512/apps"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/scalable/apps"

# Step 4: Copy PyInstaller build
print_info "Step 3: Copying PyInstaller build..."
cp -r "${DIST_DIR}"/* "${APPDIR}/usr/bin/"
chmod +x "${APPDIR}/usr/bin/${APP_NAME}"

# Verify executable is present
if [ ! -f "${APPDIR}/usr/bin/${APP_NAME}" ]; then
    print_error "Failed to copy executable"
    exit 1
fi

print_info "Build files copied successfully"

# Step 5: Create desktop entry
print_info "Step 4: Creating desktop entry file..."
cat > "${APPDIR}/usr/share/applications/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=DICOM Viewer V3
Comment=Medical imaging DICOM viewer application
Exec=${APP_NAME}
Icon=${APP_NAME}
Categories=Graphics;MedicalSoftware;Viewer;
Terminal=false
StartupNotify=true
MimeType=application/dicom;
EOF

print_info "Desktop entry created"

# Step 6: Copy icon
print_info "Step 5: Copying application icon..."
# Copy icon to multiple sizes for better desktop environment compatibility
cp "${ICON_SOURCE}" "${APPDIR}/usr/share/icons/hicolor/128x128/apps/${APP_NAME}.png"
cp "${ICON_SOURCE}" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"
cp "${ICON_SOURCE}" "${APPDIR}/usr/share/icons/hicolor/512x512/apps/${APP_NAME}.png"
# Also add to scalable directory (desktop environments can scale as needed)
cp "${ICON_SOURCE}" "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${APP_NAME}.png"

# Check if icon was copied
if [ ! -f "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png" ]; then
    print_error "Failed to copy icon"
    exit 1
fi

print_info "Icon copied successfully (multiple sizes)"

# Step 7: Create AppRun script
print_info "Step 6: Creating AppRun script..."
cat > "${APPDIR}/AppRun" << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/DICOMViewerV3" "$@"
EOF

chmod +x "${APPDIR}/AppRun"

print_info "AppRun script created"

# Step 8: Build AppImage
print_info "Step 7: Building AppImage..."
print_info "This may take a few minutes..."

# Remove old AppImage if it exists
if [ -f "${PROJECT_ROOT}/${APPIMAGE_NAME}" ]; then
    print_warn "Removing existing AppImage..."
    rm -f "${PROJECT_ROOT}/${APPIMAGE_NAME}"
fi

# Build the AppImage
"${APPIMAGETOOL}" "${APPDIR}" "${PROJECT_ROOT}/${APPIMAGE_NAME}"

# Check if AppImage was created
if [ ! -f "${PROJECT_ROOT}/${APPIMAGE_NAME}" ]; then
    print_error "Failed to create AppImage"
    exit 1
fi

# Make AppImage executable
chmod +x "${PROJECT_ROOT}/${APPIMAGE_NAME}"

# Get file size
FILE_SIZE=$(du -h "${PROJECT_ROOT}/${APPIMAGE_NAME}" | cut -f1)

print_info "AppImage created successfully!"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AppImage Creation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "File: ${APPIMAGE_NAME}"
echo "Size: ${FILE_SIZE}"
echo "Location: ${PROJECT_ROOT}/${APPIMAGE_NAME}"
echo ""
echo "To test the AppImage:"
echo "  ./${APPIMAGE_NAME}"
echo ""
echo "To clean up the AppDir (optional):"
echo "  rm -rf ${APPDIR}"
echo ""

# Optional: Clean up AppDir
read -p "Remove AppDir? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "${APPDIR}"
    print_info "AppDir removed"
fi

print_info "Done!"
