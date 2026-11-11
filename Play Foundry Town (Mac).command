#!/bin/bash
# Double-click this file in Finder to play Foundry Town on macOS.
cd "$(dirname "$0")" || exit 1

# Apple's built-in Python uses Tk 8.5, which draws a black window on recent macOS.
# Look for a Python with Tk 8.6 or newer first.
candidates=()
for uv in uv "$HOME/.local/bin/uv" /opt/homebrew/bin/uv; do
    if command -v "$uv" >/dev/null 2>&1; then
        found=$("$uv" python find '>=3.10' 2>/dev/null) && candidates+=("$found")
        break
    fi
done
candidates+=(
    /Library/Frameworks/Python.framework/Versions/Current/bin/python3
    /opt/homebrew/bin/python3
    /usr/local/bin/python3
    python3
)

for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c "import tkinter, sys; sys.exit(tkinter.TkVersion < 8.6)" >/dev/null 2>&1; then
        exec "$candidate" tycoon.py
    fi
done

echo "Foundry Town needs Python 3 with a modern Tk (8.6 or newer)."
echo "Apple's built-in Python is too old and shows a black window."
echo
echo "Fix it with one of these:"
echo "  - If you have uv:  uv python install 3.12"
echo "  - Or install Python from https://www.python.org/downloads/macos/"
echo
read -r -p "Press Return to close."
