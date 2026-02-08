import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    box = Gtk.Box()
    btn = Gtk.Button(label="Test")
    box.append(btn)
    win.set_child(box)
    win.present()
    
    # Test translate_coordinates
    try:
        ret = btn.translate_coordinates(box, 0, 0)
        print(f"Return value: {ret}")
        print(f"Type: {type(ret)}")
        print(f"Length: {len(ret) if hasattr(ret, '__len__') else 'N/A'}")
    except Exception as e:
        print(f"Error: {e}")
    
    app.quit()

app = Gtk.Application(application_id='com.example.Test')
app.connect('activate', on_activate)
app.run(None)
