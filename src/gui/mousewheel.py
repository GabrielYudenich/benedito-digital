"""Mouse-wheel helpers that prevent background panels from stealing modal events."""


def widget_is_within(widget, ancestor) -> bool:
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        current = getattr(current, "master", None)
    return False


def mousewheel_units(event) -> int:
    delta = int(getattr(event, "delta", 0) or 0)
    if delta:
        return int(-delta / 120) or (-1 if delta > 0 else 1)
    number = int(getattr(event, "num", 0) or 0)
    if number == 4:
        return -1
    if number == 5:
        return 1
    return 0


def scroll_canvas_if_within(event, canvas, content):
    if not (
        widget_is_within(getattr(event, "widget", None), canvas)
        or widget_is_within(getattr(event, "widget", None), content)
    ):
        return None
    units = mousewheel_units(event)
    if units:
        canvas.yview_scroll(units, "units")
    return "break"
