{
    "name": "Web Multi Tabs",
    "version": "19.0.2.0.0",
    "summary": "In-app tab bar for the Odoo backend: every opened view becomes a switchable / closable tab, with an overflow menu and PWA (Window Controls Overlay) support",
    "description": """
        Backend navigation enhancement module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - A tab bar is rendered inside the top navbar (header.o_navbar)
        - Opening a view automatically creates a tab; clicking a tab switches
          the view and every tab has a close button (the last one stays)
        - Tabs that do not fit collapse into a "more tabs" drop-down menu, and
          the active tab is scrolled into view automatically
        - Tab titles follow the current view (quotation number, customer name,
          ...) and are used as the document title in PWA mode
        - Homepage URL variants (/, /web, /odoo, /odoo/) are normalised into a
          single "Home" tab, and the startup redirect is merged into it
        - PWA / Window Controls Overlay aware: the bar is sized with
          CSS env(titlebar-area-*), so it fills the title bar area and can be
          used to drag the window
        - The PWA webmanifest is extended with
          display_override = ["window-controls-overlay"] through standard
          controller inheritance; no core class is monkey-patched
        - No core template is rewritten: the bar is a plain DOM node inserted
          into header.o_navbar
    """,
    "category": "Productivity",
    "author": "edwinhuish",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "web_multi_tabs/static/src/js/multi_tabs.js",
            "web_multi_tabs/static/src/scss/multi_tabs.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
