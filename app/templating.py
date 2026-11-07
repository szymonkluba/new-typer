import contextvars

from fastapi.templating import Jinja2Templates

from app.i18n import DEFAULT_LANG, format_date_localized, translate

current_lang: contextvars.ContextVar[str] = contextvars.ContextVar("current_lang", default=DEFAULT_LANG)

templates = Jinja2Templates(directory="app/templates")


def _(key: str) -> str:
    return translate(key, current_lang.get())


def _format_date_filter(dt):
    return format_date_localized(dt, current_lang.get())


def _get_current_lang():
    return current_lang.get()


templates.env.globals["_"] = _
templates.env.globals["current_lang"] = _get_current_lang
def _translate_status_filter(status: str) -> str:
    return translate(f"status_{status}", current_lang.get())


templates.env.filters["format_date"] = _format_date_filter
templates.env.filters["translate_status"] = _translate_status_filter
