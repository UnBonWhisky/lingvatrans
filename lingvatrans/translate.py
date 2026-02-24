#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line interface for Google Translator."""
import argparse
import asyncio
from lingvatrans import Translator


async def async_main():
    """Async main function for translation."""
    parser = argparse.ArgumentParser(
        description='Python Lingvanex Translator as a command-line tool')
    parser.add_argument('text', help='The text you want to translate.')
    parser.add_argument('-d', '--dest', default='en',
        help='The destination language you want to translate. (Default: en)')
    parser.add_argument('-s', '--src', default='auto',
        help='The source language you want to translate. (Default: auto)')
    parser.add_argument('-c', '--detect', action='store_true', default=False,
        help='Detect the language of the text')
    args = parser.parse_args()
    
    translator = Translator()

    try:
        if args.detect:
            result = await translator.detect(args.text)
            result = """
[{lang}, {confidence}] {text}
            """.strip().format(text=args.text,
                lang=result.lang, confidence=result.confidence)
            print(result)
            return

        result = await translator.translate(args.text, dest=args.dest, src=args.src)
        result = u"""
[{src}] {original}
    ->
[{dest}] {text}
        """.strip().format(src=result.src, dest=result.dest, original=result.origin,
                           text=result.text)
        print(result)
    finally:
        await translator.close()


def main():
    """Entry point for the translate command."""
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
