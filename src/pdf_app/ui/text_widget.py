import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Pango

from pdf_app.document.store import Annotation

class TextWidget(Gtk.Overlay):
    def __init__(self, annotation, scale, on_update, on_remove=None):
        super().__init__()
        self.annotation = annotation
        self.scale = scale
        self.on_update = on_update
        self.on_remove = on_remove
        
        # Main Container
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.add_css_class("text-annotation-box")
        self.set_child(self.box)
        
        # Header (Drag Handle)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.set_can_focus(False)
        # header.set_size_request(-1, 10) # Thin header
        
        grip_icon = Gtk.Image.new_from_icon_name("open-menu-symbolic")
        grip_icon.set_pixel_size(12)
        grip_icon.set_opacity(0.3)
        grip_icon.set_margin_start(4)
        grip_icon.set_margin_top(2)
        header.append(grip_icon)
        
        self.box.append(header)

        # TextView
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_left_margin(8)
        self.text_view.set_right_margin(8)
        self.text_view.set_top_margin(2)
        self.text_view.set_bottom_margin(8)
        self.text_view.set_vexpand(True)
        # self.text_view.add_css_class("transparent-textview") # If needed
        
        # Behavior: Double Click to Edit
        self.text_view.set_focusable(False) # Initially not focusable
        self.text_view.set_cursor_visible(False)
        
        buffer = self.text_view.get_buffer()
        buffer.set_text(annotation.content)
        buffer.connect("changed", self.on_text_changed)
        
        self.apply_style()
        self.box.append(self.text_view)
        
        # Focus Controller (Focus Out -> View Only)
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self.on_focus_leave)
        self.text_view.add_controller(focus_controller)
        
        # Key Controller (Delete Key -> Remove Widget)
        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.box.add_controller(key_controller)
        
        # Click Controller (Double Click)
        click_gesture = Gtk.GestureClick()
        click_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click_gesture.set_button(0) # Accept all buttons
        click_gesture.connect("pressed", self.on_click_pressed)
        self.add_controller(click_gesture)

        # Resize Grip (Overlay)
        self.resize_grip = Gtk.Image.new_from_icon_name("window-maximize-symbolic")
        self.resize_grip.set_pixel_size(12)
        self.resize_grip.set_opacity(0.4)
        self.resize_grip.set_cursor(Gdk.Cursor.new_from_name("nwse-resize", None))
        self.resize_grip.set_halign(Gtk.Align.END)
        self.resize_grip.set_valign(Gtk.Align.END)
        self.resize_grip.set_margin_end(2)
        self.resize_grip.set_margin_bottom(2)
        self.add_overlay(self.resize_grip)

        # Controllers
        # Move (Header)
        move_drag = Gtk.GestureDrag()
        move_drag.connect("drag-begin", self.on_drag_begin)
        move_drag.connect("drag-update", self.on_drag_update)
        move_drag.connect("drag-end", self.on_drag_end)
        header.add_controller(move_drag)
        
        # Resize (Corner Grip)
        resize_drag = Gtk.GestureDrag()
        resize_drag.connect("drag-begin", self.on_resize_begin)
        resize_drag.connect("drag-update", self.on_resize_update)
        resize_drag.connect("drag-end", self.on_resize_end)
        self.resize_grip.add_controller(resize_drag)

        # Make the box focusable to allow selecting the widget without editing
        self.box.set_focusable(True)

        # Set Initial Size
        if annotation.rects:
             _, _, w, h = annotation.rects[0]
             self.set_size_request(int(w * scale), int(h * scale))

    def on_click_pressed(self, gesture, n_press, x, y):
        # We allow bubbling for single click (so it might select parent?)
        # NO, we want to grab focus so we deselect other widgets.
        
        self.box.grab_focus() # Always grab container focus first
        
        # For Double Click, we activate edit mode.
        if n_press == 2:
            self.text_view.set_focusable(True)
            self.text_view.set_cursor_visible(True)
            self.text_view.grab_focus()
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            
    def on_key_pressed(self, controller, keyval, keycode, state):
        # Handle Delete Key
        if keyval == Gdk.KEY_Delete or keyval == Gdk.KEY_BackSpace:
             # Only delete if we are NOT inside the TextView (editing text)
             
             # Check focus
             if self.text_view.has_focus():
                 return False # Let TextView handle text deletion
                 
             if self.on_remove:
                 self.on_remove(self)
                 return True # CONSUME EVENT (Stop Propagation)
                 
        return False

    def on_focus_leave(self, controller):
        # When focus leaves, revert to view-only
        self.text_view.set_focusable(False)
        self.text_view.set_cursor_visible(False)
        self.on_update(self.annotation)
        
    def apply_style(self):
        # We apply handwritten font to TextView
        if self.annotation.style == 'handwritten':
            self.text_view.add_css_class("handwritten-font")
        else:
            self.text_view.remove_css_class("handwritten-font")

    def on_text_changed(self, buffer):
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True)
        self.annotation.content = text.strip()
        self.on_update(self.annotation)

    # --- Move Logic ---
    def on_drag_begin(self, gesture, x, y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        
        # Visual Feedback
        self.set_cursor(Gdk.Cursor.new_from_name("grabbing", None))
        self.box.add_css_class("dragging")
        
        parent = self.get_parent()
        if parent and isinstance(parent, Gtk.Fixed):
            alloc = self.get_allocation()
            self.start_fixed_x = alloc.x
            self.start_fixed_y = alloc.y

        # Anchor Strategy:
        header = gesture.get_widget()
        # Handle tuple of 2 or 3 return values from translate_coordinates
        try:
            ret = header.translate_coordinates(self, x, y)
            if ret and len(ret) == 2:
                self.anchor_x, self.anchor_y = ret
            elif ret and len(ret) == 3:
                res, self.anchor_x, self.anchor_y = ret
                if not res: raise ValueError("Translation failed")
            else:
                self.anchor_x, self.anchor_y = x, y
        except (ValueError, TypeError):
             self.anchor_x, self.anchor_y = x, y # Fallback

    def on_drag_update(self, gesture, offset_x, offset_y):
        parent = self.get_parent()
        if not parent or not isinstance(parent, Gtk.Fixed):
            return
            
        # Get coordinates in Parent directly.
        seq = gesture.get_current_sequence()
        success, p_x, p_y = gesture.get_point(seq) # Relative to Header
        
        header = gesture.get_widget()
        root_x, root_y = None, None
        
        try:
            ret = header.translate_coordinates(parent, p_x, p_y)
            if ret and len(ret) == 2:
                root_x, root_y = ret
            elif ret and len(ret) == 3:
                res, root_x, root_y = ret
                if not res: root_x = None
        except (ValueError, TypeError):
            pass

        if root_x is not None:
            new_x = root_x - self.anchor_x
            new_y = root_y - self.anchor_y
            
            parent.move(self, int(new_x), int(new_y))
            
            # Sync
            pdf_x = new_x / self.scale
            pdf_y = new_y / self.scale
            if self.annotation.rects:
                _, _, w, h = self.annotation.rects[0]
                self.annotation.rects[0] = (pdf_x, pdf_y, w, h)
        else:
            # Fallback to offset method if translation fails
            new_x = self.start_fixed_x + offset_x
            new_y = self.start_fixed_y + offset_y
            parent.move(self, int(new_x), int(new_y))

    def on_drag_end(self, gesture, offset_x, offset_y):
        self.set_cursor(None)
        self.box.remove_css_class("dragging")
        self.on_update(self.annotation)

    # --- Resize Logic ---
    def on_resize_begin(self, gesture, x, y):
        self.start_w = self.get_width()
        self.start_h = self.get_height()

    def on_resize_update(self, gesture, offset_x, offset_y):
        new_w = max(50, self.start_w + offset_x)
        new_h = max(30, self.start_h + offset_y)
        
        self.set_size_request(int(new_w), int(new_h))
        
        # Update Annotation W/H (In Memory Only)
        if self.annotation.rects:
            pdf_x, pdf_y, _, _ = self.annotation.rects[0]
            pdf_w = new_w / self.scale
            pdf_h = new_h / self.scale
            self.annotation.rects[0] = (pdf_x, pdf_y, pdf_w, pdf_h)
            # DO NOT SAVE HERE

    def on_resize_end(self, gesture, offset_x, offset_y):
        self.on_update(self.annotation) # Save on Release
