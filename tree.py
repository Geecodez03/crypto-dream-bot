#!/usr/bin/env python3
import os
import fnmatch
from pathlib import Path
import argparse
from datetime import datetime
from typing import Optional, Set


class ProjectTree:
    """A beautiful project file tree viewer with smart filtering."""

    # Default exclusions (sets for O(1) lookups)
    DEFAULT_EXCLUDE_DIRS = {
        "node_modules",
        ".next",
        ".venv",
        "__pycache__",
        "dist",
        "build",
        "lib",
        ".git",
        ".idea",
        ".vscode",
        "venv",
        "env",
        ".github",
        "coverage",
        ".pytest_cache",
    }

    DEFAULT_EXCLUDE_FILES = {
        "*.tsbuildinfo",
        "*.lock",
        "*.d.ts",
        "*.mjs",
        "*.map",
        "*.log",
        "*.tmp",
        "*.bak",
        "*.pyc",
        "*.spec.js",
        "*.min.*",
        "*.DS_Store",
    }

    def __init__(self):
        self._init_colors()

    def _init_colors(self):
        """Initialize color support with fallback."""
        try:
            from colorama import init, Fore, Style

            init()
            self.colors = {
                "dir": Fore.BLUE,
                "file": Fore.GREEN,
                "size": Fore.YELLOW,
                "time": Fore.MAGENTA,
                "path": Fore.CYAN,
                "reset": Style.RESET_ALL,
            }
        except ImportError:
            self.colors = {
                k: "" for k in ["dir", "file", "size", "time", "path", "reset"]
            }

    def _format_size(self, size_bytes: float) -> str:
        """Convert bytes to human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024 or unit == "GB":
                return (
                    f"{size_bytes:6.2f} {unit}"
                    if unit != "B"
                    else f"{size_bytes:6.0f} {unit}"
                )
            size_bytes /= 1024
        return f"{size_bytes:6.2f} B"

    def _format_time(self, timestamp: float) -> str:
        """Format timestamp for display."""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

    def _print_header(self, path: Path):
        """Print the project header."""
        c = self.colors
        print(f"\n{c['path']}Project Tree: {path}{c['reset']}\n{'=' * 60}")

    def _print_item(
        self,
        name: str,
        item_type: str,
        size: Optional[int] = None,
        mtime: Optional[float] = None,
    ):
        """Print a directory or file entry with consistent formatting."""
        c = self.colors
        size_str = f"{self._format_size(size)}" if size is not None else ""
        time_str = f" {self._format_time(mtime)}" if mtime is not None else ""

        if item_type == "dir":
            print(f"{c['dir']}[D] {name.ljust(40)}{c['reset']}")
        else:
            print(
                f"{c['file']}[F] {name.ljust(40)}{c['size']}{size_str}{c['time']}{time_str}{c['reset']}"
            )

    def generate(
        self,
        path: Path = Path("."),
        max_depth: Optional[int] = None,
        show_hidden: bool = False,
        show_size: bool = True,
        show_time: bool = True,
        exclude_dirs: Optional[Set[str]] = None,
        exclude_files: Optional[Set[str]] = None,
    ):
        """
        Generate the project tree view.

        Args:
            path: Root directory path
            max_depth: Maximum recursion depth
            show_hidden: Include hidden files/dirs
            show_size: Show file sizes
            show_time: Show modification times
            exclude_dirs: Additional directories to exclude
            exclude_files: Additional file patterns to exclude
        """
        path = Path(path).resolve()
        exclude_dirs = self.DEFAULT_EXCLUDE_DIRS | (exclude_dirs or set())
        exclude_files = self.DEFAULT_EXCLUDE_FILES | (exclude_files or set())

        self._print_header(path)

        for root, dirs, files in os.walk(path):
            # Depth control
            current_depth = root[len(str(path)) :].count(os.sep)
            if max_depth is not None and current_depth >= max_depth:
                del dirs[:]
                continue

            # Filter directories
            dirs[:] = sorted(
                [
                    d
                    for d in dirs
                    if (
                        d not in exclude_dirs and (show_hidden or not d.startswith("."))
                    )
                ]
            )

            # Filter files
            files = sorted(
                [
                    f
                    for f in files
                    if not any(fnmatch.fnmatch(f, pat) for pat in exclude_files)
                    and (show_hidden or not f.startswith("."))
                ]
            )

            # Print current directory if it has contents
            rel_path = os.path.relpath(root, path)
            if rel_path != "." and (dirs or files):
                print(f"\n{self.colors['path']}[{rel_path}]{self.colors['reset']}")

            # Print directories
            for d in dirs:
                self._print_item(d, "dir")

            # Print files
            for f in files:
                file_path = Path(root) / f
                try:
                    stat = file_path.stat()
                    self._print_item(
                        f,
                        "file",
                        size=stat.st_size if show_size else None,
                        mtime=stat.st_mtime if show_time else None,
                    )
                except OSError:
                    self._print_item(f"{f} (access denied)", "file")


def main():
    parser = argparse.ArgumentParser(
        description="Beautiful project tree viewer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan")
    parser.add_argument("--depth", type=int, help="Max directory depth")
    parser.add_argument("--hidden", action="store_true", help="Show hidden files")
    parser.add_argument("--no-size", action="store_true", help="Hide file sizes")
    parser.add_argument("--no-time", action="store_true", help="Hide timestamps")
    parser.add_argument(
        "--add-exclude-dir", action="append", help="Additional directories to exclude"
    )
    parser.add_argument(
        "--add-exclude-file",
        action="append",
        help="Additional file patterns to exclude",
    )

    args = parser.parse_args()

    tree = ProjectTree()
    tree.generate(
        path=args.path,
        max_depth=args.depth,
        show_hidden=args.hidden,
        show_size=not args.no_size,
        show_time=not args.no_time,
        exclude_dirs=set(args.add_exclude_dir) if args.add_exclude_dir else None,
        exclude_files=set(args.add_exclude_file) if args.add_exclude_file else None,
    )


if __name__ == "__main__":
    main()
