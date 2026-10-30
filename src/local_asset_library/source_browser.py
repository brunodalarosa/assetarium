"""Read-only browsing of one library folder through the desktop presentation services.

It reads the folder's working catalog when there is one, so the Asset sources tab shows assets without previews
yet and results not published yet (decision 0023); search keeps reading the published library.
"""
from .config import ConfigError
from .desktop_service import DesktopService
from .interactive_preview import InteractivePreviewService
from .publication import generation
from .sources import bound, get_source, source_status


class SourceBrowser:
    def __init__(self, config, preview_history):
        self.config = config
        self.preview_history = preview_history
        self.sessions = {}

    def session(self, key):
        # Resolve registration on every call: disabled is browsable, removed is not.
        source = get_source(self.config, key)
        scoped = bound(self.config, source)
        from .incremental import working
        if working(scoped).output_path('data', 'catalog.sqlite').is_file():
            scoped = working(scoped)
        session = self.sessions.get(key)
        if session is None or session[0].config != scoped:
            service = DesktopService(scoped)
            session = (service, InteractivePreviewService(service, history=self.preview_history))
            self.sessions[key] = session
        return source, session

    def call(self, operation, key, *args):
        if operation not in {'browse', 'asset', 'thumbnail', 'image_view', 'reveal', 'prepare', 'file', 'fault', 'release'}:
            raise ConfigError('Unknown source browsing operation')
        source, (service, preview) = self.session(key)
        if operation == 'browse':
            if not service.config.output_path('data', 'catalog.sqlite').is_file():
                saved = source_status(self.config, source)
                return {'status': 'browse', 'items': [], 'total_count': 0, 'shown_count': 0,
                        'generation': generation(service.config), 'source': source,
                        'available': False, 'reason': saved.get('scan_fault') or
                        ('Process this source from the library to prepare its assets for browsing.'
                         if saved.get('scanned') else 'Scan and process this source from the library to browse its assets.')}
            result = service.browse({}, *args)
            return dict(result, source=source, available=True)
        target = service if operation in {'asset', 'thumbnail', 'image_view', 'reveal'} else preview
        return getattr(target, operation)(*args)
