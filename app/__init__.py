"""Ireland Health Evidence -- the FastAPI application package.

Layout:
    config.py   every path and setting, resolved once
    db.py       SQLite access helpers
    schemas.py  Pydantic response models (these generate the /docs schema)
    routes.py   the /api routes
    main.py     the app factory; also mounts the dashboard at /
"""
