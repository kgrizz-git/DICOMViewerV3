# Refactor Assessment Template

## Purpose
This template provides a systematic framework for assessing code refactoring opportunities in a software project. Use this template to identify technical debt, code smells, and improvement opportunities before undertaking refactoring work.

## Instructions
1. Copy this template to create a new refactor assessment document
2. Fill out each section based on your analysis of the target codebase
3. Prioritize identified issues based on impact and effort
4. Use the assessment to create an actionable refactoring plan

---

## Assessment Information

### Project/Module Information
- **Project Name**: [Name of the project]
- **Module/Component**: [Specific module or "Full Project" if assessing entire codebase]
- **Assessment Date**: [Date]
- **Assessor**: [Name or role]
- **Assessment Scope**: [Brief description of what is being assessed]

### Current State Overview
**Brief Description**: [1-2 paragraphs describing the current state of the codebase/module]

**Technology Stack**:
- Language(s): [List]
- Frameworks: [List]
- Key Dependencies: [List]

---

## Code Quality Assessment

### 1. Architecture and Design Patterns

**Current Architecture**: [Describe the current architectural approach - MVC, layered, modular, etc.]

**Identified Issues**:
- [ ] [Issue description]
- [ ] [Issue description]

**Improvement Opportunities**:
- [ ] [Opportunity description]

### 2. Code Organization and Structure

**Current Organization**: [Describe how code is organized - file structure, module separation, etc.]

**Identified Issues**:
- [ ] Large files/classes (list files > 500 lines)
- [ ] Poor module separation
- [ ] Circular dependencies
- [ ] Other: [Specify]

**Improvement Opportunities**:
- [ ] [Opportunity description]

### 3. Code Smells and Anti-Patterns

Identify specific code smells present in the codebase:

**High Priority**:
- [ ] Duplicated Code: [Location and description]
- [ ] Long Methods/Functions: [List methods > 50 lines]
- [ ] Large Classes: [List classes > 500 lines]
- [ ] God Objects: [Objects with too many responsibilities]
- [ ] Other: [Specify]

**Medium Priority**:
- [ ] Feature Envy: [Description]
- [ ] Inappropriate Intimacy: [Description]
- [ ] Primitive Obsession: [Description]
- [ ] Dead Code: [Location]
- [ ] Other: [Specify]

**Low Priority**:
- [ ] Lazy Class: [Description]
- [ ] Comments (excessive or outdated): [Location]
- [ ] Inconsistent Naming: [Examples]
- [ ] Other: [Specify]

### 4. Maintainability Issues

**Complexity**:
- [ ] High cyclomatic complexity functions: [List with complexity scores if available]
- [ ] Deep nesting levels: [Examples]
- [ ] Complex conditionals: [Examples]

**Readability**:
- [ ] Poor naming conventions: [Examples]
- [ ] Lack of comments where needed: [Locations]
- [ ] Inconsistent code style: [Examples]

**Modularity**:
- [ ] Tight coupling: [Examples]
- [ ] Low cohesion: [Examples]
- [ ] Hard-coded values: [Examples]

### 5. Testing and Test Coverage

**Current State**:
- Test Coverage: [Percentage if known, or "Unknown"]
- Testing Framework: [Name]
- Types of Tests: [Unit, Integration, E2E, etc.]

**Issues**:
- [ ] Low test coverage areas: [List]
- [ ] Brittle tests: [Examples]
- [ ] Slow tests: [Examples]
- [ ] Missing test types: [What's missing]
- [ ] Hard-to-test code: [Examples]

**Improvement Opportunities**:
- [ ] [Opportunity description]

### 6. Performance Issues

**Identified Issues**:
- [ ] Memory leaks: [Location]
- [ ] Inefficient algorithms: [Location]
- [ ] Unnecessary computations: [Location]
- [ ] Database/API call inefficiencies: [Location]
- [ ] Other: [Specify]

### 7. Security Concerns

**Identified Issues**:
- [ ] Input validation gaps: [Location]
- [ ] Authentication/Authorization issues: [Description]
- [ ] Data exposure risks: [Location]
- [ ] Dependency vulnerabilities: [List]
- [ ] Other: [Specify]

### 8. Documentation

**Current State**:
- [ ] Code comments: [Assessment - Adequate/Inadequate/Excessive]
- [ ] API documentation: [Status]
- [ ] Architecture documentation: [Status]
- [ ] Setup/deployment documentation: [Status]

**Issues**:
- [ ] [Issue description]

---

## Dependency Analysis

### Dependencies Health
- [ ] Outdated dependencies: [List with current and latest versions]
- [ ] Deprecated dependencies: [List]
- [ ] Unused dependencies: [List]
- [ ] Security vulnerabilities: [List with severity]

### Dependency Management
- [ ] Clear dependency declaration: [Yes/No/Partial]
- [ ] Version pinning strategy: [Describe]
- [ ] Dependency conflicts: [List if any]

---

## Technical Debt Inventory

### High Priority Technical Debt
1. [Description] - Impact: [High/Medium/Low], Effort: [High/Medium/Low]
2. [Description] - Impact: [High/Medium/Low], Effort: [High/Medium/Low]

### Medium Priority Technical Debt
1. [Description] - Impact: [High/Medium/Low], Effort: [High/Medium/Low]
2. [Description] - Impact: [High/Medium/Low], Effort: [High/Medium/Low]

### Low Priority Technical Debt
1. [Description] - Impact: [High/Medium/Low], Effort: [High/Medium/Low]

---

## Refactoring Recommendations

### Immediate Actions (High Priority)
1. **[Refactoring Name]**
   - **Issue**: [What problem this addresses]
   - **Proposed Solution**: [How to refactor]
   - **Technique**: [Extract Method, Rename, etc.]
   - **Files Affected**: [List]
   - **Estimated Effort**: [Hours/Days]
   - **Risk Level**: [High/Medium/Low]
   - **Dependencies**: [Any blocking items]

### Short-term Actions (Medium Priority)
[Same format as above]

### Long-term Actions (Low Priority)
[Same format as above]

---

## Success Metrics

### Quality Metrics
- [ ] Reduce cyclomatic complexity to < [target]
- [ ] Achieve test coverage of [target]%
- [ ] Reduce file size average to < [target] lines
- [ ] Eliminate all high-severity code smells

### Performance Metrics
- [ ] Improve [specific operation] performance by [target]%
- [ ] Reduce memory usage by [target]%
- [ ] Other: [Specify]

### Maintainability Metrics
- [ ] Reduce time to onboard new developers to [target]
- [ ] Reduce average bug fix time to [target]
- [ ] Other: [Specify]

---

## Risk Assessment

### Refactoring Risks
- **High Risk Areas**: [List parts of code that are critical or fragile]
- **Dependencies**: [External systems or modules affected]
- **Rollback Plan**: [How to revert if issues arise]
- **Testing Strategy**: [How to ensure no regressions]

---

## Implementation Plan

### Phase 1: Preparation
- [ ] Set up version control branch
- [ ] Ensure comprehensive test coverage in refactoring areas
- [ ] Document current behavior
- [ ] Review plan with team

### Phase 2: Execution
- [ ] [Specific refactoring task]
- [ ] [Specific refactoring task]
- [ ] Run tests after each change
- [ ] Code review each change

### Phase 3: Validation
- [ ] Run full test suite
- [ ] Performance testing
- [ ] Security review
- [ ] Documentation updates

### Phase 4: Deployment
- [ ] Deploy to staging
- [ ] Smoke testing
- [ ] Production deployment
- [ ] Monitor for issues

---

## Timeline

| Phase | Task | Estimated Duration | Dependencies | Assignee |
|-------|------|-------------------|--------------|----------|
| [Phase] | [Task] | [Duration] | [Dependencies] | [Person] |

---

## Collaboration and Review

### Stakeholders
- **Technical Lead**: [Name]
- **Reviewers**: [Names]
- **QA**: [Names]
- **Product Owner**: [Name]

### Review Checkpoints
1. [Checkpoint description and date]
2. [Checkpoint description and date]

---

## Notes and Additional Context

[Any additional information, constraints, or context that doesn't fit in the sections above]

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| [Date] | [Change description] | [Name] |

---

## Appendix

### Tools Used for Assessment
- [ ] Static analysis tools: [List]
- [ ] Code coverage tools: [List]
- [ ] Complexity analyzers: [List]
- [ ] Other: [List]

### References
- [Link to related documentation]
- [Link to code standards]
- [Link to architectural decisions]
