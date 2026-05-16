# -*- coding: utf-8 -*-
"""
Lingvanex Translation API client.

Provides async translate() and detect() methods backed by the
Lingvanex B2B REST API (api-b2b.backenster.com) or the Chrome extension API
(backenster.com/v2).
"""
import uuid as _uuid_mod
import aiohttp
import aiorwlock
from aiohttp_socks import ProxyConnector
from contextlib import asynccontextmanager

from lingvatrans.constants import (
    DEFAULT_BEARER_TOKEN,
    CHROME_BEARER_TOKEN,
    DEFAULT_RAISE_EXCEPTION,
    TRANSLATE_URL,
    GET_LANGUAGES_URL,
    CHROME_TRANSLATE_URL,
    LANGUAGES,
    LANGCODES,
    LANGNAMES,
    ALPHA1_TO_FULL,
)
from lingvatrans.models import Translated, Detected


def _normalize_lang(code: str) -> str:
    """Normalize a language code to Lingvanex full_code format (e.g. 'en_US').

    Accepts:
    - full_code already in the known set: 'en_US', 'fr_FR', ...
    - alpha-1 code:                       'en', 'fr', ...
    - english language name:              'english', 'french', ...

    Raises ValueError if the code cannot be resolved.
    """
    if code == 'auto':
        return 'auto'

    # Already a valid full_code
    if code in LANGUAGES:
        return code

    # Alpha-1 code (e.g. 'en', 'fr', 'zh')
    if code in ALPHA1_TO_FULL:
        return ALPHA1_TO_FULL[code]

    # English language name (e.g. 'english', 'french')
    lower = code.lower()
    if lower in LANGCODES:
        return LANGCODES[lower]

    raise ValueError(
        f'Unknown language code or name: {repr(code)}. '
        'Use a full_code (e.g. "en_US"), an alpha-1 code (e.g. "en"), '
        'or an English language name (e.g. "english").'
    )


class Translator:
    """Lingvanex translation API client.

    :param token: Authentication token. Defaults to the platform's built-in token.
    :type token: str

    :param raise_exception: If True, raises exceptions on API errors
                            instead of returning empty/partial results.
    :type raise_exception: bool

    :param timeout: aiohttp ClientTimeout object.
    :type timeout: aiohttp.ClientTimeout

    :param platform: ``'web'`` (default) uses the B2B web API;
                     ``'browserExtension'`` mimics the Chrome extension.
    :type platform: str
    
    :param ssl: Whether to verify SSL certificates.  Defaults to True.
    :type ssl: bool

    Basic usage::

        import asyncio
        from lingvatrans import Translator

        async def main():
            # Web platform (default)
            async with Translator() as t:
                result = await t.translate('Hello', dest='fr_FR')
                print(result.text)          # 'Bonjour'

            # Chrome extension platform
            async with Translator(platform='browserExtension') as t:
                result = await t.translate('Bonjour', dest='en_US', src='fr_FR')
                print(result.text)

        asyncio.run(main())
    """

    def __init__(
        self,
        token: str = None,
        raise_exception: bool = DEFAULT_RAISE_EXCEPTION,
        timeout: aiohttp.ClientTimeout = None,
        proxy: str = None,
        proxy_auth: tuple = None,
        connector_limit: int = 100,
        platform: str = 'web',
        ssl: bool = True,
    ):
        self.platform = platform

        if platform == 'browserExtension':
            if token is None:
                token = CHROME_BEARER_TOKEN
            # Extension token is sent as-is, no Bearer prefix
            self._token = token
            self._translate_url = CHROME_TRANSLATE_URL
            self._session_uuid = str(_uuid_mod.uuid4())
        else:
            if token is None:
                token = DEFAULT_BEARER_TOKEN
            # Web platform uses Bearer prefix
            if not token.startswith('Bearer '):
                token = 'Bearer ' + token
            self._token = token
            self._translate_url = TRANSLATE_URL
            self._session_uuid = None

        self.raise_exception = raise_exception
        self.timeout = timeout or aiohttp.ClientTimeout(total=30)
        self.connector_limit = connector_limit
        self.proxy = None
        self.proxy_auth = None
        self._proxy_url = proxy
        self._use_proxy_connector = False
        self.rwlock = aiorwlock.RWLock(fast=True)
        self.ssl = ssl

        connector = None
        if proxy is not None:
            if proxy.startswith('socks5') or proxy.startswith('socks4'):
                connector = ProxyConnector.from_url(proxy)
                self._use_proxy_connector = True
            else:
                self.proxy = proxy
                self.proxy_auth = aiohttp.BasicAuth(proxy_auth[0], proxy_auth[1]) if proxy_auth else None

        if connector is None:
            connector = aiohttp.TCPConnector(limit=self.connector_limit, ssl=self.ssl)

        self.connector = connector
        self._session: aiohttp.ClientSession = aiohttp.ClientSession(
            connector=self.connector,
            connector_owner=True,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _get_headers(self) -> dict:
        return {
            'Authorization': self._token,
            # Exclude brotli to avoid ClientPayloadError when aiohttp can't decode 'br'
            'Accept-Encoding': 'gzip, deflate',
        }

    async def _ensure_session(self):
        async with self.rwlock.writer_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(limit=self.connector_limit, ssl=self.ssl)
                self.connector = connector
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    connector_owner=True,
                    timeout=self.timeout,
                    headers=self._get_headers(),
                )

    @asynccontextmanager
    async def _get_session(self):
        """Yield the active session under a reader lock."""
        async with self.rwlock.reader_lock:
            yield self._session

    async def close(self):
        """Close the underlying aiohttp session and connector."""
        async with self.rwlock.writer_lock:
            try:
                if self._session is not None and not self._session.closed:
                    try:
                        await self._session.close()
                    except Exception:
                        pass
            finally:
                self._session = None
                try:
                    if self.connector is not None and not self.connector.closed:
                        try:
                            await self.connector.close()
                        except Exception:
                            pass
                finally:
                    self.connector = None

    async def change_proxy(self, proxy: str = None, proxy_auth: tuple = None):
        """Change the proxy used for requests at runtime.

        :param proxy: Proxy URL, e.g. ``'socks5://foo.bar:1080'`` or
                      ``'https://foo.bar:8080'``.
        :param proxy_auth: ``(username, password)`` tuple for HTTP proxy auth.
        """
        async with self.rwlock.writer_lock:
            # Close existing session/connector first
            if self._session is not None and not self._session.closed:
                await self._session.close()
            self._session = None
            if self.connector is not None and not self.connector.closed:
                await self.connector.close()
            self.connector = None

            self.proxy = None
            self.proxy_auth = None
            self._proxy_url = proxy
            self._use_proxy_connector = False

            connector = None
            if proxy is not None:
                if proxy.startswith('socks5') or proxy.startswith('socks4'):
                    connector = ProxyConnector.from_url(proxy)
                    self._use_proxy_connector = True
                else:
                    self.proxy = proxy
                    self.proxy_auth = aiohttp.BasicAuth(proxy_auth[0], proxy_auth[1]) if proxy_auth else None

            if connector is None:
                connector = aiohttp.TCPConnector(limit=self.connector_limit)

            self.connector = connector
            self._session = aiohttp.ClientSession(
                connector=self.connector,
                connector_owner=True,
                timeout=self.timeout,
                headers=self._get_headers(),
            )

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def translate(self, text: str | list, dest: str = 'en_US', src: str = 'auto') -> Translated:
        """Translate *text* from *src* language into *dest* language.

        :param text: Text to translate.
        :param dest: Destination language.  Accepts full_code (``'fr_FR'``),
                     alpha-1 (``'fr'``), or English name (``'french'``).
        :param src: Source language, or ``'auto'`` for automatic detection
                    (default).  Same formats as *dest*.
        :returns: :class:`~lingvatrans.models.Translated`
        """
        if isinstance(text, list):
            return [await self.translate(item, dest=dest, src=src) for item in text]

        dest_code = _normalize_lang(dest)
        src_code = _normalize_lang(src)

        await self._ensure_session()

        if self.platform == 'browserExtension':
            payload = {
                'to': dest_code,
                'data': [text],
                'platform': 'browserExtension',
                'uuid': self._session_uuid,
                'compact': True,
                'enableTransliteration': False,
            }
            if src_code != 'auto':
                payload['from'] = src_code

            async with self._get_session() as session:
                async with session.post(
                    self._translate_url, json=payload,
                    proxy=self.proxy, proxy_auth=self.proxy_auth,
                ) as resp:
                    status = resp.status
                    data = await resp.json(content_type=None)

                    if status != 200:
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API returned status {status}: {data}')
                        return Translated(src=src, dest=dest, origin=text, text='', extra_data=data)

                    if data.get('err'):
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API error: {data["err"]}')
                        return Translated(src=src, dest=dest, origin=text, text='', extra_data=data)

                    result = data.get('result', '')
                    translated_text = result[0] if isinstance(result, list) else result
                    detected_src = data.get('from', src_code)
                    if src_code == 'auto' and detected_src:
                        src = detected_src

                    return Translated(src=src, dest=dest, origin=text, text=translated_text, extra_data=data)

        else:
            payload = {'to': dest_code, 'text': text}
            if src_code != 'auto':
                payload['from'] = src_code

            async with self._get_session() as session:
                async with session.post(
                    self._translate_url, data=payload,
                    proxy=self.proxy, proxy_auth=self.proxy_auth,
                ) as resp:
                    status = resp.status
                    data = await resp.json(content_type=None)

                    if status != 200:
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API returned status {status}: {data}')
                        return Translated(src=src, dest=dest, origin=text, text='', extra_data=data)

                    if data.get('err'):
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API error: {data["err"]}')
                        return Translated(src=src, dest=dest, origin=text, text='', extra_data=data)

                    translated_text = data.get('result', '')
                    detected_src = data.get('from', src_code)
                    if src_code == 'auto' and detected_src:
                        src = detected_src

                    return Translated(src=src, dest=dest, origin=text, text=translated_text, extra_data=data)

    async def detect(self, text: str | list) -> Detected:  # noqa: E302
        """Detect the language of *text*.

        :param text: Text whose language should be detected.
        :returns: :class:`~lingvatrans.models.Detected` or list of :class:`~lingvatrans.models.Detected`
        """
        if isinstance(text, list):
            return [await self.detect(item) for item in text]

        await self._ensure_session()

        if self.platform == 'browserExtension':
            payload = {
                'to': 'en_US',
                'data': [text],
                'platform': 'browserExtension',
                'uuid': self._session_uuid,
                'compact': True,
                'enableTransliteration': False,
            }

            async with self._get_session() as session:
                async with session.post(
                    self._translate_url, json=payload,
                    proxy=self.proxy, proxy_auth=self.proxy_auth,
                ) as resp:
                    status = resp.status
                    data = await resp.json(content_type=None)

                    if status != 200:
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API returned status {status}: {data}')
                        return Detected(lang='unknown', confidence=None)

                    if data.get('err'):
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API error: {data["err"]}')
                        return Detected(lang='unknown', confidence=None)

                    lang = data.get('sourceLanguage') or data.get('from', 'unknown')
                    confidence = data.get('score', None)
                    return Detected(lang=lang, confidence=confidence)

        else:
            payload = {'to': 'en_US', 'text': text}
            url = self._translate_url + '?platform=dp'

            async with self._get_session() as session:
                async with session.post(url, data=payload, proxy=self.proxy, proxy_auth=self.proxy_auth) as resp:
                    status = resp.status
                    data = await resp.json(content_type=None)

                    if status != 200:
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API returned status {status}: {data}')
                        return Detected(lang='unknown', confidence=None)

                    if data.get('err'):
                        if self.raise_exception:
                            raise Exception(f'Lingvanex API error: {data["err"]}')
                        return Detected(lang='unknown', confidence=None)

                    lang = data.get('sourceLanguage') or data.get('from', 'unknown')
                    confidence = data.get('score', None)
                    return Detected(lang=lang, confidence=confidence)

    async def get_languages(self) -> list:  # noqa: E302
        """Return the list of supported languages from the Lingvanex API.

        Each element is a dict with keys such as ``full_code``,
        ``code_alpha_1``, ``englishName``, ``codeName``, etc.

        :returns: list of language dicts
        """
        await self._ensure_session()

        async with self._get_session() as session:
            async with session.get(GET_LANGUAGES_URL, proxy=self.proxy, proxy_auth=self.proxy_auth) as resp:
                data = await resp.json(content_type=None)

                if data.get('err'):
                    if self.raise_exception:
                        raise Exception(f'Lingvanex API error: {data["err"]}')
                    return []

                return data.get('result', [])
