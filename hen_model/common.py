"""Shared pieces for the hen model scripts: the class list, and small clients
for Frigate's and Label Studio's APIs."""

import sys
from pathlib import Path

import requests
import yaml

HERE = Path(__file__).resolve().parent

# Label Studio serves the image folder at this path inside its container
# (hen_model/label-studio/docker-compose.yml mounts it there).
LS_ROOT = "/hens"

# Box colours in Label Studio, in class order.
COLOURS = ["#e8b44a", "#4a90d9", "#9b59b6", "#8e6e53", "#e67e22", "#7f8c8d",
           "#2c3e50", "#c0392b", "#16a085", "#d35400", "#27ae60", "#f39c12"]


def load_classes():
    """The class list from classes.yaml, in class-number order."""
    with open(HERE / "classes.yaml") as f:
        classes = yaml.safe_load(f)["classes"]
    names = [c["name"] for c in classes]
    if len(set(names)) != len(names):
        sys.exit("classes.yaml: class names must be unique")
    return classes


def label_config(classes):
    """Label Studio labelling interface: boxes on an image, one label per class."""
    labels = "\n".join(
        f'    <Label value="{c["name"]}" background="{COLOURS[i % len(COLOURS)]}"/>'
        for i, c in enumerate(classes))
    return f"""<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <RectangleLabels name="label" toName="image">
{labels}
  </RectangleLabels>
</View>"""


def image_url(rel_path):
    """How a task points at an image in the shared folder (Label Studio's
    local files), from its path relative to the folder."""
    return "/data/local-files/?d=" + Path(rel_path).as_posix()


def rel_from_url(url):
    """The image's path relative to the shared folder, from a task's URL."""
    return url.split("?d=", 1)[1] if "?d=" in url else url


def base_url(url):
    """An address as typed into a setting, with http:// added if left off."""
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = "http://" + url
    return url


def unreachable(what, url, setting, example, error):
    reason = str(error.__context__ or error) if isinstance(error, requests.ConnectionError) else str(error)
    sys.exit(f"Can't reach {what} at {url}: {reason[:200]}\n"
             f"Check {setting} (on the same server as the harvester: {example}).")


class Frigate:
    """Frigate's HTTP API. Logs in when given a user (port 8971); port 5000
    needs no login."""

    def __init__(self, url, user=None, password=None):
        self.url = base_url(url)
        self.session = requests.Session()
        try:
            if user:
                r = self.session.post(f"{self.url}/api/login", json={"user": user, "password": password},
                                      timeout=30)
                if r.status_code != 200:
                    sys.exit(f"Frigate login failed ({r.status_code}): check the user and password")
            else:
                self.session.get(f"{self.url}/api/version", timeout=30).raise_for_status()
        except requests.RequestException as e:
            unreachable("Frigate", self.url, "FRIGATE_URL / --frigate", "http://127.0.0.1:8971", e)

    def get(self, path, **params):
        r = self.session.get(f"{self.url}/api/{path}", params=params, timeout=60)
        r.raise_for_status()
        return r


class LabelStudio:
    """Label Studio's HTTP API. Takes the token from Account & Settings:
    either a personal access token (newer installs) or a legacy token."""

    def __init__(self, url, token):
        self.url = base_url(url)
        self.session = requests.Session()
        if token.count(".") == 2:  # personal access token (a JWT): swap it for a short-lived one
            try:
                r = requests.post(f"{self.url}/api/token/refresh", json={"refresh": token.strip()}, timeout=30)
            except requests.RequestException as e:
                unreachable("Label Studio", self.url, "LABEL_STUDIO_URL / --ls", "http://127.0.0.1:8085", e)
            if r.status_code != 200:
                sys.exit(f"Label Studio refused the token ({r.status_code}): create a new personal access token")
            self.session.headers["Authorization"] = f"Bearer {r.json()['access']}"
        else:
            self.session.headers["Authorization"] = f"Token {token.strip()}"

    def request(self, method, path, **kwargs):
        try:
            r = self.session.request(method, f"{self.url}/api/{path}", timeout=300, **kwargs)
        except requests.RequestException as e:
            unreachable("Label Studio", self.url, "LABEL_STUDIO_URL / --ls", "http://127.0.0.1:8085", e)
        if not r.ok:
            sys.exit(f"Label Studio {method} /api/{path} failed ({r.status_code}): {r.text[:300]}")
        return r.json() if r.content else None

    def project(self, title, classes, create=True):
        """The project with this title, created (with storage for the shared
        folder) if it doesn't exist yet and create is set."""
        found = self.request("GET", "projects", params={"title": title})
        found = found["results"] if isinstance(found, dict) else found
        for p in found:
            if p["title"] == title:
                return p["id"]
        if not create:
            sys.exit(f"No Label Studio project called {title!r}")
        p = self.request("POST", "projects", json={"title": title, "label_config": label_config(classes)})
        self.request("POST", "storages/localfiles", json={
            "project": p["id"], "title": "Hen images", "path": f"{LS_ROOT}/images",
            "use_blob_urls": True, "regex_filter": ".*jpg"})
        return p["id"]
