import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw, GLib, Gdk

from pdf_app.document.loading import load_document
from pdf_app.ui.page_view import PDFPageView
from pdf_app.document.store import AnnotationStore

class PDFView(Gtk.ScrolledWindow):
    """
    Main PDF viewer widget. Scrollable container for pages.
    Implements proper focal-point anchored zoom.
    """
    def __init__(self, file):
        super().__init__()
        self.file = file
        self.document = None
        self.store = AnnotationStore()
        self.scale = 1.0  # Zoom level: 1.0 = 100%
        self.min_scale = 0.5
        self.max_scale = 4.0
        
        # Gesture state
        self._gesture_start_scale = 1.0
        self._focal_point = (0, 0)  # Focal point in viewport coords
        
        # UI Setup
        self.set_vexpand(True)
        self.set_hexpand(True)
        
        # Container for pages (vertical stack)
        self.page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.page_box.set_halign(Gtk.Align.CENTER)
        self.page_box.set_margin_top(20)
        self.page_box.set_margin_bottom(20)
        
        self.set_child(self.page_box)
        self.pages = [] # Track page instances
        
        # Pinch-to-Zoom Gesture
        zoom_gesture = Gtk.GestureZoom()
        zoom_gesture.connect("begin", self.on_zoom_begin)
        zoom_gesture.connect("scale-changed", self.on_zoom_scale_changed)
        zoom_gesture.connect("end", self.on_zoom_end)
        self.add_controller(zoom_gesture)
        
        # Scroll event for Ctrl+Scroll zoom
        scroll_controller = Gtk.EventControllerScroll()
        scroll_controller.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.connect("scroll", self.on_scroll)
        self.add_controller(scroll_controller)

        # Load document
        self.load_pdf()

    def load_pdf(self):
        try:
            # 1. Load PDF logic
            self.document = load_document(self.file)
            if not self.document:
                self.show_error("Failed to load PDF.")
                return
                
            # 2. Load Annotations
            self.store.load(self.file.get_path())

            n_pages = self.document.get_n_pages()
            print(f"Loaded PDF with {n_pages} pages.")

            # Render pages
            for i in range(n_pages):
                page = self.document.get_page(i)
                # Pass store to page view
                page_view = PDFPageView(page, i, self.store)
                self.pages.append(page_view)
                self.page_box.append(page_view)
                self.pages.append(page_view)

            # Set initial zoom to fit-to-width after layout
            GLib.idle_add(self._fit_to_width)

        except Exception as e:
            self.show_error(str(e))

    def _fit_to_width(self):
        """Set initial scale to fit page width in viewport."""
        viewport_width = self.get_allocated_width()
        if viewport_width <= 1 or not self.document:
            return False  # Not ready yet
        
        # Get first page width
        first_page = self.document.get_page(0)
        page_width, _ = first_page.get_size()
        
        # Calculate fit-to-width scale (with small margin)
        fit_scale = (viewport_width - 40) / page_width  # 20px margin each side
        fit_scale = max(self.min_scale, min(self.max_scale, fit_scale))
        
        self.scale = fit_scale
        self._gesture_start_scale = fit_scale
        self._apply_zoom()
        print(f"DEBUG: Fit to width: {self.scale:.1%}")
        return False

    def set_tool(self, tool_name):
        """Propagate tool selection to all pages."""
        self.tool_name = tool_name
        for page in self.pages:
            page.activate_tool(tool_name)

    def handle_escape(self):
        """Global Escape Logic."""
        # 1. Reset Tool
        self.set_tool(None)
        
        # 2. Clear Selection & Close Popovers
        for page in self.pages:
            if page.drawing_area.selected_annotation:
                 page.drawing_area.selected_annotation = None
                 page.drawing_area.queue_draw()
            if hasattr(page, 'editor_popover') and page.editor_popover:
                 page.editor_popover.popdown()

    def set_text_mode(self, enabled):
        child = self.page_box.get_first_child()
        while child:
            if isinstance(child, PDFPageView):
                child.set_text_mode(enabled)
            child = child.get_next_sibling()
            
        if enabled:
            self.page_box.grab_focus()

    def reload_page(self, page_index: int):
        """Reloads widgets for a specific page after undo."""
        child = self.page_box.get_first_child()
        while child:
            if isinstance(child, PDFPageView) and child.page_number == page_index:
                # child.load_widgets() # REMOVED: Legacy
                child.drawing_area.queue_draw()
                break
            child = child.get_next_sibling()

    def show_error(self, message):
        label = Gtk.Label(label=f"Error: {message}")
        self.page_box.append(label)

    # ========== ZOOM HANDLERS ==========

    def on_zoom_begin(self, gesture, sequence):
        """Store starting state for pinch gesture."""
        self._gesture_start_scale = self.scale
        # Get gesture center point as focal point
        _, x, y = gesture.get_bounding_box_center()
        self._focal_point = (x, y)

    def on_zoom_scale_changed(self, gesture, scale):
        """Handle pinch-to-zoom gesture - continuous, proportional."""
        new_scale = self._gesture_start_scale * scale
        new_scale = max(self.min_scale, min(self.max_scale, new_scale))
        
        if abs(new_scale - self.scale) < 0.001:
            return
        
        self._zoom_around_focal(new_scale, self._focal_point)

    def on_zoom_end(self, gesture, sequence):
        """Pinch gesture ended."""
        self._gesture_start_scale = self.scale

    def on_scroll(self, controller, dx, dy):
        """Handle Ctrl+Scroll for zoom."""
        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            # Get cursor position as focal point
            event = controller.get_current_event()
            if event:
                x, y = event.get_position()
                focal = (x, y)
            else:
                # Fallback to viewport center
                focal = (self.get_allocated_width() / 2, self.get_allocated_height() / 2)
            
            # Proportional zoom (10% per scroll tick)
            factor = 1.1 if dy < 0 else 1 / 1.1
            new_scale = self.scale * factor
            new_scale = max(self.min_scale, min(self.max_scale, new_scale))
            
            self._zoom_around_focal(new_scale, focal)
            return True  # Event handled
        return False  # Let scrolling happen normally

    def _zoom_around_focal(self, new_scale, focal):
        """Zoom around a focal point, adjusting scroll to keep it fixed."""
        if abs(new_scale - self.scale) < 0.001:
            return
        
        # Get current scroll position
        hadj = self.get_hadjustment()
        vadj = self.get_vadjustment()
        old_scroll_x = hadj.get_value()
        old_scroll_y = vadj.get_value()
        
        # Calculate the document position of the focal point
        doc_x = old_scroll_x + focal[0]
        doc_y = old_scroll_y + focal[1]
        
        # Calculate scale ratio
        ratio = new_scale / self.scale
        
        # Apply new scale
        old_scale = self.scale
        self.scale = new_scale
        self._apply_zoom()
        
        # Calculate new document position of focal point
        new_doc_x = doc_x * ratio
        new_doc_y = doc_y * ratio
        
        # Adjust scroll to keep focal point stationary
        new_scroll_x = new_doc_x - focal[0]
        new_scroll_y = new_doc_y - focal[1]
        
        # Apply new scroll (clamp to valid range)
        hadj.set_value(max(0, new_scroll_x))
        vadj.set_value(max(0, new_scroll_y))

    def _apply_zoom(self):
        """Apply current scale to all page views."""
        child = self.page_box.get_first_child()
        while child:
            if isinstance(child, PDFPageView):
                child.update_scale(self.scale)
            child = child.get_next_sibling()

    # ========== PUBLIC ZOOM METHODS ==========

    def zoom_in(self):
        """Zoom in by 10%, centered on viewport."""
        focal = (self.get_allocated_width() / 2, self.get_allocated_height() / 2)
        new_scale = min(self.max_scale, self.scale * 1.1)
        self._zoom_around_focal(new_scale, focal)

    def zoom_out(self):
        """Zoom out by 10%, centered on viewport."""
        focal = (self.get_allocated_width() / 2, self.get_allocated_height() / 2)
        new_scale = max(self.min_scale, self.scale / 1.1)
        self._zoom_around_focal(new_scale, focal)

    def zoom_reset(self):
        """Reset to fit-to-width."""
        self._fit_to_width()
