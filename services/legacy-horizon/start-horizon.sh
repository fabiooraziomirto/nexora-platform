#!/usr/bin/env bash
set -euo pipefail

if [ ! -d /opt/nexora-dashboard ]; then
  git clone https://opendev.org/x/nexora-dashboard.git /opt/nexora-dashboard
fi

if [ -d /adapter/nexora_dashboard ]; then
  cp -f /adapter/nexora_dashboard/api/nexora.py /opt/nexora-dashboard/nexora_dashboard/api/nexora.py
  mkdir -p /opt/nexora-dashboard/nexora_dashboard/iot/boards
  cp -f /adapter/nexora_dashboard/iot/boards/tabs.py /opt/nexora-dashboard/nexora_dashboard/iot/boards/tabs.py
  cp -f /adapter/nexora_dashboard/iot/plugins/forms.py /opt/nexora-dashboard/nexora_dashboard/iot/plugins/forms.py
  cp -f /adapter/nexora_dashboard/iot/plugins/views.py /opt/nexora-dashboard/nexora_dashboard/iot/plugins/views.py
fi

python3 - <<'PY'
from pathlib import Path
root = Path("/opt/nexora-dashboard/nexora_dashboard")
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

/var/lib/kolla/venv/bin/pip install --no-deps -e /opt/nexora-dashboard
cp -f /opt/nexora-dashboard/nexora_dashboard/enabled/_6*.py /var/lib/kolla/venv/lib/python3.10/site-packages/openstack_dashboard/enabled/
cp -f /opt/nexora-dashboard/nexora_dashboard/api/nexora.py /var/lib/kolla/venv/lib/python3.10/site-packages/openstack_dashboard/api/nexora.py

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
