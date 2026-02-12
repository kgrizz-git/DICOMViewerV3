# GitHub Releases, Versions, and Tags Guide

This guide explains Git tags, semantic versioning, and GitHub releases, and how they work together in the DICOM Viewer V3 project.

## Table of Contents

1. [Overview](#overview)
2. [Git Tags](#git-tags)
3. [Semantic Versioning](#semantic-versioning)
4. [GitHub Releases](#github-releases)
5. [How They Work Together](#how-they-work-together)
6. [Your Project Workflow](#your-project-workflow)
7. [Best Practices](#best-practices)
8. [Quick Reference](#quick-reference)
9. [Common Tasks](#common-tasks)

## Overview

**Git Tags**, **Versions**, and **GitHub Releases** work together to create a complete release management system:

- **Git Tags**: Mark specific commits in your repository history
- **Versions**: Follow semantic versioning (e.g., `3.0.0`) to indicate changes
- **GitHub Releases**: Package tags with downloadable assets and release notes

```
Git Tag (v3.0.0)
    ↓
GitHub Release (created from tag)
    ↓
Downloadable Assets (executables, AppImages)
```

## Git Tags

A **Git tag** is a pointer to a specific commit in your repository's history. Think of it as a bookmark that marks important milestones.

### Types of Tags

#### 1. Lightweight Tags

Simple pointers to commits with no additional metadata:

```bash
git tag v3.0.0
```

**Characteristics:**
- Just a pointer to a commit
- No metadata stored
- Faster to create
- Less information available

#### 2. Annotated Tags (Recommended)

Include additional metadata (author, date, message):

```bash
git tag -a v3.0.0 -m "Release version 3.0.0"
```

**Characteristics:**
- Store author information
- Store creation date
- Include a message/description
- Recommended for releases
- Can be signed with GPG

### Common Tag Naming Conventions

- **Version tags**: `v1.0.0`, `v2.1.3`, `v3.0.0` (your project uses this format)
- **Alternative format**: `release-1.0.0`, `1.0.0`
- **Pre-release tags**: `v1.0.0-beta`, `v1.0.0-rc.1`
- **Branch tags**: `v1.0.0-main`, `v1.0.0-dev`

### Tag Commands

#### Create a Tag

```bash
# Create annotated tag (recommended)
git tag -a v3.0.0 -m "Release version 3.0.0"

# Create lightweight tag
git tag v3.0.0

# Create tag for specific commit
git tag -a v3.0.0 -m "Release version 3.0.0" abc1234
```

#### List Tags

```bash
# List all tags
git tag

# List tags matching a pattern
git tag -l "v3.*"

# List tags with messages
git tag -n
```

#### View Tag Information

```bash
# Show tag details
git show v3.0.0

# Show tag message only
git tag -l -n1 v3.0.0
```

#### Push Tags to GitHub

```bash
# Push a specific tag
git push origin v3.0.0

# Push all tags
git push origin --tags

# Push tags and commits together
git push origin main --tags
```

#### Delete Tags

```bash
# Delete local tag
git tag -d v3.0.0

# Delete remote tag
git push origin --delete v3.0.0

# Delete both local and remote
git tag -d v3.0.0
git push origin --delete v3.0.0
```

#### Update Existing Tag

```bash
# Force update local tag
git tag -a -f v3.0.0 -m "Updated release message"

# Force push updated tag (use with caution)
git push origin v3.0.0 --force
```

## Semantic Versioning

**Semantic Versioning** (SemVer) is a versioning scheme that uses three numbers: `MAJOR.MINOR.PATCH` (e.g., `3.0.0`).

> **📖 For a comprehensive guide on Semantic Versioning, including detailed rules, decision-making processes, and how AI can help you follow SemVer, see [SEMANTIC_VERSIONING_GUIDE.md](./SEMANTIC_VERSIONING_GUIDE.md).**

This section provides a quick reference. For complete details, refer to the comprehensive guide.

### Version Number Format

```
MAJOR.MINOR.PATCH
  3  .  0  .  0
```

### Version Increment Rules

1. **MAJOR version** (X.0.0): Increment when you make incompatible API changes
   - Breaking changes
   - Major feature removals
   - Significant architectural changes
   - Example: `2.0.0` → `3.0.0`

2. **MINOR version** (0.X.0): Increment when you add functionality in a backward-compatible manner
   - New features
   - New functionality
   - Backward compatible changes
   - Example: `3.0.0` → `3.1.0`

3. **PATCH version** (0.0.X): Increment when you make backward-compatible bug fixes
   - Bug fixes
   - Security patches
   - Small improvements
   - Example: `3.1.0` → `3.1.1`

### Version Examples

```
3.0.0  → Initial release
3.0.1  → Bug fix release
3.0.2  → Another bug fix
3.1.0  → New feature added
3.1.1  → Bug fix for new feature
3.2.0  → Another new feature
4.0.0  → Major breaking change
```

### Pre-Release Versions

For beta, alpha, or release candidates:

```
3.0.0-alpha.1    → Alpha release
3.0.0-beta.1     → Beta release
3.0.0-rc.1       → Release candidate
3.0.0-rc.2       → Second release candidate
3.0.0            → Final release
```

### Version Comparison

Versions are compared numerically:

- `3.0.0` < `3.1.0` < `3.1.1` < `4.0.0`
- `3.0.0-beta` < `3.0.0-rc.1` < `3.0.0`

## GitHub Releases

A **GitHub Release** is a feature that packages a Git tag with:
- Release notes (what changed)
- Downloadable assets (executables, AppImages, etc.)
- A public page for distribution
- Version information

### Release Features

- **Permanent storage**: Unlike artifacts, releases are permanent
- **Public access**: Users can download directly from the releases page
- **Version tracking**: Each release has a version tag
- **Release notes**: Describe what changed
- **Asset downloads**: Attach executables, installers, documentation
- **Direct links**: Shareable download URLs

### How Tags and Releases Relate

```
Git Tag (v3.0.0)
    ↓
GitHub Release (created from tag)
    ↓
Downloadable Assets (executables, AppImages)
```

**Important:** A release is always based on a tag, but not every tag needs a release.

### Creating a Release

#### Method 1: Push a Tag (Automatic - Your Project)

When you push a tag that matches your workflow pattern (`v*`), GitHub Actions automatically:
1. Builds executables
2. Creates a GitHub Release
3. Attaches all built files to the release

```bash
# Create and push tag
git tag -a v3.0.0 -m "Release version 3.0.0"
git push origin v3.0.0

# GitHub Actions automatically creates the release
```

#### Method 2: Create Manually on GitHub

1. Go to your repository on GitHub
2. Click **"Releases"** in the right sidebar
3. Click **"Draft a new release"**
4. Choose an existing tag or create a new one
5. Add release title and notes
6. Upload assets (executables, etc.)
7. Click **"Publish release"**

### Release Page Structure

A GitHub Release page includes:

- **Version tag**: `v3.0.0`
- **Release title**: Usually matches the tag
- **Release notes**: Description of changes
- **Assets**: Downloadable files
  - `DICOMViewerV3.exe` (Windows)
  - `DICOMViewerV3.app` (macOS)
  - `DICOMViewerV3-x86_64.AppImage` (Linux)
- **Source code**: Link to the tagged commit

### Accessing Releases

**URL Format:**
```
https://github.com/username/repository/releases/tag/v3.0.0
```

**For your project:**
```
https://github.com/kgrizz-git/DICOMViewerV3/releases/tag/v3.0.0
```

## How They Work Together

### Complete Workflow

```
1. Developer makes changes
   ↓
2. Commits changes to repository
   ↓
3. Creates and pushes a tag (v3.0.0)
   ↓
4. GitHub Actions detects tag push
   ↓
5. Workflow builds executables
   ↓
6. GitHub creates Release from tag
   ↓
7. Executables attached to Release
   ↓
8. Users download from Releases page
```

### Visual Example

```
Your Repository
│
├── Commits
│   ├── commit abc123 "Initial commit"
│   ├── commit def456 "Add feature X"  ← Tag v3.0.0 points here
│   ├── commit ghi789 "Fix bug Y"      ← Tag v3.0.1 points here
│   └── commit jkl012 "Add feature Z"  ← Tag v3.1.0 points here
│
├── Tags (pointers to commits)
│   ├── v3.0.0 → points to def456
│   ├── v3.0.1 → points to ghi789
│   └── v3.1.0 → points to jkl012
│
└── GitHub Releases (created from tags)
    ├── Release v3.0.0
    │   ├── DICOMViewerV3-3.0.0-x86_64.AppImage
    │   ├── DICOMViewerV3.exe
    │   └── DICOMViewerV3.app
    ├── Release v3.0.1
    │   └── (executables...)
    └── Release v3.1.0
        └── (executables...)
```

## Your Project Workflow

### Current Configuration

Your GitHub Actions workflow (`.github/workflows/build.yml`) is configured to:

1. **Trigger on tag push**: Detects tags matching `v*` pattern
2. **Build executables**: Creates Windows, macOS, and Linux builds
3. **Create AppImage**: Generates Linux AppImage with version in filename
4. **Create Release**: Automatically creates GitHub Release from tag
5. **Attach assets**: Uploads all executables to the release

### Example Workflow

#### Step 1: Make Changes and Commit

```bash
# Make your changes
git add .
git commit -m "Add new feature X"
git push origin main
```

#### Step 2: Create and Push a Tag

```bash
# Create annotated tag
git tag -a v3.1.0 -m "Release version 3.1.0 - Added feature X"

# Push tag to GitHub
git push origin v3.1.0
```

#### Step 3: GitHub Actions Automatically

When you push the tag, GitHub Actions automatically:

1. **Detects the tag**: `v3.1.0` matches the `v*` pattern
2. **Builds executables**:
   - Windows: `DICOMViewerV3.exe`
   - macOS: `DICOMViewerV3.app`
   - Linux: `DICOMViewerV3` (executable)
3. **Creates AppImage**: `DICOMViewerV3-3.1.0-x86_64.AppImage`
4. **Creates GitHub Release**: From tag `v3.1.0`
5. **Attaches all files**: All executables and AppImage to the release

#### Step 4: Users Download

Users can now download from:
```
https://github.com/kgrizz-git/DICOMViewerV3/releases/tag/v3.1.0
```

### Version Extraction in Your Workflow

Your workflow extracts the version number from the tag:

```bash
# Tag: v3.1.0
# Extracted version: 3.1.0
# AppImage name: DICOMViewerV3-3.1.0-x86_64.AppImage
```

The workflow uses this logic:
```bash
if [[ "${{ github.ref }}" == refs/tags/* ]]; then
  VERSION=$(echo "${{ github.ref }}" | sed 's/refs\/tags\/v//')
  # v3.1.0 → 3.1.0
else
  VERSION="latest"
fi
```

### Testing Before Release

**Recommended workflow:**

1. **Test with artifacts** (manual trigger):
   ```bash
   # Push code
   git push origin main
   
   # Manually trigger workflow from GitHub Actions tab
   # Download artifacts to test
   ```

2. **Create release** (when ready):
   ```bash
   # Create and push tag
   git tag -a v3.1.0 -m "Release version 3.1.0"
   git push origin v3.1.0
   
   # Release created automatically with all executables
   ```

## Best Practices

### Tagging

1. **Use annotated tags** for releases:
   ```bash
   git tag -a v3.0.0 -m "Release version 3.0.0"
   ```

2. **Follow semantic versioning**: Use `MAJOR.MINOR.PATCH` format

3. **Tag from stable branch**: Usually `main` or `master`

4. **Write clear tag messages**: Describe what the release includes

5. **Tag format**: Use `v` prefix (`v3.0.0`) to match your workflow pattern

6. **Don't move tags**: Once pushed, tags should be immutable (use new version instead)

### Versioning

1. **Start with 0.1.0**: For initial development releases
2. **Increment appropriately**: 
   - Bug fix → PATCH
   - New feature → MINOR
   - Breaking change → MAJOR
3. **Use pre-release versions**: For beta/alpha testing
4. **Document changes**: Keep a changelog

### Releases

1. **Test before releasing**: Use artifacts for testing
2. **Write release notes**: Describe what changed
3. **Include all platforms**: Ensure all executables are attached
4. **Verify downloads**: Test that files download correctly
5. **Announce releases**: Notify users of new versions

### Workflow

1. **Develop on feature branches**: Keep `main` stable
2. **Merge to main**: After testing
3. **Tag from main**: When ready to release
4. **Let automation handle builds**: GitHub Actions creates releases

## Quick Reference

### Tag Commands

| Action | Command | Result |
|--------|---------|--------|
| Create tag | `git tag -a v3.0.0 -m "Message"` | Tag created locally |
| Push tag | `git push origin v3.0.0` | Tag pushed, triggers workflow |
| List tags | `git tag` | Shows all tags |
| View tag | `git show v3.0.0` | Shows tag details |
| Delete tag | `git tag -d v3.0.0` | Deletes local tag |
| Delete remote tag | `git push origin --delete v3.0.0` | Deletes remote tag |

### Version Examples

| Current Version | Change Type | New Version |
|----------------|-------------|-------------|
| 3.0.0 | Bug fix | 3.0.1 |
| 3.0.1 | New feature | 3.1.0 |
| 3.1.0 | Breaking change | 4.0.0 |
| 3.0.0 | Beta release | 3.0.0-beta.1 |
| 3.0.0-beta.1 | Release candidate | 3.0.0-rc.1 |
| 3.0.0-rc.1 | Final release | 3.0.0 |

### Release Workflow

```bash
# 1. Make changes
git add .
git commit -m "Add feature"
git push origin main

# 2. Create tag
git tag -a v3.1.0 -m "Release version 3.1.0"
git push origin v3.1.0

# 3. GitHub Actions automatically:
#    - Builds executables
#    - Creates AppImage
#    - Creates GitHub Release
#    - Attaches all files

# 4. Users download from releases page
```

## Common Tasks

### Creating a New Release

```bash
# 1. Ensure all changes are committed and pushed
git status
git add .
git commit -m "Final changes for v3.1.0"
git push origin main

# 2. Create and push tag
git tag -a v3.1.0 -m "Release version 3.1.0 - Added feature X"
git push origin v3.1.0

# 3. Wait for GitHub Actions to complete
# 4. Check releases page for new release
```

### Updating Release Notes

1. Go to GitHub Releases page
2. Click on the release you want to edit
3. Click "Edit release"
4. Update release notes
5. Click "Update release"

### Creating a Pre-Release

```bash
# Create beta tag
git tag -a v3.1.0-beta.1 -m "Beta release 3.1.0-beta.1"
git push origin v3.1.0-beta.1

# Note: Your workflow uses 'v*' pattern, so this will trigger
# You may want to mark it as pre-release on GitHub
```

### Fixing a Release

If you need to fix a release:

```bash
# Option 1: Create patch release
git tag -a v3.1.1 -m "Patch release - Fix critical bug"
git push origin v3.1.1

# Option 2: Delete and recreate (use with caution)
git tag -d v3.1.0
git push origin --delete v3.1.0
# Make fixes, then recreate tag
git tag -a v3.1.0 -m "Release version 3.1.0 (fixed)"
git push origin v3.1.0
```

### Viewing Release History

```bash
# List all tags
git tag

# View tag details
git show v3.1.0

# Compare versions
git diff v3.0.0 v3.1.0
```

### Checking What Changed Between Versions

```bash
# Show commits between two tags
git log v3.0.0..v3.1.0

# Show summary of changes
git log v3.0.0..v3.1.0 --oneline

# Show file changes
git diff v3.0.0..v3.1.0 --stat
```

## Additional Resources

- **Semantic Versioning Guide**: [SEMANTIC_VERSIONING_GUIDE.md](./SEMANTIC_VERSIONING_GUIDE.md) - Comprehensive guide to Semantic Versioning for this project
- **Semantic Versioning (Official)**: https://semver.org/
- **Git Tagging**: https://git-scm.com/book/en/v2/Git-Basics-Tagging
- **GitHub Releases**: https://docs.github.com/en/repositories/releasing-projects-on-github
- **GitHub Actions**: https://docs.github.com/en/actions

## Notes

- **Tag format**: Your workflow expects tags starting with `v` (e.g., `v3.0.0`)
- **Version extraction**: The workflow automatically extracts `3.0.0` from `v3.0.0`
- **File naming**: AppImages are named `DICOMViewerV3-3.0.0-x86_64.AppImage`
- **Automatic releases**: Pushing a tag automatically creates a release
- **Artifacts vs Releases**: Artifacts are temporary (90 days), releases are permanent
