import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

from pdf_app.ui.pdf_view import PDFView
from pdf_app.ui.empty_view import EmptyView

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.set_title("PDF Workspace")
        self.set_default_size(1200, 800)
        
        # --- Core UI Structure ---
        # 1. Tab View (Chrome-like tabs)
        self.tab_view = Adw.TabView()
        
        # 2. Tab Bar (Top strip for tabs)
        self.tab_bar = Adw.TabBar()
        self.tab_bar.set_view(self.tab_view)
        self.tab_bar.set_autohide(False) 
        
        # 3. Main layout container
        # We use a ToolbarView (Libadwaita 1.4+) or just a box + headerbar approach
        # AdwToolbarView is cleaner for modern apps
        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)
        
        # Top bar with tabs
        self.header_bar = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(self.header_bar)
        
        # The tab bar usually goes below the header bar or *in* the header bar for simple apps.
        # For a Chrome-like experience, we want tabs to be prominent. 
        # Making the tab bar the primary navigation.
        self.toolbar_view.add_top_bar(self.tab_bar)
        
        # Content area
        self.toolbar_view.set_content(self.tab_view)
        
        # Content area
        self.toolbar_view.set_content(self.tab_view)
        
        # --- Ribbon UI ---
        self.active_tool_name = None
        self.ribbon_box = self.build_ribbon()
        self.toolbar_view.add_top_bar(self.ribbon_box)

        # --- Actions ---
        self.setup_actions()
        
        # Add an initial empty tab or welcome screen
        self.add_empty_tab()

    def setup_actions(self):
        """Register window-level actions (Ctrl+O, etc.)"""
        # Open Document Action
        action_open = Gio.SimpleAction.new("open_document", None)
        action_open.connect("activate", self.on_open_document)
        self.add_action(action_open)
        
        # Add New Tab Action (Ctrl+T)
        action_new_tab = Gio.SimpleAction.new("new_tab", None)
        action_new_tab.connect("activate", self.on_new_tab)
        self.add_action(action_new_tab)
        
        action_text_mode = Gio.SimpleAction.new_stateful(
            "insert_text_mode", 
            None, 
            GLib.Variant.new_boolean(False)
        )
        # action_text_mode.connect("change-state", self.on_insert_text_toggled) # REMOVED
        # self.add_action(action_text_mode) # REMOVED
        
        # UI: Add Toggle Button to HeaderBar - REMOVED for Ribbon
        # btn_text = Gtk.ToggleButton(icon_name="document-edit-symbolic")
        # btn_text.set_tooltip_text("Insert Text Mode")
        # btn_text.set_action_name("win.insert_text_mode")
        # self.header_bar.pack_start(btn_text)
        
        # Undo Action (Ctrl+Z)
        action_undo = Gio.SimpleAction.new("undo", None)
        action_undo.connect("activate", self.on_undo)
        self.add_action(action_undo)
        
        # Redo Action (Ctrl+Y)
        action_redo = Gio.SimpleAction.new("redo", None)
        action_redo.connect("activate", self.on_redo)
        self.add_action(action_redo)
        
        # Keyboard Shortcuts
        app = self.get_application()
        if app:
            app.set_accels_for_action("win.open_document", ["<Ctrl>o"])
            app.set_accels_for_action("win.undo", ["<Ctrl>z"])
            app.set_accels_for_action("win.redo", ["<Ctrl>y"])
            app.set_accels_for_action("win.zoom_in", ["<Ctrl>plus", "<Ctrl>equal", "<Ctrl>KP_Add"])
            app.set_accels_for_action("win.zoom_out", ["<Ctrl>minus", "<Ctrl>KP_Subtract"])
            app.set_accels_for_action("win.zoom_reset", ["<Ctrl>0", "<Ctrl>KP_0"])
        
        # Zoom Actions
        action_zoom_in = Gio.SimpleAction.new("zoom_in", None)
        action_zoom_in.connect("activate", self.on_zoom_in)
        self.add_action(action_zoom_in)
        
        action_zoom_out = Gio.SimpleAction.new("zoom_out", None)
        action_zoom_out.connect("activate", self.on_zoom_out)
        self.add_action(action_zoom_out)
        
        action_zoom_reset = Gio.SimpleAction.new("zoom_reset", None)
        action_zoom_reset.connect("activate", self.on_zoom_reset)
        self.add_action(action_zoom_reset)
        
        # File Actions
        action_save = Gio.SimpleAction.new("save", None)
        action_save.connect("activate", self.on_save)
        self.add_action(action_save)
        
        action_export = Gio.SimpleAction.new("export", None)
        action_export.connect("activate", self.on_export)
        self.add_action(action_export)
        
        app.set_accels_for_action("win.save", ["<Ctrl>s"])
        app.set_accels_for_action("win.deselect", ["Escape"])

        # Deselect Action (Escape)
        action_deselect = Gio.SimpleAction.new("deselect", None)
        action_deselect.connect("activate", self.on_deselect)
        self.add_action(action_deselect)

    def on_deselect(self, action, param):
        """Handle Escape key globally."""
        page = self.get_active_page()
        if page:
            # Delegate to page logic (which handles tool reset & selection clear)
            if hasattr(page, 'handle_escape'):
                page.handle_escape()
        
        # Always sync UI (Reset to Select Mode)
        self.update_ribbon_tool_state(None)

    def on_open_document(self, action, param):
        """Handle file open dialog."""
        # TODO: Implement Gtk.FileDialog for GTK 4.10+ or keep Gtk.FileChooserNative
        dialog = Gtk.FileChooserNative(
            title="Open PDF",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN
        )
        
        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF Documents")
        filter_pdf.add_mime_type("application/pdf")
        dialog.add_filter(filter_pdf)
        
        dialog.connect("response", self.on_open_response)
        dialog.show()

    def on_open_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            self.open_pdf_tab(file)
        dialog.destroy()

    # def on_insert_text_toggled(self, action, state): # REMOVED
    
    def build_ribbon(self):
        ribbon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ribbon_box.add_css_class("toolbar")
        ribbon_box.set_margin_start(10)
        ribbon_box.set_margin_end(10)
        ribbon_box.set_margin_top(5)
        ribbon_box.set_margin_bottom(5)
        
        # Tools Group
        box_tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_tools.add_css_class("linked")
        
        # Select (Cursor)
        btn_select = Gtk.ToggleButton(icon_name="edit-select-symbolic")
        btn_select.set_tooltip_text("Select / Move")
        btn_select.set_active(True)
        btn_select.connect("toggled", self.on_tool_toggled, None)
        self.btn_select = btn_select
        
        # Highlight
        btn_highlight = Gtk.ToggleButton(icon_name="format-text-bold-symbolic")
        btn_highlight.set_tooltip_text("Highlight")
        btn_highlight.set_group(btn_select)
        btn_highlight.connect("toggled", self.on_tool_toggled, "highlight")
        self.btn_highlight = btn_highlight
        
        # Underline
        btn_underline = Gtk.ToggleButton(icon_name="format-text-underline-symbolic")
        btn_underline.set_tooltip_text("Underline")
        btn_underline.set_group(btn_select)
        btn_underline.connect("toggled", self.on_tool_toggled, "underline")
        self.btn_underline = btn_underline
        
        # Text
        btn_text = Gtk.ToggleButton(icon_name="document-edit-symbolic")
        btn_text.set_tooltip_text("Add Text")
        btn_text.set_group(btn_select)
        btn_text.connect("toggled", self.on_tool_toggled, "text")
        self.btn_text = btn_text
        
        box_tools.append(btn_select)
        box_tools.append(btn_highlight)
        box_tools.append(btn_underline)
        box_tools.append(btn_text)
        
        ribbon_box.append(box_tools)
        
        # Spacer
        ribbon_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        
        # Zoom Controls
        box_zoom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_zoom.add_css_class("linked")
        
        btn_zoom_out = Gtk.Button(icon_name="zoom-out-symbolic")
        btn_zoom_out.set_action_name("win.zoom_out")
        
        btn_zoom_in = Gtk.Button(icon_name="zoom-in-symbolic")
        btn_zoom_in.set_action_name("win.zoom_in")
        
        btn_zoom_fit = Gtk.Button(icon_name="zoom-fit-best-symbolic")
        btn_zoom_fit.set_tooltip_text("Fit Width")
        btn_zoom_fit.set_action_name("win.zoom_reset")
        
        box_zoom.append(btn_zoom_out)
        box_zoom.append(btn_zoom_fit)
        box_zoom.append(btn_zoom_in)
        
        ribbon_box.append(box_zoom)
        
        # Spacer
        ribbon_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        
        # File Actions
        box_file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_file.add_css_class("linked")
        
        btn_open = Gtk.Button(icon_name="document-open-symbolic")
        btn_open.set_tooltip_text("Open PDF")
        btn_open.set_action_name("win.open_document")
        
        btn_save = Gtk.Button(icon_name="document-save-symbolic")
        btn_save.set_tooltip_text("Save (Force JSON Sync)")
        btn_save.set_action_name("win.save")
        
        btn_export = Gtk.Button(icon_name="document-print-symbolic")
        btn_export.set_tooltip_text("Export to PDF")
        btn_export.set_action_name("win.export")
        
        box_file.append(btn_open)
        box_file.append(btn_save)
        box_file.append(btn_export)
        
        ribbon_box.append(box_file)
        
        return ribbon_box

    def on_tool_toggled(self, btn, tool_name):
        if btn.get_active():
            self.activate_tool(tool_name)
    
    def get_active_page(self):
        """Get current PDFView."""
        page = self.tab_view.get_selected_page()
        if page:
            return page.get_child()
        return None
            
    def activate_tool(self, tool_name):
        self.active_tool_name = tool_name
        # Propagate to ALL tabs (Global Tool State)
        n = self.tab_view.get_n_pages()
        for i in range(n):
            page_wrapper = self.tab_view.get_nth_page(i)
            view = page_wrapper.get_child()
            if hasattr(view, 'set_tool'):
                view.set_tool(tool_name)

    def update_ribbon_tool_state(self, tool_name):
        """Update ribbon buttons based on tool name (Sync UI)."""
        # Block signals to prevent recursion
        self.btn_select.handler_block_by_func(self.on_tool_toggled)
        self.btn_highlight.handler_block_by_func(self.on_tool_toggled)
        self.btn_underline.handler_block_by_func(self.on_tool_toggled)
        self.btn_text.handler_block_by_func(self.on_tool_toggled)
        
        try:
             if tool_name == 'highlight': self.btn_highlight.set_active(True)
             elif tool_name == 'underline': self.btn_underline.set_active(True)
             elif tool_name == 'text': self.btn_text.set_active(True)
             else: self.btn_select.set_active(True)
        finally:
             self.btn_select.handler_unblock_by_func(self.on_tool_toggled)
             self.btn_highlight.handler_unblock_by_func(self.on_tool_toggled)
             self.btn_underline.handler_unblock_by_func(self.on_tool_toggled)
             self.btn_text.handler_unblock_by_func(self.on_tool_toggled)
             
        # Also ensure tool is activated (if sync called from outside but tool not set?)
        # Usually checking recursion.
        self.activate_tool(tool_name)

    def on_new_tab(self, action, param):
        self.add_empty_tab()

    def on_undo(self, action, param):
        """Undoes the last annotation operation."""
        selected = self.tab_view.get_selected_page()
        if not selected:
            return
        view = selected.get_child()
        if isinstance(view, PDFView):
            result = view.store.undo()
            if result:
                op, ann = result
                print(f"DEBUG: Undone {op} on annotation {ann.id}, page {ann.page_index}")
                view.reload_page(ann.page_index)

    def on_redo(self, action, param):
        """Redoes the last undone annotation operation."""
        selected = self.tab_view.get_selected_page()
        if not selected:
            return
        view = selected.get_child()
        if isinstance(view, PDFView):
            result = view.store.redo()
            if result:
                op, ann = result
                print(f"DEBUG: Redone {op} on annotation {ann.id}, page {ann.page_index}")
                view.reload_page(ann.page_index)

    def add_empty_tab(self):
        """Adds a 'New Tab' page."""
        page = self.tab_view.append(EmptyView())
        page.set_title("New Tab")
        page.set_icon(None)
        self.tab_view.set_selected_page(page)

    def open_pdf_tab(self, file):
        """Opens a PDF file in a new tab."""
        # 1. Create the PDF View widget
        pdf_view = PDFView(file)
        
        # Apply active tool
        if self.active_tool_name:
            pdf_view.set_tool(self.active_tool_name)
        
        # 2. Add to tabs
        page = self.tab_view.append(pdf_view)
        page.set_title(file.get_basename())
        page.set_icon(None) # TODO: Set PDF icon
        
        # 3. Select it
        self.tab_view.set_selected_page(page)

    def on_zoom_in(self, action, param):
        """Zoom in on current PDF."""
        selected = self.tab_view.get_selected_page()
        if selected:
            view = selected.get_child()
            if isinstance(view, PDFView):
                view.zoom_in()

    def on_zoom_out(self, action, param):
        """Zoom out on current PDF."""
        selected = self.tab_view.get_selected_page()
        if selected:
            view = selected.get_child()
            if isinstance(view, PDFView):
                view.zoom_out()

    def on_zoom_reset(self, action, param):
        """Reset zoom to fit-to-width."""
        selected = self.tab_view.get_selected_page()
        if selected:
            view = selected.get_child()
            if isinstance(view, PDFView):
                view.zoom_reset()

    def on_save(self, action, param):
        """Save the annotations to JSON immediately."""
        selected_page = self.tab_view.get_selected_page()
        if not selected_page: return
        page = selected_page
        view = page.get_child()
        if hasattr(view, 'store'):
            view.store.save()
            print(f"DEBUG: Saved annotations for {view.file.get_basename()}")

    def on_export(self, action, param):
        """Export to PDF (Placeholder)."""
        # TODO: Implement PDF Export
        print("DEBUG: Export to PDF triggered")

