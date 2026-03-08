import sys
import os
import xml.etree.ElementTree as ET

def run_splash():
    try:
        from AppKit import NSApplication, NSWindow, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, NSColor, NSRect, NSScreen, NSApplicationActivationPolicyProhibited
        from WebKit import WKWebView, WKWebViewConfiguration
        from Foundation import NSURL
    except ImportError:
        print("WebKit/AppKit not found")
        return

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    splash_svg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "splash.svg")
    
    if not os.path.exists(splash_svg):
        print("No SVG found")
        return

    # Parse SVG to get aspect ratio
    try:
        tree = ET.parse(splash_svg)
        svg_root = tree.getroot()
        orig_w = float(svg_root.attrib.get("width", 3484.66))
        orig_h = float(svg_root.attrib.get("height", 2260))
    except Exception:
        orig_w, orig_h = 3484.66, 2260.0

    screen_frame = NSScreen.mainScreen().frame()
    screen_w = screen_frame.size.width
    screen_h = screen_frame.size.height

    # Aha! The original SVG is HUGE: 3484 x 2260.
    # 50% of that is still 1742 x 1130, which is likely larger than the screen height and width of a MacBook!
    
    # We will forcefully set the target height/width to be reasonable. Let's make it 600px wide.
    # 600px is a very standard and pleasant size for a splash logo.
    
    target_w = 600.0
    target_h = target_w * (orig_h / orig_w)

    w, h = int(target_w), int(target_h)

    x = (screen_w - w) / 2
    y = (screen_h - h) / 2

    # Provide exact dimensions to window
    frame = NSRect((x, y), (w, h))
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        NSWindowStyleMaskBorderless, # Explicitly say NO border
        NSBackingStoreBuffered,
        False
    )
    
    # The magical incantations to TRULY get rid of macOS borders/shadows/corners
    window.setOpaque_(False)
    window.setBackgroundColor_(NSColor.clearColor())
    window.setHasShadow_(False)
    window.setIgnoresMouseEvents_(True) # Make it click-through just in case
    
    # NSWindowCollectionBehaviorStationary = 1 << 4
    # NSWindowCollectionBehaviorIgnoresCycle = 1 << 6
    window.setCollectionBehavior_(16 | 64)
    window.setLevel_(1000)

    config = WKWebViewConfiguration.alloc().init()

    # The WKWebView frame MUST match the window frame exactly to avoid clipping/borders
    webview = WKWebView.alloc().initWithFrame_configuration_(NSRect((0,0),(w,h)), config)
    
    # Make WebKit background transparent natively
    webview.setValue_forKey_(False, "drawsBackground")


    with open(splash_svg, "r") as f:
        svg_content = f.read()

    # REMOVE EXCALIDRAW WHITE BACKGROUND RECTANGLE
    import re
    svg_content = re.sub(r"""<rect([^>]*)fill="#ffffff"([^>]*)>""", r"<rect\g<1>fill=\"#000000\"\g<2>>", svg_content)


    # We use a trick in the HTML body to remove ANY browser default margins, borders, or backgrounds.
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        html, body {{ 
            margin: 0 !important; 
            padding: 0 !important; 
            overflow: hidden !important; 
            background-color: #000000 !important; 
            width: 100vw; 
            height: 100vh; 
            border: none !important;
            outline: none !important;
        }}
        svg {{ 
            width: 100%; 
            height: 100%; 
            display: block; 
            border: none !important;
            outline: none !important;
            background: #000000 !important;
        }}
    </style>
    </head>
    <body>
    {svg_content}
    </body>
    </html>
    """

    webview.loadHTMLString_baseURL_(html, NSURL.fileURLWithPath_(os.path.dirname(splash_svg)))

    window.contentView().addSubview_(webview)
    window.makeKeyAndOrderFront_(None)

    import threading
    import time
    def close_app():
        time.sleep(2.5) # show for 2.5 seconds
        app.terminate_(None)

    threading.Thread(target=close_app, daemon=True).start()

    app.run()

if __name__ == "__main__":
    run_splash()
