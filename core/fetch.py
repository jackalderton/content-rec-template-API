import requests

def fetch_html(url: str, timeout: int = 30) -> tuple[str, bytes]:
    """
    Fetch HTML for a URL with a simple requests.get.
    Returns (final_url, content_bytes).
    """
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ContentRecTool/1.0)"}
    )
    resp.raise_for_status()
    return resp.url, resp.content
