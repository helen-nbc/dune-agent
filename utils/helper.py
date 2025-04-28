from urllib.parse import urlencode


def generate_search_url(base_url: str, input: str) -> str:
    search_url = f"{base_url}?{urlencode(input)}"
    return search_url