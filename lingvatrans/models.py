# -*- coding: utf-8 -*-
"""Data models for lingvatrans results."""


class Translated:
    """Translation result object.

    :param src: source language full_code (e.g. 'en_US'), or 'auto'
    :param dest: destination language full_code (e.g. 'fr_FR')
    :param origin: original text
    :param text: translated text
    :param extra_data: raw response data from the API
    """

    def __init__(self, src, dest, origin, text, extra_data=None):
        self.src = src
        self.dest = dest
        self.origin = origin
        self.text = text
        self.extra_data = extra_data

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return (
            u'Translated(src={src}, dest={dest}, text={text})'.format(
                src=self.src,
                dest=self.dest,
                text=self.text,
            )
        )

    def __repr__(self):
        return self.__unicode__()


class Detected:
    """Language detection result object.

    :param lang: detected language full_code (e.g. 'en_US')
    :param confidence: confidence score (0.0 to 1.0), may be None if not provided
    """

    def __init__(self, lang, confidence=None):
        self.lang = lang
        self.confidence = confidence

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return u'Detected(lang={lang}, confidence={confidence})'.format(
            lang=self.lang,
            confidence=self.confidence,
        )

    def __repr__(self):
        return self.__unicode__()
