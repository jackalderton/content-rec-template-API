import requests

def fetch_html(url: str) -> tuple[str, bytes]:
    """
    Fetch a URL and return (final_url, raw_bytes).
    Raises an exception if the request fails.
    """
    resp = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ContentRecAPI/1.0)"}
    )
    resp.raise_for_status()
    return resp.url, resp.content
