# PDF Annotation Workspace (Linux)

A professional, UX-first PDF annotation tool built with Python, GTK 4, and Libadwaita.

## Setup & Installation

### 1. System Dependencies
This application requires GTK 4, Libadwaita, Poppler, and Cairo development headers.

**Fedora / RHEL:**
```bash
sudo dnf install gtk4-devel libadwaita-devel python3-gobject python3-cairo poppler-glib-devel cairo-devel
```

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install libgtk-4-dev libadwaita-1-dev python3-gi python3-full python3-cairo libcairo2-dev libgirepository1.0-dev libpoppler-glib-dev gir1.2-poppler-0.18
```

### 2. Python Environment
Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install PyGObject pycairo
```

## Running the Application

To start the application from the project root:

```bash
# Set PYTHONPATH to include the src directory
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Run the entry point
python3 src/pdf_app/main.py
```

## Project Structure
- `src/pdf_app/`: Main source code
    - `ui/`: GTK 4 widgets and window classes
    - `document/`: PDF loading and rendering logic
    - `utils/`: Helper functions
- `assets/`: Icons and resources
