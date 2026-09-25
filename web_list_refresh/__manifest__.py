{
    "name": "List View Refresh",
    "version": "19.0.1.0.0",
    "summary": "Add a refresh button to every list, kanban and card view: reloads data with the current search terms, filters, grouping, sorting and page preserved",
    "description": """
        List View Refresh module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese translation ships in i18n/zh_CN.po.

        Key features:
        - A refresh button is added to the control panel of every multi-record view (list, kanban and custom views derived from them, such as a card view)
        - Refreshing re-runs the current query without rebuilding the view, so search terms, filters, group bys, favourites, pagination and sorting stay exactly as they were
        - A row being edited is saved first; if validation fails, the refresh is aborted and the draft is kept
        - The button only appears when the current view registered a refresh handler, so form views and other non list views do not show it
        - Standard extension only: a core OWL template is extended with t-inherit and two controllers are patched with @web/core/utils/patch, no core file is modified
    """,
    "category": "Productivity",
    "author": "edwinhuish",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "web_list_refresh/static/src/js/view_refresh.js",
            "web_list_refresh/static/src/js/list_refresh_patch.js",
            "web_list_refresh/static/src/xml/list_refresh_templates.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
