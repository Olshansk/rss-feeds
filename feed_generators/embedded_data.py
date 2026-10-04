"""Read JSON objects embedded in Next.js HTML without evaluating JavaScript."""

import json

from bs4 import BeautifulSoup


def next_objects(html):
    """Yield dictionaries from Next.js Flight records, including split chunks.

    How:
    1. Decode only JSON arguments to the known Flight push wrapper.
    2. Join string chunks and parse JSON records after their row identifiers.
    3. Walk nested objects and arrays without evaluating script content.
    """
    chunks = []
    decoder = json.JSONDecoder()
    for script in BeautifulSoup(html, "html.parser").find_all("script"):
        text = script.string or ""
        marker = "self.__next_f.push("
        if marker not in text:
            continue
        argument = text.split(marker, 1)[1]
        try:
            value, _ = decoder.raw_decode(argument)
        except ValueError:
            continue
        if isinstance(value, list) and len(value) > 1 and isinstance(value[1], str):
            chunks.append(value[1])

    def walk(value):
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from walk(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from walk(nested)

    records = dict.fromkeys(record for stream in ["".join(chunks), *chunks] for record in stream.splitlines())
    for record in records:
        _, separator, payload = record.partition(":")
        if not separator:
            continue
        try:
            value, _ = decoder.raw_decode(payload)
        except ValueError:
            continue
        yield from walk(value)
