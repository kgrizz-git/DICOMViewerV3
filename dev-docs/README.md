# Development Documentation

This directory contains internal development documentation, templates, and assessments for the DICOM Viewer V3 project.

## Contents

### Assessments

- **[REFACTOR_ASSESSMENT_2026-02.md](REFACTOR_ASSESSMENT_2026-02.md)** - Comprehensive refactor assessment of the codebase conducted in February 2026
  - Identifies technical debt, code smells, and improvement opportunities
  - Provides prioritized refactoring recommendations
  - Includes 10-week implementation plan

### Templates

- **[templates-generalized/](templates-generalized/)** - Reusable templates for development processes
  - **[refactor-assessment-template.md](templates-generalized/refactor-assessment-template.md)** - Template for conducting code refactor assessments

## Purpose

The `dev-docs/` directory serves as a repository for:

1. **Code Quality Assessments** - Systematic evaluations of code quality, architecture, and technical debt
2. **Development Templates** - Standardized templates for common development tasks
3. **Internal Planning Documents** - Planning documents that are not part of user-facing documentation
4. **Technical Analyses** - Deep-dive technical analyses that guide development decisions

## Directory Structure

```
dev-docs/
├── README.md                           # This file
├── REFACTOR_ASSESSMENT_2026-02.md     # Latest refactor assessment
└── templates-generalized/              # Reusable templates
    └── refactor-assessment-template.md # Refactor assessment template
```

## How to Use

### For Refactor Assessments

1. Copy `templates-generalized/refactor-assessment-template.md` to a new file (e.g., `REFACTOR_ASSESSMENT_YYYY-MM.md`)
2. Fill out each section based on your analysis of the codebase
3. Prioritize identified issues based on impact and effort
4. Create an actionable implementation plan
5. Use the assessment to guide refactoring work

### For Contributors

If you're working on refactoring or code quality improvements:
1. Review the latest refactor assessment to understand known issues
2. Check recommendations and priorities before starting work
3. Update the assessment or create a new one after major refactoring

## Relationship to docs/

The main `docs/` directory contains **user-facing** and **deployment** documentation:
- Building executables
- Code signing
- Feature documentation
- Implementation plans for user features

The `dev-docs/` directory contains **internal development** documentation:
- Code quality assessments
- Refactoring plans
- Development templates
- Technical debt tracking

---

**Note**: Documentation in this directory is primarily for developers and maintainers of the DICOM Viewer V3 project.
