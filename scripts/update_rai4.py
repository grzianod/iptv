"""Publish Rai 4's HLS master with absolute, freshly issued media URLs."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen


RELINKER = (
    "https://mediapolis.rai.it/relinker/relinkerServlet.htm"
    "?cont=746966&output=7&forceUserAgent=raiplayappletv"
)
USER_AGENT = "raiplayappletv"
URI_ATTRIBUTE = re.compile(r'URI="([^"]+)"')
ROOT = Path(__file__).resolve().parents[1]


def fetch(url, sample=False):
    """Read a playlist, or just a small sample of a media segment."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response:
            data = response.read(1024 if sample else 1_000_001)
            if not data or (not sample and len(data) > 1_000_000):
                raise ValueError("Empty response or oversized playlist")
            return response.url, data
    except HTTPError as error:
        # Avoid putting signed URLs in public Actions logs.
        raise ValueError(f"Upstream HTTP {error.code} from {urlsplit(url).hostname}") from None
    except URLError:
        raise ValueError(f"Network error contacting {urlsplit(url).hostname}") from None


def decode_playlist(data):
    text = data.decode("utf-8-sig")
    if not text.startswith("#EXTM3U"):
        raise ValueError("Upstream did not return an HLS playlist")
    return text


def absolute_url(base, uri):
    result = urljoin(base, uri)
    if urlsplit(result).scheme not in ("http", "https"):
        raise ValueError("Unsupported URI scheme in playlist")
    return result


def rewrite_master(text, base):
    if "#EXT-X-STREAM-INF:" not in text:
        raise ValueError("Expected a multivariant HLS master, not a media playlist")
    result = []
    for line in text.splitlines():
        if line.startswith("#"):
            line = URI_ATTRIBUTE.sub(
                lambda match: 'URI="' + absolute_url(base, match[1]) + '"', line
            )
        elif line.strip():
            line = absolute_url(base, line.strip())
        result.append(line)
    return "\n".join(result) + "\n"


def references(text):
    urls = []
    for line in text.splitlines():
        if line and not line.startswith("#"):
            urls.append(line)
        else:
            urls.extend(URI_ATTRIBUTE.findall(line))
    return list(dict.fromkeys(urls))


def validate_master(master, minimum_hours):
    """Fail closed if token lifetimes or any referenced live media are unsuitable."""
    urls = references(master)
    if not urls:
        raise ValueError("No media references found")
    deadline = time.time() + minimum_hours * 3600
    expiries = []
    for url in urls:
        query = parse_qs(urlsplit(url).query)
        if "tk2" not in query or "tend" not in query:
            raise ValueError("Rai token format changed; inspect the upstream master")
        expiry = int(query["tend"][0])
        if expiry < deadline:
            raise ValueError(f"Media token has less than {minimum_hours:g} hours remaining")
        expiries.append(expiry)
        resolved, data = fetch(url)
        media = decode_playlist(data)
        if "#EXTINF:" not in media or "#EXT-X-ENDLIST" in media:
            raise ValueError("Expected an active live media playlist")
        segment = next(
            (line for line in media.splitlines() if line and not line.startswith("#")),
            None,
        )
        if not segment:
            raise ValueError("Media playlist has no segments")
        fetch(absolute_url(resolved, segment), sample=True)
    return min(expiries)


def refresh(output, minimum_hours=6):
    final_url, data = fetch(RELINKER)
    master = rewrite_master(decode_playlist(data), final_url)
    earliest = validate_master(master, minimum_hours)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    master = master.replace("#EXTM3U\n", f"#EXTM3U\n# Generated at {generated}\n", 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        temporary.write_text(master, encoding="utf-8", newline="\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    expiry = datetime.fromtimestamp(earliest, timezone.utc).isoformat()
    print(f"Updated {output.name}: {master.count('#EXT-X-STREAM-INF:')} video variants")
    print(f"Earliest indicated media-token expiry: {expiry}")
    print("Playlist and segment HTTP checks passed; player compatibility is not tested.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "rai" / "rai4.m3u8")
    parser.add_argument("--minimum-hours", type=float, default=6)
    args = parser.parse_args()
    if args.minimum_hours <= 0:
        parser.error("--minimum-hours must be positive")
    try:
        refresh(args.output, args.minimum_hours)
    except (ValueError, OSError) as error:
        print(f"Refresh failed; previous playlist preserved. {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
