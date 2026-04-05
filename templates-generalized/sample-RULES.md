# Sample rules

This file records rules to be applied when working in this project: user (global) rules and project-scoped (workspace) rules.

---

## User rules (global)

- **Shell commands / tests**: When running shell commands like running tests, use timeout or similar approaches when possible—the time can be high if appropriate (e.g. up to 300 seconds). Notify if more time is appropriate.

- **Semantic versioning and changelog**: Use semantic versioning and keep a changelog; set up any required files and subfolders. Whenever you make changes in the codebase, decide if an entry needs to be made in the changelog and add any necessary notes regarding impact for semantic versioning.

- **Moving content / refactoring**: When moving content from one file to another, do not remove it from the source file until it is verified to be present in the target file. When refactoring code files, make a backup of any code files that will be modified in the backups subfolder before making any changes.

- **Tests**: When running tests, do not edit them or change the approach to force them to pass artificially. Give frequent updates on findings during testing and explain the next steps and confirm. If a test fails, do not edit the test and rerun without first explaining why you think it failed and what you propose to edit.

- **Test scripts**: Put any scripts created solely for running tests in a tests subfolder.

- **Git push**: Never try to push a commit to GitHub without being asked. You can ask if the user wants to, but do not try to do it on your own initiative.

- **Checklist items**: When implementing a plan with checklist items, mark items as complete only after they have been explicitly and fully completed and confirmed. If there are problems completing an item, add comments to that checklist item and report them, but do not change the goal of the checklist item or settle for a workaround that does not achieve the stated task.

- **Venv**: Before running shell commands, check if a venv exists for the project. If it does, activate the venv before running shell commands.

- **Branches**: If asked to commit to git or push a project to GitHub, and there is more than one branch, ask which branch to use unless one is stated explicitly (and it exists).

- **Libraries / APIs**: When unsure how a library or API works (e.g. when saying “xxx code MAY be doing yyy”), search online for documentation rather than guessing.

- **Existing functionality**: When editing code, do not sacrifice any existing features or break any existing functionality without confirming unless explicitly told to do so.

- **Documentation**: Update documentation such as README, AGENTS, and requirements when relevant changes are made to the code or when given a new rule for the project.

- **New projects**: When creating a new project, set up a project folder including a README.md, an AGENTS.md, a requirements.txt, and git / GitHub support. When committing and pushing to GitHub, write verbose and descriptive comments. Use diffs to thoroughly evaluate changes since last commit. Ignore virtual environments in git.

- **Code documentation**: Document code clearly and extensively: some comments at the top indicating what the code does overall, what inputs it takes, what outputs it creates, and what requirements are needed; plus docstrings and comments throughout for classes, methods, and other sections.

- **Senior developer practices**: Act as a senior developer with experience in Python, Rust, JavaScript, C++, C#, CSS, HTML, Swift, and Flutter; implement industry best practices; consider flow of relevant code and all possible causes; pay attention to security vulnerabilities and edge cases.

- **Ambiguity**: If there is ambiguity in what is being asked or more information or clarification is needed, ask the user or check sources for conclusive data rather than make assumptions or guesses.

- **File dialogs / popups**: Any file selection dialogs or popup windows displayed to the user should initially appear in focus and on top of any other open windows so the user sees them right away. They should not stay on top if another window is selected.

- **Modular design**: Use modular design. Methods and functions should do only one thing where possible. Try to keep individual files to under 500–1000 lines. Avoid redundancies or unnecessary code (unless commented out).

- **Source**: `no-inline-imports` (always apply)
- Always place imports at the top of the module. Avoid inline imports in function bodies, type annotations, or interface fields unless there is a strict circular-dependency reason and it is documented.

---

*Last consolidated from user rules and workspace rules. Update this file when rules change.*
