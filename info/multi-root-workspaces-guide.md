# Multi-Root Workspaces Guide

## Overview

Yes, you can add folders or files outside the main project folder to a workspace in VS Code/Windsurf. This is done through **multi-root workspaces**.

## What it means to add external folders/files:

**Multi-root workspace** allows you to work with multiple project folders that may not be stored inside the same parent directory on disk. You can pick folders from anywhere on your system to add to the workspace.

## How to add external folders:

### 1. File Menu Method
- Go to **File > Add Folder to Workspace**
- Select any folder from your system

### 2. Drag and Drop Method
- Drag folders directly into the File Explorer
- You can drag multiple folders at once
- Note: Dropping a single folder into the editor region opens it in single-folder mode
- Dropping multiple folders creates a new multi-root workspace

### 3. Command Line Method
```bash
code --add folder1 folder2
```

### 4. Multiple Selection Method
- Use your platform's native file open dialog
- Select multiple folders to create a multi-root workspace

## What this enables:

### Cross-Project Development
- Work on related projects simultaneously
- Switch between projects without losing context

### Shared Libraries
- Include common dependencies used by multiple projects
- Reference shared components or utilities

### Independent Configurations
- Each folder maintains its own settings, tasks, and debug configurations
- Folder-specific settings override global workspace settings

### Git Integration
- Each folder can have its own git repository
- Independent version control per project

## Workspace File Structure

When you create a multi-root workspace, VS Code generates a `.code-workspace` JSON file:

```json
{
  "folders": [
    { "path": "my-folder-a" },
    { "path": "my-folder-b" }
  ]
}
```

### Advanced Workspace Configuration

You can customize each folder with additional settings:

```json
{
  "folders": [
    {
      "path": "frontend",
      "name": "Frontend App"
    },
    {
      "path": "backend",
      "name": "Backend API"
    },
    {
      "path": "../shared-lib",
      "name": "Shared Library"
    }
  ],
  "settings": {
    "files.exclude": {
      "**/node_modules": true
    }
  },
  "extensions": {
    "recommendations": [
      "ms-vscode.vscode-typescript-next"
    ]
  }
}
```

## Use Cases

### Monorepos
- Manage multiple packages in a single repository
- Shared build tools and configurations

### Microservices Architecture
- Develop multiple services simultaneously
- Shared configuration and deployment scripts

### Related Projects
- Frontend and backend of the same application
- Documentation alongside source code

### Template Development
- Work with template files and implementation files
- Reference examples and documentation

## Removing Folders

- Right-click on any root folder in the File Explorer
- Select **Remove Folder from Workspace**
- Or use the context menu command

## Best Practices

1. **Organize logically** - Group related projects together
2. **Use descriptive names** - Rename folders for clarity
3. **Workspace settings** - Configure shared settings at the workspace level
4. **Folder-specific settings** - Override settings per folder when needed
5. **Save workspace** - Save your workspace configuration for future use

## Common Questions

### Can I use a multi-root workspace without folders?
No, a workspace must have at least one folder.

### What's the difference between single-folder and multi-root workspaces?
- **Single-folder**: Opens one folder as the workspace
- **Multi-root**: Opens a `.code-workspace` file that references multiple folders

### How do I know if I'm in a multi-root workspace?
Look for "(Workspace)" suffix next to folder names in the File Explorer.

### Can I have different git repositories?
Yes, each folder can have its own independent git repository.
