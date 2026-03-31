#!/usr/bin/env bash
set -euo pipefail

if [ ! -d /opt/iotronic-ui ]; then
  git clone https://opendev.org/x/iotronic-ui.git /opt/iotronic-ui
fi

if [ -d /adapter/iotronic_ui ]; then
  cp -f /adapter/iotronic_ui/api/iotronic.py /opt/iotronic-ui/iotronic_ui/api/iotronic.py
  mkdir -p /opt/iotronic-ui/iotronic_ui/iot/boards
  cp -f /adapter/iotronic_ui/iot/boards/tabs.py /opt/iotronic-ui/iotronic_ui/iot/boards/tabs.py
  cp -f /adapter/iotronic_ui/iot/plugins/forms.py /opt/iotronic-ui/iotronic_ui/iot/plugins/forms.py
  cp -f /adapter/iotronic_ui/iot/plugins/views.py /opt/iotronic-ui/iotronic_ui/iot/plugins/views.py
fi

python3 - <<'PY'
from pathlib import Path
root = Path("/opt/iotronic-ui/iotronic_ui")
for p in root.rglob("*.py"):
    txt = p.read_text()
    new = txt.replace("from django.utils.translation import ugettext_lazy as _", "from django.utils.translation import gettext_lazy as _")
    new = new.replace("from django.utils.translation import ugettext as _", "from django.utils.translation import gettext as _")
    new = new.replace("ugettext_lazy(", "gettext_lazy(")
    new = new.replace("ugettext(", "gettext(")
    new = new.replace("from django.utils.translation import ungettext_lazy", "from django.utils.translation import ngettext_lazy")
    new = new.replace("from django.utils.translation import ungettext", "from django.utils.translation import ngettext")
    new = new.replace("ungettext_lazy(", "ngettext_lazy(")
    new = new.replace("ungettext(", "ngettext(")
    new = new.replace("from django.core.urlresolvers import reverse", "from django.urls import reverse")
    new = new.replace("from django.conf.urls import url", "from django.urls import re_path")
    new = new.replace("url(", "re_path(")
    if new != txt:
        p.write_text(new)
PY

/var/lib/kolla/venv/bin/pip install --no-deps -e /opt/iotronic-ui
cp -f /opt/iotronic-ui/iotronic_ui/enabled/_6*.py /var/lib/kolla/venv/lib/python3.10/site-packages/openstack_dashboard/enabled/
cp -f /opt/iotronic-ui/iotronic_ui/api/iotronic.py /var/lib/kolla/venv/lib/python3.10/site-packages/openstack_dashboard/api/iotronic.py

python3 - <<'PY'
from pathlib import Path
settings = Path("/etc/openstack-dashboard/local_settings.py")
text = settings.read_text()
text = text.replace(
    'AVAILABLE_REGIONS = [("RegionOne", "http://legacy-keystone:5000/v3", "RegionOne")]',
    'AVAILABLE_REGIONS = [("RegionOne", "http://legacy-keystone:5000/v3")]'
)
text = text.replace(
    'AVAILABLE_REGIONS = [("RegionOne", "http://legacy-keystone:5000/v3")]',
    'AVAILABLE_REGIONS = [("http://legacy-keystone:5000/v3", "default")]'
)
text = text.replace(
    'AVAILABLE_REGIONS = [("http://legacy-keystone:5000/v3", "RegionOne")]',
    'AVAILABLE_REGIONS = [("http://legacy-keystone:5000/v3", "default")]'
)
inject = """
ALLOWED_HOSTS = ['*']
OPENSTACK_KEYSTONE_URL = "http://legacy-keystone:5000/v3"
OPENSTACK_HOST = "legacy-keystone"
OPENSTACK_KEYSTONE_ENDPOINT_TYPE = "internalURL"
OPENSTACK_ENDPOINT_TYPE = "internalURL"
OPENSTACK_KEYSTONE_DEFAULT_ROLE = "member"
AVAILABLE_REGIONS = [("http://legacy-keystone:5000/v3", "default")]
WEBROOT = "/"
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/horizon.sqlite3",
    }
}
"""
if "OPENSTACK_KEYSTONE_URL = \"http://legacy-keystone:5000/v3\"" not in text:
    settings.write_text(text + "\n" + inject + "\n")
elif "SESSION_ENGINE = \"django.contrib.sessions.backends.signed_cookies\"" not in text:
    settings.write_text(text + "\n" + inject + "\n")
elif "\"ENGINE\": \"django.db.backends.sqlite3\"" not in text:
    settings.write_text(text + "\n" + inject + "\n")
elif "OPENSTACK_ENDPOINT_TYPE = \"internalURL\"" not in text:
    settings.write_text(text + "\n" + inject + "\n")
PY

/var/lib/kolla/venv/bin/python /var/lib/kolla/venv/bin/manage.py migrate --noinput || true
exec /var/lib/kolla/venv/bin/python /var/lib/kolla/venv/bin/manage.py runserver --noreload 0.0.0.0:8080
