import json
import uuid
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple

@dataclass
class Annotation:
    id: str
    type: str  # 'highlight', 'underline', 'text'
    page_index: int
    rects: List[Tuple[float, float, float, float]]  # List of [x, y, w, h] in PDF points
    color: Tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.4) # RGBA
    content: str = ""
    style: str = "standard" # for text annotations
    created_at: str = "" # ISO timestamp

    @classmethod
    def create(cls, type: str, page_index: int, rects: List[Tuple[float, float, float, float]], 
               color: Tuple[float, float, float, float] = None, content: str = ""):
        
        # Default Colors
        if color is None:
            if type == 'highlight':
                color = (1.0, 1.0, 0.0, 0.4) # Yellow
            elif type == 'underline':
                color = (1.0, 0.0, 0.0, 1.0) # Red
            else:
                color = (0.0, 0.0, 0.0, 1.0) # Black text
                
        return cls(
            id=str(uuid.uuid4()),
            type=type,
            page_index=page_index,
            rects=rects,
            color=color,
            content=content
        )

class AnnotationStore:
    def __init__(self):
        self.annotations: List[Annotation] = []
        self.file_path: Optional[str] = None
        self._is_dirty: bool = False 
        self.on_dirty_changed = None # Callback function(is_dirty: bool)
        
        # Undo/Redo stacks store tuples: (operation, annotation)
        self._undo_stack: List[tuple] = []
        self._redo_stack: List[tuple] = []

    @property
    def is_dirty(self):
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, value: bool):
        print(f"DEBUG: is_dirty changed to {value}")
        self._is_dirty = value
        if self.on_dirty_changed:
            self.on_dirty_changed(value)
        
    def get_fingerprint(self, pdf_path: str) -> str:
        """Generates a simple fingerprint for the PDF file."""
        import hashlib
        try:
            stat = os.stat(pdf_path)
            with open(pdf_path, 'rb') as f:
                header = f.read(4096) # Read first 4KB
            
            hasher = hashlib.md5()
            hasher.update(str(stat.st_size).encode('utf-8'))
            hasher.update(str(stat.st_mtime).encode('utf-8'))
            hasher.update(header)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error generating fingerprint: {e}")
            return "unknown"

    def save_to_file(self, path: str, pdf_path: str):
        """Saves project to a specific JSON file."""
        fingerprint = self.get_fingerprint(pdf_path)
        data = {
            "format_version": 1,
            "pdf_fingerprint": fingerprint,
            "annotations": [asdict(ann) for ann in self.annotations]
        }
        
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved project to {path}")
            self.is_dirty = False
        except Exception as e:
            print(f"Error saving project: {e}")
            raise e

    def load_from_file(self, path: str, pdf_path: str) -> bool:
        """Loads project from JSON. Returns False if fingerprint mismatch."""
        if not os.path.exists(path):
            return False
            
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # version check (future proofing)
            version = data.get("format_version", 1)
            
            # fingerprint check
            saved_fingerprint = data.get("pdf_fingerprint", "")
            current_fingerprint = self.get_fingerprint(pdf_path)
            
            mismatch = False
            if saved_fingerprint != current_fingerprint:
                print(f"WARNING: Fingerprint mismatch! Saved: {saved_fingerprint}, Current: {current_fingerprint}")
                mismatch = True
                
            self.annotations = []
            for item in data.get('annotations', []):
                # Backwards compat: If ID missing, generate one
                if 'id' not in item: item['id'] = str(uuid.uuid4())
                
                ann = Annotation(**item)
                ann.color = tuple(ann.color)
                ann.rects = [tuple(r) for r in ann.rects]
                self.annotations.append(ann)
                
            self._undo_stack.clear()
            self._redo_stack.clear()
            self.is_dirty = False
            print(f"Loaded {len(self.annotations)} annotations from {path}")
            
            return mismatch # Returns True if there was a mismatch (Warning needed)
            
        except Exception as e:
            print(f"Error loading project: {e}")
            raise e
        
    def load(self, pdf_path: str):
        """Loads annotations from a sidecar JSON file (pdf_path + .json)."""
        self.file_path = pdf_path + ".json"
        
        if not os.path.exists(self.file_path):
            self.annotations = []
            return

        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                
            self.annotations = []
            for item in data.get('annotations', []):
                # Convert back to dataclass
                ann = Annotation(**item)
                # Ensure tuples for color/rects if JSON loaded lists
                ann.color = tuple(ann.color)
                ann.rects = [tuple(r) for r in ann.rects]
                self.annotations.append(ann)
                
            print(f"Loaded {len(self.annotations)} annotations from {self.file_path}")
            
        except Exception as e:
            print(f"Error loading annotations: {e}")
            self.annotations = []

    def save(self):
        """Saves annotations to the sidecar JSON file."""
        if not self.file_path:
            return

        data = {
            "version": 1,
            "annotations": [asdict(ann) for ann in self.annotations]
        }
        
        try:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved annotations to {self.file_path}")
            self.is_dirty = False # Sidecar save clears dirty too? Requirement: "Set dirty = False after Save"
        except Exception as e:
            print(f"Error saving annotations: {e}")

    def add(self, annotation: Annotation):
        self.annotations.append(annotation)
        self.is_dirty = True
        self._undo_stack.append(('add', annotation))  # Track for undo
        self._redo_stack.clear()  # New action invalidates redo
        print(f"DEBUG: Added annotation {annotation.id}, undo_stack now has {len(self._undo_stack)} items")

    def get_for_page(self, page_index: int) -> List[Annotation]:
        return [a for a in self.annotations if a.page_index == page_index]
    
    def remove(self, annotation_id: str):
        removed = None
        new_list = []
        for a in self.annotations:
            if a.id == annotation_id:
                removed = a
            else:
                new_list.append(a)
        
        if removed:
            self._undo_stack.append(('remove', removed))  # Track as 'remove' operation
            self._redo_stack.clear()  # New action invalidates redo history
            self.annotations = new_list
            self.is_dirty = True
            print(f"DEBUG: Removed annotation {removed.id}, undo_stack now has {len(self._undo_stack)} items")
            
    def record_modify(self, annotation_id: str, old_rects: list):
        """Records a modification (rect change) for undo. Stores annotation ID and old rects."""
        self._undo_stack.append(('modify', annotation_id, old_rects))
        self._redo_stack.clear()  # New action invalidates redo
        self.is_dirty = True
        print(f"DEBUG: Recorded modify for {annotation_id}, undo_stack now has {len(self._undo_stack)} items")
            
    def undo(self) -> Optional[tuple]:
        """Undoes the last operation. Returns (operation, ...) or None."""
        print(f"DEBUG: undo() called, undo_stack has {len(self._undo_stack)} items")
        if not self._undo_stack:
            print("DEBUG: undo_stack is empty, nothing to undo")
            return None
        
        entry = self._undo_stack.pop()
        op = entry[0]
        
        if op == 'add':
            ann = entry[1]
            # Undo an add → remove the annotation
            self.annotations = [a for a in self.annotations if a.id != ann.id]
            print(f"DEBUG: Undid ADD - removed annotation {ann.id}")
            self._redo_stack.append(entry)
            self.is_dirty = True
            return (op, ann)
        elif op == 'remove':
            ann = entry[1]
            # Undo a remove → restore the annotation
            self.annotations.append(ann)
            print(f"DEBUG: Undid REMOVE - restored annotation {ann.id}")
            self._redo_stack.append(entry)
            self.is_dirty = True
            return (op, ann)
        elif op == 'modify':
            annotation_id, old_rects = entry[1], entry[2]
            # Find the annotation and swap rects
            for ann in self.annotations:
                if ann.id == annotation_id:
                    current_rects = list(ann.rects) if ann.rects else []
                    ann.rects = old_rects
                    self._redo_stack.append(('modify', annotation_id, current_rects))
                    print(f"DEBUG: Undid MODIFY - restored {len(old_rects)} rects for {annotation_id}")
                    self.is_dirty = True
                    return (op, ann)
        return None

    def redo(self) -> Optional[tuple]:
        """Redoes the last undone operation. Returns (operation, ...) or None."""
        print(f"DEBUG: redo() called, redo_stack has {len(self._redo_stack)} items")
        if not self._redo_stack:
            print("DEBUG: redo_stack is empty, nothing to redo")
            return None
        
        entry = self._redo_stack.pop()
        op = entry[0]
        
        if op == 'add':
            ann = entry[1]
            # Redo an add → add the annotation back
            self.annotations.append(ann)
            print(f"DEBUG: Redid ADD - added annotation {ann.id}")
            self._undo_stack.append(entry)
            self.is_dirty = True
            return (op, ann)
        elif op == 'remove':
            ann = entry[1]
            # Redo a remove → remove the annotation again
            self.annotations = [a for a in self.annotations if a.id != ann.id]
            print(f"DEBUG: Redid REMOVE - removed annotation {ann.id}")
            self._undo_stack.append(entry)
            self.is_dirty = True
            return (op, ann)
        elif op == 'modify':
            annotation_id, new_rects = entry[1], entry[2]
            # Find the annotation and swap rects
            for ann in self.annotations:
                if ann.id == annotation_id:
                    current_rects = list(ann.rects) if ann.rects else []
                    ann.rects = new_rects
                    self._undo_stack.append(('modify', annotation_id, current_rects))
                    print(f"DEBUG: Redid MODIFY - applied {len(new_rects)} rects for {annotation_id}")
                    self.is_dirty = True
                    return (op, ann)
        return None

    def find_annotation_at(self, page_index: int, x: float, y: float, tolerance: float = 5.0) -> Optional[Annotation]:
        """Finds the top-most annotation at the given PDF coordinates with tolerance."""
        print(f"DEBUG: find_annotation_at page={page_index}, x={x:.2f}, y={y:.2f}, tol={tolerance}")
        # Iterate in reverse to find the one drawn on top
        for ann in reversed(self.annotations):
            if ann.page_index != page_index:
                continue
            
            # Check rects
            if not ann.rects: continue
            for r in ann.rects:
                # r is (x, y, w, h)
                rx, ry, rw, rh = r
                if (rx - tolerance) <= x <= (rx + rw + tolerance) and \
                   (ry - tolerance) <= y <= (ry + rh + tolerance):
                    print(f"DEBUG: HIT annotation {ann.id}")
                    return ann
        print("DEBUG: No annotation hit")
        return None
