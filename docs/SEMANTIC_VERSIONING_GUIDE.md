# Semantic Versioning (SemVer) Comprehensive Guide

This guide provides a detailed explanation of Semantic Versioning (SemVer) based on the official specification at [semver.org](https://semver.org/), and explains how to apply it to your DICOM Viewer V3 project.

## Table of Contents

1. [Introduction](#introduction)
2. [What is Semantic Versioning?](#what-is-semantic-versioning)
3. [The SemVer Specification](#the-semver-specification)
4. [Version Number Format](#version-number-format)
5. [Version Increment Rules](#version-increment-rules)
6. [Pre-Release Versions](#pre-release-versions)
7. [Build Metadata](#build-metadata)
8. [Version Precedence](#version-precedence)
9. [Public API Definition](#public-api-definition)
10. [Decision-Making Guide](#decision-making-guide)
11. [Common Scenarios](#common-scenarios)
12. [How AI Can Help](#how-ai-can-help)
    - [Automatic Change Analysis](#9-automatic-change-analysis-since-prior-release) - Automatically analyze all changes since a prior release
13. [Best Practices](#best-practices)
14. [FAQ](#faq)
15. [Tools and Validation](#tools-and-validation)

---

## Introduction

Semantic Versioning (SemVer) is a versioning scheme that uses a three-part version number (`MAJOR.MINOR.PATCH`) to communicate the nature of changes in your software. It was created to solve "dependency hell" - the problem of managing dependencies in software systems.

### Why Use Semantic Versioning?

- **Clear Communication**: Version numbers convey meaning about what changed
- **Dependency Management**: Enables safe and predictable dependency updates
- **User Expectations**: Users understand what to expect from version changes
- **Professional Standards**: Widely adopted in open-source and commercial software

---

## What is Semantic Versioning?

Semantic Versioning is a simple set of rules that dictate how version numbers are assigned and incremented. The key principle is:

> **Given a version number MAJOR.MINOR.PATCH, increment the:**
> 1. **MAJOR** version when you make incompatible API changes
> 2. **MINOR** version when you add functionality in a backward compatible manner
> 3. **PATCH** version when you make backward compatible bug fixes

### The Problem It Solves

In systems with many dependencies, releasing new package versions can become a nightmare:
- **Version Lock**: Dependencies specified too tightly prevent upgrades
- **Version Promiscuity**: Dependencies specified too loosely assume compatibility that doesn't exist
- **Dependency Hell**: When version lock and/or version promiscuity prevent moving forward

SemVer provides a solution by establishing clear rules for version increments.

---

## The SemVer Specification

The Semantic Versioning specification (SemVer) consists of 11 rules. Here they are in detail:

### Rule 1: Public API Declaration

**Software using Semantic Versioning MUST declare a public API.** This API could be:
- Declared in the code itself (e.g., exported functions, public classes)
- Documented separately (e.g., API documentation, README)
- A combination of both

**For DICOM Viewer V3:**
- Your public API includes:
  - Command-line interface (if any)
  - File formats supported (input/output)
  - Configuration file formats
  - Plugin interfaces (if any)
  - User-facing features and behaviors

### Rule 2: Version Number Format

**A normal version number MUST take the form X.Y.Z where:**
- X, Y, and Z are non-negative integers
- MUST NOT contain leading zeroes
- X is the major version
- Y is the minor version
- Z is the patch version
- Each element MUST increase numerically

**Examples:**
- ✅ Valid: `1.0.0`, `1.9.0`, `1.10.0`, `1.11.0`, `2.0.0`
- ❌ Invalid: `01.0.0` (leading zero), `1.0` (missing patch), `v1.0.0` (includes prefix)

**Note:** The "v" prefix (e.g., `v1.0.0`) is commonly used in Git tags but is NOT part of the semantic version itself. The semantic version is `1.0.0`.

### Rule 3: Immutability

**Once a versioned package has been released, the contents of that version MUST NOT be modified.** Any modifications MUST be released as a new version.

**Implications:**
- Never modify a released version
- If you find a bug in `3.0.0`, release `3.0.1` (or `3.0.2` if `3.0.1` already exists)
- Never force-update a tag that's been pushed to a public repository

### Rule 4: Major Version Zero (0.y.z)

**Major version zero (0.y.z) is for initial development.**
- Anything MAY change at any time
- The public API SHOULD NOT be considered stable
- Use for rapid development and experimentation

**Examples:**
- `0.1.0` - First development release
- `0.2.0` - Added features, API may change
- `0.9.0` - Approaching 1.0.0
- `1.0.0` - First stable release

### Rule 5: Version 1.0.0

**Version 1.0.0 defines the public API.** The way in which the version number is incremented after this release is dependent on this public API and how it changes.

**When to release 1.0.0:**
- Your software is being used in production
- You have a stable API on which users depend
- You're worrying about backward compatibility
- You're ready to commit to maintaining API stability

### Rule 6: Patch Version (x.y.Z | x > 0)

**Patch version Z MUST be incremented if only backward compatible bug fixes are introduced.**

**A bug fix is defined as an internal change that fixes incorrect behavior.**

**Examples of PATCH increments:**
- Fixing a crash when opening certain DICOM files
- Correcting a calculation error in ROI statistics
- Fixing a UI bug where buttons don't respond
- Resolving a memory leak
- Fixing incorrect metadata display

**What does NOT count as a patch:**
- Adding new features (use MINOR)
- Changing existing behavior (could be MINOR or MAJOR)
- Removing features (use MAJOR)

### Rule 7: Minor Version (x.Y.z | x > 0)

**Minor version Y MUST be incremented if:**
1. New, backward compatible functionality is introduced to the public API
2. Any public API functionality is marked as deprecated

**Minor version Y MAY be incremented if:**
- Substantial new functionality or improvements are introduced within the private code
- It MAY include patch level changes

**Patch version MUST be reset to 0 when minor version is incremented.**

**Examples of MINOR increments:**
- Adding a new export format (JPEG, PNG, etc.)
- Adding a new keyboard shortcut
- Adding a new ROI tool (rectangle, ellipse, etc.)
- Adding a new feature like image fusion
- Deprecating an old feature (before removing it in MAJOR)
- Performance improvements that don't change API
- UI improvements that don't change functionality

**Examples:**
- `3.0.0` → `3.1.0` (new feature added)
- `3.1.5` → `3.2.0` (new feature, patch reset to 0)

### Rule 8: Major Version (X.y.z | X > 0)

**Major version X MUST be incremented if any backward incompatible changes are introduced to the public API.**

**It MAY also include minor and patch level changes.**

**Patch and minor versions MUST be reset to 0 when major version is incremented.**

**Examples of MAJOR increments:**
- Removing a feature
- Changing the behavior of an existing feature in a way that breaks compatibility
- Changing file format requirements
- Changing command-line interface
- Removing support for an operating system
- Changing configuration file format
- Breaking changes to plugin API

**Examples:**
- `2.9.5` → `3.0.0` (breaking change, minor and patch reset)
- `3.0.0` → `4.0.0` (another breaking change)

### Rule 9: Pre-Release Versions

**A pre-release version MAY be denoted by appending a hyphen and a series of dot separated identifiers immediately following the patch version.**

**Requirements:**
- Identifiers MUST comprise only ASCII alphanumerics and hyphens `[0-9A-Za-z-]`
- Identifiers MUST NOT be empty
- Numeric identifiers MUST NOT include leading zeroes
- Pre-release versions have a lower precedence than the associated normal version

**Examples:**
- `1.0.0-alpha`
- `1.0.0-alpha.1`
- `1.0.0-0.3.7`
- `1.0.0-beta`
- `1.0.0-beta.2`
- `1.0.0-beta.11`
- `1.0.0-rc.1`
- `1.0.0-rc.2`

**Common Pre-Release Identifiers:**
- `alpha` or `alpha.1`, `alpha.2` - Early testing, unstable
- `beta` or `beta.1`, `beta.2` - Feature complete, testing
- `rc` or `rc.1`, `rc.2` - Release candidate, near final

**Precedence:**
- `1.0.0-alpha` < `1.0.0-alpha.1` < `1.0.0-beta` < `1.0.0-rc.1` < `1.0.0`

### Rule 10: Build Metadata

**Build metadata MAY be denoted by appending a plus sign and a series of dot separated identifiers immediately following the patch or pre-release version.**

**Requirements:**
- Identifiers MUST comprise only ASCII alphanumerics and hyphens `[0-9A-Za-z-]`
- Identifiers MUST NOT be empty
- Build metadata MUST be ignored when determining version precedence
- Two versions that differ only in build metadata have the same precedence

**Examples:**
- `1.0.0+20130313144700`
- `1.0.0+exp.sha.5114f85`
- `1.0.0-alpha+001`
- `1.0.0-beta+exp.sha.5114f85`
- `1.0.0+21AF26D3----117B344092BD`

**Use Cases:**
- Build timestamp
- Git commit hash
- Build number
- CI/CD pipeline identifier

**Note:** Build metadata is typically used for internal tracking and doesn't affect version comparison.

### Rule 11: Version Precedence

**Precedence refers to how versions are compared to each other when ordered.**

**Precedence MUST be calculated by:**
1. Separating the version into major, minor, patch and pre-release identifiers (build metadata does not figure into precedence)
2. Comparing each identifier from left to right:
   - Major, minor, and patch versions are always compared numerically
   - When major, minor, and patch are equal, a pre-release version has lower precedence than a normal version
   - Pre-release versions are compared by:
     - Identifiers consisting of only digits are compared numerically
     - Identifiers with letters or hyphens are compared lexically in ASCII sort order
     - Numeric identifiers always have lower precedence than non-numeric identifiers
     - A larger set of pre-release fields has a higher precedence than a smaller set, if all preceding identifiers are equal

**Examples:**
- `1.0.0` < `2.0.0` < `2.1.0` < `2.1.1`
- `1.0.0-alpha` < `1.0.0`
- `1.0.0-alpha` < `1.0.0-alpha.1` < `1.0.0-alpha.beta` < `1.0.0-beta` < `1.0.0-beta.2` < `1.0.0-beta.11` < `1.0.0-rc.1` < `1.0.0`
- `1.0.0+20130313144700` = `1.0.0+exp.sha.5114f85` (same precedence, build metadata ignored)

---

## Version Number Format

### Standard Format

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

### Components

1. **MAJOR** (X): Breaking changes
2. **MINOR** (Y): New features, backward compatible
3. **PATCH** (Z): Bug fixes, backward compatible
4. **PRERELEASE** (optional): Alpha, beta, rc, etc.
5. **BUILD** (optional): Build metadata

### Examples

```
3.0.0                    # Standard release
3.1.0                    # Minor release with new features
3.1.5                    # Patch release with bug fixes
3.1.5-alpha              # Pre-release alpha
3.1.5-beta.1             # Pre-release beta 1
3.1.5-rc.2               # Release candidate 2
3.1.5+20240101          # Build with metadata
3.1.5-beta.1+abc123     # Pre-release with build metadata
```

---

## Version Increment Rules

### Decision Tree

```
Is this a bug fix that doesn't change behavior?
├─ YES → Increment PATCH (3.0.0 → 3.0.1)
└─ NO → Does it add new functionality?
    ├─ YES → Is it backward compatible?
    │   ├─ YES → Increment MINOR (3.0.0 → 3.1.0)
    │   └─ NO → Increment MAJOR (3.0.0 → 4.0.0)
    └─ NO → Does it change existing behavior?
        ├─ YES → Is it backward compatible?
        │   ├─ YES → Increment MINOR (3.0.0 → 3.1.0)
        │   └─ NO → Increment MAJOR (3.0.0 → 4.0.0)
        └─ NO → Does it remove functionality?
            └─ YES → Increment MAJOR (3.0.0 → 4.0.0)
```

### Detailed Rules

#### When to Increment PATCH (x.y.Z)

**Increment PATCH when:**
- Fixing bugs that don't change the public API
- Fixing incorrect behavior
- Security patches that don't change functionality
- Internal refactoring that doesn't affect users
- Documentation fixes (if versioned)

**Reset PATCH to 0 when:**
- MINOR version is incremented
- MAJOR version is incremented

**Examples:**
- `3.0.0` → `3.0.1`: Fixed crash when opening corrupted DICOM files
- `3.1.5` → `3.1.6`: Fixed calculation error in ROI statistics
- `3.2.0` → `3.2.1`: Fixed memory leak in image loading

#### When to Increment MINOR (x.Y.z)

**Increment MINOR when:**
- Adding new features that are backward compatible
- Adding new functionality to the public API
- Deprecating functionality (before removing in MAJOR)
- Adding new export formats
- Adding new tools or features
- Performance improvements (if significant)
- UI improvements that add functionality

**Reset MINOR to 0 when:**
- MAJOR version is incremented

**Examples:**
- `3.0.0` → `3.1.0`: Added image fusion feature
- `3.1.5` → `3.2.0`: Added new ROI tool, reset patch to 0
- `3.0.0` → `3.1.0`: Deprecated old export format (will remove in 4.0.0)

#### When to Increment MAJOR (X.y.z)

**Increment MAJOR when:**
- Making breaking changes to the public API
- Removing functionality
- Changing behavior in a way that breaks compatibility
- Changing file format requirements
- Removing support for features
- Changing configuration in incompatible ways

**Reset both MINOR and PATCH to 0 when:**
- MAJOR version is incremented

**Examples:**
- `2.9.5` → `3.0.0`: Removed support for Windows 7
- `3.0.0` → `4.0.0`: Changed DICOM export format structure
- `3.1.0` → `4.0.0`: Removed deprecated feature that was marked in 3.1.0

---

## Pre-Release Versions

### Purpose

Pre-release versions indicate that the version is unstable and might not satisfy the intended compatibility requirements. They're useful for:
- Alpha testing
- Beta testing
- Release candidates
- Development snapshots

### Format

```
MAJOR.MINOR.PATCH-IDENTIFIER[.IDENTIFIER]...
```

### Common Identifiers

1. **alpha** / **alpha.N**: Early development, unstable
   - Example: `3.1.0-alpha`, `3.1.0-alpha.1`

2. **beta** / **beta.N**: Feature complete, testing
   - Example: `3.1.0-beta`, `3.1.0-beta.1`

3. **rc** / **rc.N**: Release candidate, near final
   - Example: `3.1.0-rc.1`, `3.1.0-rc.2`

### Precedence Rules

- Pre-release versions have lower precedence than normal versions
- `1.0.0-alpha` < `1.0.0-alpha.1` < `1.0.0-beta` < `1.0.0-rc.1` < `1.0.0`
- Numeric identifiers are compared numerically: `beta.2` < `beta.11`
- Non-numeric identifiers are compared lexically: `alpha` < `beta`

### Workflow Example

```
3.1.0-alpha.1    # First alpha
3.1.0-alpha.2    # Second alpha
3.1.0-beta.1      # First beta
3.1.0-beta.2      # Second beta
3.1.0-rc.1        # First release candidate
3.1.0-rc.2        # Second release candidate
3.1.0             # Final release
```

---

## Build Metadata

### Purpose

Build metadata provides additional information about the build but doesn't affect version precedence. Useful for:
- Tracking build timestamps
- Including Git commit hashes
- CI/CD pipeline identifiers
- Build numbers

### Format

```
MAJOR.MINOR.PATCH[+BUILD-METADATA]
MAJOR.MINOR.PATCH-PRERELEASE[+BUILD-METADATA]
```

### Examples

- `3.1.0+20240101120000` - Build timestamp
- `3.1.0+abc123def456` - Git commit hash
- `3.1.0-beta.1+20240101` - Pre-release with build metadata
- `3.1.0+exp.sha.5114f85` - Experimental build with commit hash

### Important Notes

- Build metadata is ignored in version comparison
- `1.0.0+abc` and `1.0.0+xyz` have the same precedence
- Build metadata is typically used for internal tracking

---

## Version Precedence

### Comparison Rules

1. **Major, Minor, Patch**: Compared numerically
   - `1.0.0` < `2.0.0` < `2.1.0` < `2.1.1`

2. **Pre-release vs Normal**: Pre-release has lower precedence
   - `1.0.0-alpha` < `1.0.0`

3. **Pre-release Comparison**:
   - Compare dot-separated identifiers left to right
   - Numeric identifiers: compare numerically (`2` < `11`)
   - Non-numeric identifiers: compare lexically (`alpha` < `beta`)
   - Numeric < non-numeric (`1` < `alpha`)
   - More identifiers > fewer identifiers (if preceding equal)

### Examples

```
1.0.0-alpha
1.0.0-alpha.1
1.0.0-alpha.beta
1.0.0-beta
1.0.0-beta.2
1.0.0-beta.11
1.0.0-rc.1
1.0.0
```

---

## Public API Definition

### What is a Public API?

Your public API includes anything that users or other software depend on:

1. **User-Facing Features**
   - File formats supported (input/output)
   - Keyboard shortcuts
   - Menu items and their behavior
   - Tool functionality
   - Export formats

2. **Configuration**
   - Configuration file formats
   - Command-line arguments
   - Settings file structure

3. **Data Formats**
   - Export file formats
   - Import file formats
   - Metadata structures

4. **Behavior**
   - How features work
   - Default settings
   - Error handling

### For DICOM Viewer V3

**Public API includes:**
- Supported DICOM file formats and structures
- Export formats (JPEG, PNG, DICOM)
- Keyboard shortcuts
- ROI tools and their behavior
- Measurement functionality
- Window/level behavior
- File loading behavior
- Configuration file formats (if any)

**Not part of public API:**
- Internal code structure
- Private methods
- Implementation details
- UI layout (unless it affects functionality)

---

## Decision-Making Guide

### Step-by-Step Process

1. **Identify the Change**
   - What exactly changed?
   - Is it a bug fix, new feature, or behavior change?

2. **Determine Impact**
   - Does it affect the public API?
   - Is it backward compatible?
   - Will existing users be affected?

3. **Apply SemVer Rules**
   - Use the decision tree above
   - Consider edge cases

4. **Document the Decision**
   - Update CHANGELOG
   - Write release notes
   - Communicate breaking changes clearly

### Common Scenarios

#### Scenario 1: Bug Fix

**Situation:** Fixed a crash when opening certain DICOM files.

**Analysis:**
- Fixes incorrect behavior (crash)
- Doesn't change public API
- Backward compatible

**Decision:** Increment PATCH
- `3.0.0` → `3.0.1`

#### Scenario 2: New Feature

**Situation:** Added image fusion feature.

**Analysis:**
- Adds new functionality
- Doesn't break existing features
- Backward compatible

**Decision:** Increment MINOR
- `3.0.0` → `3.1.0`

#### Scenario 3: Breaking Change

**Situation:** Removed support for Windows 7.

**Analysis:**
- Removes functionality
- Breaks compatibility for Windows 7 users
- Not backward compatible

**Decision:** Increment MAJOR
- `2.9.5` → `3.0.0`

#### Scenario 4: Deprecation

**Situation:** Marking old export format as deprecated (will remove in next major version).

**Analysis:**
- Still works, but marked for removal
- Backward compatible (for now)
- Users should migrate

**Decision:** Increment MINOR
- `3.0.0` → `3.1.0`
- Document deprecation
- Remove in `4.0.0`

#### Scenario 5: Behavior Change

**Situation:** Changed default window/level calculation method.

**Analysis:**
- Changes existing behavior
- May affect users who depend on old behavior
- Could be MINOR or MAJOR depending on impact

**Decision:** 
- If subtle improvement: MINOR (`3.0.0` → `3.1.0`)
- If significant change: MAJOR (`3.0.0` → `4.0.0`)

---

## Common Scenarios

### Adding a New Feature

**Example:** Adding histogram display feature

**Version:** `3.0.0` → `3.1.0`

**Reasoning:**
- New functionality added
- Doesn't break existing features
- Backward compatible

### Fixing a Bug

**Example:** Fixed ROI statistics calculation error

**Version:** `3.1.0` → `3.1.1`

**Reasoning:**
- Fixes incorrect behavior
- Doesn't change API
- Backward compatible bug fix

### Removing a Feature

**Example:** Removed support for old DICOM format

**Version:** `2.9.5` → `3.0.0`

**Reasoning:**
- Removes functionality
- Breaking change
- Not backward compatible

### Changing Default Behavior

**Example:** Changed default zoom level

**Analysis needed:**
- Does it break user expectations?
- Is it a significant change?

**Possible versions:**
- Minor change: `3.0.0` → `3.1.0`
- Major change: `3.0.0` → `4.0.0`

### Performance Improvements

**Example:** Optimized image loading, 2x faster

**Version:** `3.0.0` → `3.1.0` (typically)

**Reasoning:**
- Improvement doesn't change API
- Usually MINOR unless it's a critical fix (then PATCH)

### Security Fixes

**Example:** Fixed vulnerability in file parsing

**Version:** `3.0.0` → `3.0.1` (typically)

**Reasoning:**
- Security fix is a bug fix
- Usually PATCH unless it requires API changes

### Pre-Release Workflow

**Example:** Preparing version 3.1.0

```
3.1.0-alpha.1    # First alpha for testing
3.1.0-alpha.2    # Second alpha with fixes
3.1.0-beta.1      # Beta release
3.1.0-beta.2      # Beta with fixes
3.1.0-rc.1        # Release candidate
3.1.0             # Final release
```

---

## How AI Can Help

As an AI assistant, I can help you follow Semantic Versioning rules in several ways:

### 1. Version Number Analysis

**I can help you determine the correct version increment by:**
- Analyzing your changes and categorizing them
- Identifying breaking vs. non-breaking changes
- Suggesting appropriate version numbers
- Explaining the reasoning behind version choices

**Example questions you can ask:**
- "I fixed a bug in ROI calculations and added a new export format. What version should this be?"
- "I removed support for Windows 7. Is this a major version bump?"
- "I changed the default window/level behavior. Should this be minor or major?"

### 2. Change Categorization

**I can help categorize your changes:**
- Review commit messages or changelog entries
- Identify which changes are bug fixes, features, or breaking changes
- Group related changes together
- Suggest appropriate version increments for each category

**Example workflow:**
```
You: "Here are my recent changes: [list of changes]"
AI: "Based on these changes:
     - Bug fixes: 3 items → PATCH increment
     - New features: 2 items → MINOR increment
     - Breaking changes: 0 items
     Suggested version: 3.0.5 → 3.1.0"
```

### 3. Breaking Change Detection

**I can help identify breaking changes by:**
- Analyzing code changes for API modifications
- Reviewing documentation changes
- Identifying removed features or changed behaviors
- Flagging potential compatibility issues

**Example:**
```
You: "I changed how the export dialog works. Is this breaking?"
AI: "Let me analyze the changes... [analysis]
     This changes user-facing behavior. If users have scripts
     or workflows depending on the old behavior, this is a
     breaking change → MAJOR version increment."
```

### 4. Version Validation

**I can validate version numbers by:**
- Checking format compliance (no leading zeros, correct structure)
- Verifying pre-release format
- Validating build metadata format
- Ensuring version increments follow SemVer rules

**Example:**
```
You: "Is '3.01.0' a valid semantic version?"
AI: "No. '3.01.0' contains a leading zero in the minor version.
     Valid versions: '3.1.0', '3.10.0', but not '3.01.0'."
```

### 5. Release Notes Generation

**I can help create release notes by:**
- Organizing changes by version type (major/minor/patch)
- Writing clear descriptions of changes
- Highlighting breaking changes
- Formatting according to SemVer conventions

**Example:**
```
You: "Generate release notes for version 3.1.0"
AI: [Generates formatted release notes with:
     - New features section
     - Bug fixes section
     - Breaking changes (if any)
     - Migration guide (if needed)]
```

### 6. Pre-Release Management

**I can help with pre-release versions by:**
- Suggesting appropriate pre-release identifiers
- Managing alpha/beta/rc progression
- Determining when to promote to final release
- Validating pre-release version formats

**Example:**
```
You: "I'm preparing 3.1.0. What pre-release versions should I use?"
AI: "Suggested progression:
     3.1.0-alpha.1 → 3.1.0-beta.1 → 3.1.0-rc.1 → 3.1.0
     Use alpha for early testing, beta for feature-complete
     testing, rc for near-final releases."
```

### 7. Changelog Maintenance

**I can help maintain changelogs by:**
- Organizing entries by SemVer categories
- Ensuring proper version formatting
- Keeping changelog structure consistent
- Adding entries in the correct format

### 8. Decision Support

**I can provide decision support by:**
- Explaining SemVer rules when you're uncertain
- Providing examples of similar scenarios
- Helping weigh the impact of changes
- Suggesting alternatives when appropriate

### 9. Automatic Change Analysis Since Prior Release

**Yes, I can automatically determine all changes since a prior release version and suggest the correct version number.**

**I can do this by:**
- Using Git commands to compare code between release tags/commits
- Analyzing commit messages and diffs
- Examining code changes to identify:
  - Bug fixes (PATCH increments)
  - New features (MINOR increments)
  - Breaking changes (MAJOR increments)
  - Deprecations (MINOR increments)
- Reviewing file modifications, additions, and deletions
- Checking for API changes, removed features, and behavior modifications
- Categorizing all changes and determining the highest required increment

**How it works:**
1. **Git History Analysis**: I can run `git log`, `git diff`, and `git show` commands to see what changed between versions
2. **Code Analysis**: I can examine modified files to understand the nature of changes
3. **Change Categorization**: I categorize each change as bug fix, feature, or breaking change
4. **Version Recommendation**: Based on SemVer rules, I suggest the appropriate version number

**Example request:**
```
"Analyze all changes since version 3.0.0 and determine what the next version should be"
```

**What I'll provide:**
- List of all changes since the specified version
- Categorization of changes (bug fixes, features, breaking changes)
- Suggested version number with reasoning
- Summary of what changed and why it affects the version

**Example output:**
```
Analyzed changes since v3.0.0:

Bug Fixes (PATCH):
- Fixed crash when opening corrupted DICOM files
- Fixed ROI statistics calculation error
- Fixed memory leak in image loading

New Features (MINOR):
- Added image fusion feature
- Added histogram display
- Added new export format (TIFF)

Breaking Changes (MAJOR):
- None detected

Recommended version: 3.0.0 → 3.1.0
Reasoning: Multiple new features require MINOR increment. 
Bug fixes are included in the MINOR release (patch reset to 0).
```

**Requirements:**
- Access to your Git repository (I can use terminal commands)
- The prior release version tag or commit hash
- Ability to read and analyze code files

**Limitations:**
- I need access to the repository to analyze changes
- Some context may require your input (e.g., "is this change user-facing?")
- Final decision is yours (I provide recommendations)
- I cannot access private Git history without repository access

**When to use this:**
- Before creating a new release
- When you're unsure what version to use
- To ensure you haven't missed any changes
- To generate comprehensive release notes

**How to request:**
Simply ask: "Analyze all changes since version X.Y.Z and determine the next version number"

I'll automatically:
1. Check what tags/commits exist
2. Compare the codebase between versions
3. Analyze all changes
4. Provide a version recommendation

### Limitations

**What I cannot do:**
- Make final decisions for you (you know your project best)
- Understand all context without you providing information
- Predict how users will react to changes
- Replace your judgment on edge cases

**What I can do:**
- Provide guidance based on SemVer specification
- Analyze changes you describe
- Suggest appropriate version numbers
- Explain the reasoning behind recommendations

### How to Get Help

**To get the best help, you can either:**

#### Option 1: Automatic Analysis (Recommended)
**Just ask me to analyze changes since a prior release:**
```
"Analyze all changes since version 3.0.0 and determine the next version number"
```

I'll automatically:
- Use Git to find all changes
- Categorize them (bug fixes, features, breaking changes)
- Suggest the correct version number
- Explain the reasoning

#### Option 2: Manual Description
**Provide information about your changes:**
1. Current version number
2. Description of changes made
3. Any breaking changes
4. Context about your project and users

**Example request:**
```
"I'm currently at version 3.0.5. I've made these changes:
- Fixed a bug where ROI statistics were incorrect
- Added support for exporting to TIFF format
- Changed the default window/level calculation (users complained
  about the old method)
- Removed the old 'Legacy Export' option that was deprecated

What version should this be, and why?"
```

**Note:** Automatic analysis is more comprehensive and less error-prone than manual descriptions, as it examines the actual code changes.

---

## Best Practices

### 1. Start with 0.1.0 for Initial Development

- Use `0.y.z` for rapid development
- Move to `1.0.0` when you have a stable API
- Don't skip from `0.9.0` directly to `2.0.0`

### 2. Use Annotated Git Tags

```bash
git tag -a v3.1.0 -m "Release version 3.1.0 - Added image fusion"
```

- Include meaningful messages
- Use "v" prefix for tags (not in SemVer itself)
- Tag from stable branches (main/master)

### 3. Maintain a CHANGELOG

Keep a changelog organized by version:

```markdown
## [3.1.0] - 2024-01-15

### Added
- Image fusion feature
- New ROI tool

### Fixed
- ROI statistics calculation

### Changed
- Improved image loading performance

## [3.0.1] - 2024-01-01

### Fixed
- Crash when opening corrupted DICOM files
```

### 4. Communicate Breaking Changes Clearly

- Document breaking changes prominently
- Provide migration guides
- Give advance notice (deprecate in MINOR, remove in MAJOR)

### 5. Use Pre-Releases for Testing

- Use alpha/beta/rc for testing
- Don't skip pre-releases for major changes
- Get feedback before final release

### 6. Don't Modify Released Versions

- Never change a released version
- Create a new version instead
- Document any issues in release notes

### 7. Be Conservative with Major Versions

- Only increment MAJOR for true breaking changes
- Consider user impact
- Provide migration paths when possible

### 8. Document Your Public API

- Clearly define what's part of your API
- Document breaking changes
- Keep API documentation up to date

### 9. Use Version Comparison Tools

- Validate versions before releasing
- Use tools to compare versions
- Ensure consistency across tools

### 10. Plan Version Numbers

- Think ahead about version strategy
- Consider long-term maintenance
- Plan deprecation cycles

---

## FAQ

### How should I deal with revisions in the 0.y.z initial development phase?

Start at `0.1.0` and increment the minor version for each subsequent release. For example: `0.1.0` → `0.2.0` → `0.3.0` → `1.0.0`.

### How do I know when to release 1.0.0?

Release `1.0.0` when:
- Your software is being used in production
- You have a stable API on which users depend
- You're worrying about backward compatibility
- You're ready to commit to API stability

### Doesn't this discourage rapid development and fast iteration?

No. Major version zero (`0.y.z`) is designed for rapid development. If you're changing the API every day, stay in `0.y.z` or work on a separate development branch for the next major version.

### If even tiny backward incompatible changes require a major version bump, won't I end up at version 42.0.0 very rapidly?

This is about responsible development. Incompatible changes should not be introduced lightly. The cost of upgrading can be significant. Having to bump major versions makes you think through the impact and evaluate the cost/benefit ratio.

### Documenting the entire public API is too much work!

It's your responsibility as a professional developer to properly document software intended for use by others. Managing software complexity is important, and that's hard to do if nobody knows how to use your software. In the long run, SemVer and a well-defined public API keep everything running smoothly.

### What do I do if I accidentally release a backward incompatible change as a minor version?

As soon as you realize you've broken the SemVer spec:
1. Fix the problem
2. Release a new minor version that corrects the problem and restores backward compatibility
3. Document the offending version
4. Inform users of the problem

**Never modify a versioned release.** Even in this circumstance, it's unacceptable to modify versioned releases.

### What should I do if I update my own dependencies without changing the public API?

This is considered compatible since it doesn't affect the public API. Determining whether it's a patch or minor level modification depends on whether you updated dependencies to:
- Fix a bug → PATCH increment
- Introduce new functionality → MINOR increment

### What if I inadvertently alter the public API in a way that is not compliant with the version number change?

Use your best judgment. If you have a huge audience that will be drastically impacted by changing the behavior back, it may be best to perform a major version release, even though the fix could strictly be considered a patch release. Remember, SemVer is about conveying meaning through version numbers.

### How should I handle deprecating functionality?

1. Update documentation to let users know about the change
2. Issue a new minor release with the deprecation in place
3. Before completely removing functionality in a new major release, there should be at least one minor release that contains the deprecation so users can smoothly transition

**Example:**
- `3.0.0`: Feature exists
- `3.1.0`: Feature deprecated (still works, but marked for removal)
- `4.0.0`: Feature removed

### Does SemVer have a size limit on the version string?

No, but use good judgment. A 255 character version string is probably overkill. Also, specific systems may impose their own limits.

### Is "v1.2.3" a semantic version?

No. "v1.2.3" is not a semantic version. However, prefixing a semantic version with a "v" is a common way to indicate it's a version number. The semantic version is `1.2.3`; `v1.2.3` is a tag name.

**Example:**
```bash
git tag v1.2.3 -m "Release version 1.2.3"
```
Here, `v1.2.3` is the tag name, and `1.2.3` is the semantic version.

---

## Tools and Validation

### Regular Expression for SemVer

**With named groups** (PCRE, Python, Go):
```
^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$
```

**With numbered groups** (JavaScript, PCRE, Python, Go):
```
^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$
```

### Online Tools

- **SemVer.org**: Official specification and FAQ
- **Regex101**: Test SemVer regex patterns
- **Semantic Versioning Validator**: Online validators available

### Python Libraries

- **semantic_version**: Python library for SemVer
- **packaging**: Python's packaging utilities (includes version parsing)

### Command-Line Tools

- **semver**: CLI tool for SemVer operations
- **git-semver**: Git integration for SemVer

---

## Summary

Semantic Versioning provides a clear, standardized way to version your software:

1. **Format**: `MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`
2. **Rules**: 
   - MAJOR for breaking changes
   - MINOR for new features (backward compatible)
   - PATCH for bug fixes (backward compatible)
3. **Principles**: 
   - Communicate meaning through version numbers
   - Never modify released versions
   - Document your public API
   - Be conservative with major versions

### Quick Reference

| Change Type | Version Increment | Example |
|------------|------------------|---------|
| Bug fix | PATCH | `3.0.0` → `3.0.1` |
| New feature | MINOR | `3.0.0` → `3.1.0` |
| Breaking change | MAJOR | `3.0.0` → `4.0.0` |
| Deprecation | MINOR | `3.0.0` → `3.1.0` |
| Pre-release | Add identifier | `3.1.0-beta.1` |

### Getting Help

When in doubt:
1. Review this guide
2. Consult [semver.org](https://semver.org/)
3. Ask me (the AI assistant) for guidance
4. Consider user impact
5. When uncertain, be conservative (prefer MAJOR over MINOR if unsure)

---

## References

- **Official Specification**: [https://semver.org/](https://semver.org/)
- **Git Tagging**: [https://git-scm.com/book/en/v2/Git-Basics-Tagging](https://git-scm.com/book/en/v2/Git-Basics-Tagging)
- **Keep a Changelog**: [https://keepachangelog.com/](https://keepachangelog.com/)

---

*This guide is based on Semantic Versioning 2.0.0. For the most up-to-date information, always refer to [semver.org](https://semver.org/).*

