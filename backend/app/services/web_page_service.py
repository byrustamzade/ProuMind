from bs4 import BeautifulSoup
import httpx


class WebPageService:
    def fetch_text(self, url: str) -> tuple[str, str]:
        response = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "ProuMindBot/0.1"
            },
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else url

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        return title, "\n".join(lines)


web_page_service = WebPageService()