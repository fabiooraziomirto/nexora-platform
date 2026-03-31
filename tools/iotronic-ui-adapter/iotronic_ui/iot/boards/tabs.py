import logging

from django.utils.translation import gettext_lazy as _
from horizon import tabs

LOG = logging.getLogger(__name__)


def _safe_info(board):
    return getattr(board, "_info", {}) or {}


def _safe_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _extract_coordinates(board):
    location = getattr(board, "location", None)
    if isinstance(location, dict):
        if "coordinates" in location:
            coords = location.get("coordinates")
            if isinstance(coords, list):
                return coords
            if coords is not None:
                return [coords]
        if "lat" in location and "lon" in location:
            return [location.get("lat"), location.get("lon")]
        if "latitude" in location and "longitude" in location:
            return [location.get("latitude"), location.get("longitude")]
        return []
    if isinstance(location, list):
        return location
    return []


class OverviewTab(tabs.Tab):
    name = _("Overview")
    slug = "overview"
    template_name = ("iot/boards/_detail_overview.html")

    def get_context_data(self, request):
        board = self.tab_group.kwargs.get("board")
        info = _safe_info(board)

        return {
            "board": board,
            "coordinates": _extract_coordinates(board),
            "services": _safe_list(info.get("services")),
            "webservices": _safe_list(info.get("webservices")),
            "ports": _safe_list(info.get("ports")),
            "plugins": _safe_list(info.get("plugins")),
            "is_superuser": request.user.is_superuser,
        }


class BoardDetailTabs(tabs.TabGroup):
    slug = "board_details"
    tabs = (OverviewTab,)
    sticky = True
