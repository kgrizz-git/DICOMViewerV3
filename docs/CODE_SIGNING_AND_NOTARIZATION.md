# Code Signing and Notarization Guide for macOS

This guide explains how to code sign and notarize your DICOM Viewer V3 macOS application for distribution outside the Mac App Store. Code signing and notarization are required to avoid Gatekeeper warnings and security issues on macOS 10.15 (Catalina) and later.

## Prerequisites

### 1. Apple Developer Account

- **Cost:** $99/year
- **Sign up:** https://developer.apple.com/programs/
- You need a valid Apple ID to enroll

### 2. App-Specific Password

You'll need an app-specific password for notarization (not your regular Apple ID password):

1. Go to https://appleid.apple.com/
2. Sign in with your Apple ID
3. Navigate to "App-Specific Passwords"
4. Click "Generate New Password"
5. Save this password securely (you'll need it for notarization)

**Note:** App-specific passwords are required for two-factor authentication accounts.

## Step 1: Get Your Developer ID Certificate

1. Go to https://developer.apple.com/account/resources/certificates/list
2. Click the "+" button to create a new certificate
3. Select **"Developer ID Application"** (for distribution outside the App Store)
4. Follow the prompts to create and download the certificate
5. Double-click the downloaded `.cer` file to install it in Keychain Access

**Important:** Choose "Developer ID Application" (not "Mac App Distribution" which is for App Store distribution).

## Step 2: Find Your Certificate Name and Team ID

Run this command to list your available certificates:

```bash
security find-identity -v -p codesigning
```

Look for a certificate like:
```
Developer ID Application: Your Name (TEAM_ID)
```

**Note down:**
- The full certificate name (e.g., "Developer ID Application: Your Name (TEAM_ID)")
- Your Team ID (the alphanumeric code in parentheses)

## Step 3: Code Sign the App

Sign your app bundle with the certificate:

```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAM_ID)" \
  --options runtime \
  --entitlements entitlements.plist \
  dist/DICOMViewerV3.app
```

**Note:** The `--deep` flag is deprecated but still works. For better practice, you might want to sign individual components first, but `--deep` is simpler for PyInstaller apps.

### Creating an Entitlements File

If you get an error about entitlements, create a minimal `entitlements.plist` file in your project root:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
```

Then use:
```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAM_ID)" \
  --options runtime \
  --entitlements entitlements.plist \
  dist/DICOMViewerV3.app
```

## Step 4: Verify Code Signing

Verify the app is properly signed:

```bash
codesign --verify --verbose dist/DICOMViewerV3.app
```

Check the signature details:
```bash
codesign -dv --verbose=4 dist/DICOMViewerV3.app
```

You should see information about the certificate and signature.

## Step 5: Create a ZIP for Notarization

Apple requires a ZIP file (not the .app directly) for notarization:

```bash
cd dist
ditto -c -k --keepParent DICOMViewerV3.app DICOMViewerV3.zip
cd ..
```

**Why ZIP?** Apple's notarization service requires a ZIP archive, not the app bundle directly.

## Step 6: Notarize the App

Submit for notarization using `xcrun notarytool` (the modern method):

```bash
xcrun notarytool submit dist/DICOMViewerV3.zip \
  --apple-id "your@email.com" \
  --team-id "YOUR_TEAM_ID" \
  --password "YOUR_APP_SPECIFIC_PASSWORD" \
  --wait
```

**Parameters:**
- `--apple-id`: Your Apple ID email address
- `--team-id`: Your Team ID (from Step 2)
- `--password`: App-specific password (from Prerequisites)
- `--wait`: Wait for notarization to complete (can take 5-30 minutes)

### Alternative: Submit Without Waiting

If you don't want to wait, submit without `--wait` and get a submission ID:

```bash
xcrun notarytool submit dist/DICOMViewerV3.zip \
  --apple-id "your@email.com" \
  --team-id "YOUR_TEAM_ID" \
  --password "YOUR_APP_SPECIFIC_PASSWORD"
```

Then check status later:
```bash
xcrun notarytool log SUBMISSION_ID \
  --apple-id "your@email.com" \
  --team-id "YOUR_TEAM_ID" \
  --password "YOUR_APP_SPECIFIC_PASSWORD"
```

**Note:** Notarization typically takes 5-30 minutes. The `--wait` flag will poll until completion.

## Step 7: Staple the Notarization Ticket

After successful notarization, staple the ticket to your app:

```bash
xcrun stapler staple dist/DICOMViewerV3.app
```

**Why staple?** Stapling attaches the notarization ticket directly to the app, so it works even when offline.

## Step 8: Verify Notarization

Verify the staple was successful:

```bash
xcrun stapler validate dist/DICOMViewerV3.app
```

You should see: **"The validate action worked!"**

## Step 9: Final Verification

Test that everything works with Gatekeeper:

```bash
spctl --assess --verbose --type execute dist/DICOMViewerV3.app
```

This should return: **"dist/DICOMViewerV3.app: accepted"**

## Complete Automation Script

Here's a complete script you can save and run (replace the placeholders):

```bash
#!/bin/bash

# Configuration - REPLACE THESE VALUES
CERT_NAME="Developer ID Application: Your Name (TEAM_ID)"
APPLE_ID="your@email.com"
TEAM_ID="YOUR_TEAM_ID"
APP_PASSWORD="YOUR_APP_SPECIFIC_PASSWORD"
APP_PATH="dist/DICOMViewerV3.app"
ZIP_PATH="dist/DICOMViewerV3.zip"
ENTITLEMENTS="entitlements.plist"

echo "========================================="
echo "Code Signing and Notarization Script"
echo "========================================="
echo ""

echo "Step 1: Code signing..."
codesign --deep --force --verify --verbose \
  --sign "$CERT_NAME" \
  --options runtime \
  --entitlements "$ENTITLEMENTS" \
  "$APP_PATH"

if [ $? -ne 0 ]; then
    echo "ERROR: Code signing failed!"
    exit 1
fi

echo ""
echo "Step 2: Verifying code signature..."
codesign --verify --verbose "$APP_PATH"

if [ $? -ne 0 ]; then
    echo "ERROR: Code signature verification failed!"
    exit 1
fi

echo ""
echo "Step 3: Creating ZIP for notarization..."
cd dist
rm -f DICOMViewerV3.zip
ditto -c -k --keepParent DICOMViewerV3.app DICOMViewerV3.zip
cd ..

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create ZIP!"
    exit 1
fi

echo ""
echo "Step 4: Submitting for notarization..."
echo "This may take 5-30 minutes..."
xcrun notarytool submit "$ZIP_PATH" \
  --apple-id "$APPLE_ID" \
  --team-id "$TEAM_ID" \
  --password "$APP_PASSWORD" \
  --wait

if [ $? -ne 0 ]; then
    echo "ERROR: Notarization failed!"
    echo "Check the logs with: xcrun notarytool log <submission-id> ..."
    exit 1
fi

echo ""
echo "Step 5: Stapling notarization ticket..."
xcrun stapler staple "$APP_PATH"

if [ $? -ne 0 ]; then
    echo "ERROR: Stapling failed!"
    exit 1
fi

echo ""
echo "Step 6: Verifying..."
xcrun stapler validate "$APP_PATH"
spctl --assess --verbose --type execute "$APP_PATH"

echo ""
echo "========================================="
echo "Done! Your app is code signed and notarized."
echo "========================================="
```

**To use the script:**

1. Save it as `sign_and_notarize.sh` in your project root
2. Make it executable: `chmod +x sign_and_notarize.sh`
3. Edit the configuration variables at the top
4. Run: `./sign_and_notarize.sh`

## Troubleshooting

### "no identity found" Error

**Problem:** `codesign` can't find your certificate.

**Solutions:**
- Make sure the certificate is installed in Keychain Access
- Use the exact certificate name from `security find-identity -v -p codesigning`
- Check that the certificate hasn't expired
- Make sure you're using "Developer ID Application" (not "Mac App Distribution")

### Notarization Fails

**Problem:** Notarization submission fails or is rejected.

**Solutions:**
- Check the notarization log:
  ```bash
  xcrun notarytool log SUBMISSION_ID \
    --apple-id "your@email.com" \
    --team-id "YOUR_TEAM_ID" \
    --password "YOUR_APP_SPECIFIC_PASSWORD"
  ```
- Common issues:
  - Unsigned binaries inside the app bundle
  - Missing entitlements
  - Hardened runtime issues
  - Invalid bundle identifier
- Make sure all components are properly code signed

### "resource fork, Finder information, or similar detritus" Warning

**Problem:** Warning about resource forks or metadata.

**Solution:** This is usually harmless, but you can clean it:
```bash
xattr -cr dist/DICOMViewerV3.app
```

Then re-sign and re-notarize.

### Gatekeeper Still Blocks the App

**Problem:** Even after notarization, Gatekeeper still shows warnings.

**Solutions:**
- Make sure you stapled the ticket: `xcrun stapler staple dist/DICOMViewerV3.app`
- Verify with: `spctl --assess --verbose --type execute dist/DICOMViewerV3.app`
- Check that notarization actually succeeded (check logs)
- Try clearing Gatekeeper cache: `sudo rm -rf /Library/Caches/com.apple.kext.caches`

### Certificate Expired

**Problem:** Certificate has expired.

**Solution:**
- Go to https://developer.apple.com/account/resources/certificates/list
- Create a new "Developer ID Application" certificate
- Download and install it
- Update your script with the new certificate name

### Wrong Certificate Type

**Problem:** Using "Mac App Distribution" instead of "Developer ID Application".

**Solution:**
- "Mac App Distribution" is for App Store distribution only
- Use "Developer ID Application" for direct distribution outside the App Store

## Important Notes

1. **Notarization Time:** Notarization can take 5-30 minutes. Be patient.

2. **Order Matters:** 
   - Code sign first
   - Then notarize
   - Then staple

3. **ZIP vs App:**
   - Submit the ZIP for notarization
   - Staple the .app bundle

4. **Security:**
   - Keep your app-specific password secure
   - Don't commit passwords to version control
   - Consider using environment variables for sensitive data

5. **Requirements:**
   - Notarization is required for macOS 10.15+ to avoid Gatekeeper warnings
   - Code signing is required before notarization
   - Hardened runtime is required (enabled with `--options runtime`)

6. **Testing:**
   - Test on a clean system without your development environment
   - Test on different macOS versions if possible
   - Verify Gatekeeper acceptance

## Additional Resources

- [Apple Code Signing Guide](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/)
- [Notarization Documentation](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Hardened Runtime](https://developer.apple.com/documentation/security/hardened_runtime)
- [Entitlements Documentation](https://developer.apple.com/documentation/bundleresources/entitlements)

## Quick Reference Commands

```bash
# Find certificates
security find-identity -v -p codesigning

# Code sign
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAM_ID)" \
  --options runtime \
  --entitlements entitlements.plist \
  dist/DICOMViewerV3.app

# Verify signature
codesign --verify --verbose dist/DICOMViewerV3.app

# Create ZIP
ditto -c -k --keepParent dist/DICOMViewerV3.app dist/DICOMViewerV3.zip

# Notarize
xcrun notarytool submit dist/DICOMViewerV3.zip \
  --apple-id "your@email.com" \
  --team-id "YOUR_TEAM_ID" \
  --password "YOUR_APP_SPECIFIC_PASSWORD" \
  --wait

# Staple
xcrun stapler staple dist/DICOMViewerV3.app

# Verify
xcrun stapler validate dist/DICOMViewerV3.app
spctl --assess --verbose --type execute dist/DICOMViewerV3.app
```

