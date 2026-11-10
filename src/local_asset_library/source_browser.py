"""Read-only detail, card images and 3D previews of one library folder's assets, through the desktop services.

It reads the folder's working catalog when there is one, so the Asset sources tab shows assets without previews
yet and results not published yet (decision 0023); search keeps reading the published library.
"""
from .config import ConfigError
from .desktop_service import DesktopService
from .interactive_preview import InteractivePreviewService
from .sources import bound, get_source


class SourceBrowser:
    def __init__(self, config, preview_history):
        self.config = config
        self.preview_history = preview_history
        self.sessions = {}

    def session(self, key):
        # Resolve registration on every call: disabled is browsable, removed is not.
        scoped = bound(self.config, get_source(self.config, key))
        from .incremental import working
        if working(scoped).output_path('data', 'catalog.sqlite').is_file():
            scoped = working(scoped)
        session = self.sessions.get(key)
        if session is None or session[0].config != scoped:
            service = DesktopService(scoped)
            session = (service, InteractivePreviewService(service, history=self.preview_history))
            self.sessions[key] = session
        return session

    def call(self, operation, key, *args):
        if operation not in {'asset', 'thumbnail', 'image_view', 'reveal', 'prepare', 'file', 'fault', 'release'}:
            raise ConfigError('Unknown source browsing operation')
        service, preview = self.session(key)
        target = service if operation in {'asset', 'thumbnail', 'image_view', 'reveal'} else preview
        return getattr(target, operation)(*args)
