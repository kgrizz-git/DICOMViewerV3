"""
File Explorer Utility

This module provides platform-specific functions to reveal files in the system
file explorer.

Inputs:
    - File paths to reveal
    
Outputs:
    - Opens file explorer and selects the specified file
    
Requirements:
    - subprocess module (standard library)
    - platform module (standard library)
    - os module (standard library)
"""

import subprocess
import platform
import os
from typing import Optional


def reveal_file_in_explorer(file_path: str) -> bool:
    """
    Open file explorer and select the specified file.
    
    Platform-specific behavior:
    - macOS: Opens Finder and reveals the file (selects it)
    - Windows: Opens File Explorer and selects the file
    - Linux: Attempts to use file manager with --select flag, falls back to opening parent directory
    
    Args:
        file_path: Path to file to reveal (must be absolute or relative path)
        
    Returns:
        True if successful, False otherwise
        
    Note:
        If file doesn't exist, the function will still attempt to reveal it
        (the file manager may show an error or the parent directory)
    """
    if not file_path:
        return False
    
    # Convert to absolute path for consistency
    try:
        abs_path = os.path.abspath(file_path)
    except (OSError, ValueError):
        return False
    
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            # Use 'open -R' to reveal file in Finder
            subprocess.run(['open', '-R', abs_path], check=True)
            return True
            
        elif system == "Windows":
            # Use explorer with /select flag to select the file
            # Note: /select, requires a comma after /select
            subprocess.run(['explorer', '/select,', abs_path], check=True)
            return True
            
        else:  # Linux and other Unix-like systems
            # Try file manager-specific commands with --select flag
            # Nautilus (GNOME)
            try:
                subprocess.run(['nautilus', '--select', abs_path], check=True, timeout=5)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Dolphin (KDE)
            try:
                subprocess.run(['dolphin', '--select', abs_path], check=True, timeout=5)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Thunar (XFCE)
            try:
                subprocess.run(['thunar', '--select', abs_path], check=True, timeout=5)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Fallback: open parent directory with xdg-open
            try:
                parent_dir = os.path.dirname(abs_path)
                if parent_dir:
                    subprocess.run(['xdg-open', parent_dir], check=True, timeout=5)
                    return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            return False
            
    except subprocess.CalledProcessError:
        # Command failed
        return False
    except FileNotFoundError:
        # Command not found (e.g., file manager not installed)
        return False
    except Exception:
        # Any other error
        return False

