from fastapi.templating import Jinja2Templates

from app.core.config import APP_VERSION, settings
from app.core.timezone import (
    format_compact_date,
    format_compact_datetime,
    format_date,
    format_datetime,
    format_time,
)

templates = Jinja2Templates(
    directory="app/web/templates",
)

templates.env.globals.update(
    {
        "settings": settings,
        "app_version": APP_VERSION,
    },
)

templates.env.filters.update(
    {
        "format_datetime": format_datetime,
        "format_compact_datetime": format_compact_datetime,
        "format_date": format_date,
        "format_compact_date": format_compact_date,
        "format_time": format_time,
    },
)