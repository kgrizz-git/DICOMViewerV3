# Generalized Project Assessment Templates

**Version**: 2.0  
**Last Updated**: 2026-02-18

## Overview

This directory contains **generalized, language-agnostic versions** of project assessment templates that work with any software project, regardless of programming language, framework, or project structure. These templates provide systematic approaches for assessing code quality, security, documentation, testing, and project management.

## Available Templates

### 1. **doc-assessment-template.md**
Systematic approach to assess documentation accuracy, agreement, and completeness against the actual codebase.

**Use for:** Verifying that project documentation correctly describes features, configuration, installation procedures, and system requirements.

### 2. **doc-refactor-assessment-template.md**
Framework for evaluating documentation organization and identifying opportunities to merge, split, rename, or restructure documentation files.

**Use for:** Improving documentation structure and ensuring content is appropriately distributed across files.

### 3. **functionality-integrity-assessment-template.md**
Comprehensive checklist for verifying that all code functionality works as intended and matches documented behavior.

**Use for:** Testing and validating core functionality, configuration systems, error handling, and edge cases.

### 4. **future-and-remaining-assessment-template.md** (COMPLETELY REWRITTEN in v2.0)
Template for scanning and verifying TODO, Future Enhancements, Roadmap, and other future work documentation files to ensure they're up-to-date.

**Use for:** Verifying completion status matches implementation, tracking remaining work, and keeping future work documentation current.

### 5. **qi-assessment-template.md** (Quality Improvement Assessment)
Holistic quality assessment covering code quality, documentation, testing, safety, and maintainability.

**Use for:** Comprehensive quality reviews and identifying areas for improvement across all aspects of a project.

### 6. **refactor-assessment-template.md**
Systematic approach to analyze code files for refactoring opportunities, especially for files exceeding size thresholds.

**Use for:** Identifying code that should be broken into smaller, more maintainable modules.

### 7. **safety-scan-template.md** (COMPLETELY REWRITTEN in v2.0)
Comprehensive security and safety vulnerability scanning covering injection attacks, authentication, data exposure, file operations, and dependency vulnerabilities.

**Use for:** Security audits, identifying vulnerabilities, and ensuring safe coding practices. Works with any programming language.

### 8. **scan-general-reusable-info-template.md**
Template for identifying and cataloging reusable documentation and information that could benefit other projects.

**Use for:** Extracting generalizable patterns and creating portable documentation.

### 9. **testing-assessment-template.md**
Comprehensive testing assessment identifying what tests are needed, categorizing by automation feasibility, and prioritizing critical testing needs.

**Use for:** Planning testing strategies and identifying test coverage gaps.

## How to Use These Templates

### Step 1: Adapt Templates to Your Project

Each template uses **placeholder syntax** in square brackets that you should replace with your project-specific values:

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `[PROJECT_NAME]` | Your project name | "File Manager Pro", "API Server" |
| `[MAIN_SCRIPT].sh` | Your main entry point script | `server.sh`, `app-launcher.sh` |
| `[INSTALL_SCRIPT].sh` | Installation script name | `install.sh`, `setup.sh` |
| `[UNINSTALL_SCRIPT].sh` | Uninstallation script name | `uninstall.sh`, `cleanup.sh` |
| `[CONFIGURE_SCRIPT].sh` | Configuration script name | `configure.sh`, `config.sh` |
| `[MANAGE_SCRIPT].sh` | Management/admin script name | `manage.sh`, `admin.sh` |
| `[LIB_DIR]/` | Library/module directory | `lib/`, `src/`, `modules/` |
| `[DEV_DOCS]/` | Developer documentation directory | `dev-docs/`, `docs/dev/`, `.dev/` |
| `[CONFIG_DIR]/` | Configuration directory | `~/.config/myapp/`, `/etc/myapp/` |
| `[CONFIG_FILE_PATH]` | Full path to config file | `~/.config/myapp/config.ini` |
| `[INSTALL_DIR]/` | Installation directory | `~/.local/bin/`, `/usr/local/bin/` |
| `[LOG_DIR]/` | Log file directory | `~/.local/share/myapp/logs/` |
| `[INIT_SYSTEM]` | Init system (systemd, etc.) | `systemd`, `init.d`, `launchd` |
| `[SYSTEMD_DIR]/` | Systemd unit file directory | `~/.config/systemd/user/` |
| `[MODULE_NAME].sh` | Library module name | `database.sh`, `api.sh` |
| `[ENHANCEMENT_NAME]` | Feature/enhancement identifier | "Feature #42", "Enhancement 2.1" |

### Step 2: Copy Template to Your Project

```bash
# Create assessment directories in your project
mkdir -p dev-docs/templates
mkdir -p dev-docs/doc-assessments
mkdir -p dev-docs/refactor-assessments
mkdir -p dev-docs/testing-assessments
mkdir -p dev-docs/quality-assessments

# Copy desired template
cp path/to/generalized/doc-assessment-template.md dev-docs/templates/
```

### Step 3: Create Timestamped Assessment Copies

When performing an assessment, create a timestamped copy as instructed in each template:

```bash
# Example for documentation assessment
cp dev-docs/templates/doc-assessment-template.md \
   "dev-docs/doc-assessments/doc-assessment-$(date +%Y-%m-%d-%H%M%S).md"
```

### Step 4: Perform Assessment

- Work only with the timestamped copy (not the template)
- Fill in analysis sections
- Check off completed items
- Document findings thoroughly
- Keep the master template unchanged for future use

## Customization for Different Project Types

### For Non-Shell Script Projects

If your project isn't primarily shell scripts:

- Replace `.sh` script references with your file extensions (`.py`, `.js`, `.go`, etc.)
- Adapt library/module references to your project structure
- Modify init system references if not using systemd
- Adjust file paths and directory structures to match your conventions

### For Projects Without Certain Components

Some templates assume certain project structures:

- **No install scripts:** Skip or remove sections about installation procedures
- **No systemd integration:** Remove or replace systemd-specific sections
- **Different documentation structure:** Adapt document names and organization
- **Different testing approach:** Modify testing templates to match your framework

### Adding Project-Specific Sections

Feel free to extend templates with sections specific to your project:

- Add technology-specific checks (database migrations, API endpoints, etc.)
- Include domain-specific validation (e.g., financial calculations, data privacy)
- Add compliance or regulatory requirements
- Include platform-specific considerations

## Template Philosophy

These templates follow several key principles:

### 1. **Assessment-Only Approach**
Templates are designed for **analysis and documentation**, not immediate implementation. This ensures:
- All issues are documented before changes are made
- Teams can prioritize which issues to address
- Assessment results provide complete picture of project state
- Analysis isn't mixed with implementation changes

### 2. **Timestamped Copies**
Always work with timestamped copies, keeping master templates unchanged. This provides:
- Historical record of assessments over time
- Ability to track improvement trends
- Clean master templates for future assessments

### 3. **Comprehensive Checklists**
Each template includes detailed checklists to ensure thorough coverage and prevent overlooked areas.

### 4. **Prioritization Framework**
Templates include criteria for prioritizing findings (High/Medium/Low priority) to guide remediation efforts.

### 5. **Structured Results**
Standard result formats make findings easy to review and act upon.

## Directory Structure Recommendations

Suggested directory structure when using these templates:

```
your-project/
├── dev-docs/
│   ├── templates/                    # Master templates (unchanged)
│   │   ├── doc-assessment-template.md
│   │   ├── refactor-assessment-template.md
│   │   └── ...
│   ├── doc-assessments/              # Documentation assessment results
│   │   ├── doc-assessment-2024-01-15-143022.md
│   │   └── doc-assessment-2024-02-07-091530.md
│   ├── refactor-assessments/         # Refactor assessment results
│   ├── testing-assessments/          # Testing assessment results
│   ├── quality-assessments/          # QI assessment results
│   ├── safety-scans/                 # Safety scan results
│   └── functionality-assessments/    # Functionality integrity results
└── ...
```

## Best Practices

### Regular Assessments

- Run documentation assessments after significant code changes
- Perform refactor assessments when files grow beyond maintainability thresholds
- Conduct safety scans before major releases
- Execute quality assessments periodically (monthly/quarterly)

### Team Collaboration

- Share assessment results with the team before implementation
- Discuss high-priority findings in team meetings
- Assign remediation tasks based on assessment priorities
- Track assessment metrics over time to measure improvement

### Continuous Improvement

- Update master templates when you discover new assessment patterns
- Customize templates as you learn what works for your project
- Document lessons learned from each assessment
- Refine prioritization criteria based on experience

## Version History

- **Version 2.0** (2026-02-18): Complete generalization for any programming language
  - Made all templates language-agnostic (work with Python, JavaScript, Java, C++, Go, Rust, etc.)
  - Added language-specific threshold table to refactor template
  - **Completely rewrote** `safety-scan-template.md` for general security vulnerability scanning
  - **Completely rewrote** `future-and-remaining-assessment-template.md` for TODO/future work tracking
  - Moved version info to top of each template file
  - Added automatic backup file exclusion to all templates
  - Standardized structure across all templates
  - Updated all templates to version 2.0
  - See `GENERALIZATION_SUMMARY.md` for detailed changes

- **Version 1.0** (2024-02-07): Initial generalized versions
  - Removed project-specific references
  - Added comprehensive placeholder system
  - Maintained assessment methodologies and structures

## Contributing Improvements

If you adapt these templates and discover improvements:

1. Document the improvement in your project's templates
2. Consider whether it would benefit other projects
3. Update this README with lessons learned
4. Share improvements back to the community

## License

These templates are provided as-is for use in any project. Modify and adapt as needed for your specific requirements.

## Questions or Issues?

If you find issues with these templates or have suggestions for improvement:
- Document what worked and what didn't for your project
- Note any missing sections or unnecessary complexity
- Share feedback on clarity and usability

---

**Remember:** These are **starting points**, not rigid requirements. Adapt them to serve your project's needs effectively.
