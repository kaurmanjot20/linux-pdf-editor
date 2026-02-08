import cairo
import gi
gi.require_version('Poppler', '0.18')
from gi.repository import Poppler, Gdk

def render_page_to_surface(page: Poppler.Page, scale: float = 1.0) -> cairo.ImageSurface:
    """
    Renders a Poppler page to a Cairo Image Surface.
    Scales the page by standard screen scale factor * zoom level.
    """
    width, height = page.get_size()
    scaled_width = int(width * scale)
    scaled_height = int(height * scale)
    
    # Create ARGB32 surface (supports transparency, though PDF usually opaque)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, scaled_width, scaled_height)
    context = cairo.Context(surface)
    
    # Fill background with white (PDFs are transparent by default)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    
    # Apply scaling
    context.scale(scale, scale)
    
    # Render PDF content
    page.render(context)
    
    return surface

def get_page_size(page: Poppler.Page, scale: float = 1.0):
    w, h = page.get_size()
    return w * scale, h * scale
