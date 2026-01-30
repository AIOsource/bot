"""
Cleanup script to organize project structure.
Removes documentation files and unused directories.
"""
import os
import shutil
from pathlib import Path

# Get project directory
project_dir = Path(__file__).parent

print("🧹 Cleaning up project...")

# Remove all .md files
md_files = list(project_dir.glob("*.md"))
for md_file in md_files:
    try:
        md_file.unlink()
        print(f"  ✓ Removed: {md_file.name}")
    except Exception as e:
        print(f"  ✗ Error removing {md_file.name}: {e}")

# Remove src directory (empty/unused)
src_dir = project_dir / "src"
if src_dir.exists():
    try:
        shutil.rmtree(src_dir)
        print(f"  ✓ Removed: src/")
    except Exception as e:
        print(f"  ✗ Error removing src/: {e}")

# Remove .docx file
docx_file = project_dir / "тз этап 1.docx"
if docx_file.exists():
    try:
        docx_file.unlink()
        print(f"  ✓ Removed: тз этап 1.docx")
    except Exception as e:
        print(f"  ✗ Error removing docx: {e}")

print("\n✅ Cleanup complete!")
print("\n📁 Final project structure:")
print("=" * 50)

# Show final structure
core_files = [
    "main.py",
    "config.py",
    "models.py",
    "database.py",
    "news_collector.py",
    "ai_filter.py",
    "telegram_bot.py",
    "utils.py",
    "requirements.txt",
    ".env",
    ".env.example",
    ".gitignore"
]

for file in core_files:
    file_path = project_dir / file
    if file_path.exists():
        if file_path.is_file():
            size = file_path.stat().st_size
            print(f"  ✓ {file} ({size:,} bytes)")
        else:
            print(f"  ✓ {file}")
    else:
        print(f"  ✗ {file} (missing)")

print("=" * 50)
