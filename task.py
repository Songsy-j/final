import re
import sqlite3
import time
from bs4 import BeautifulSoup
import requests

DB_PATH = "google_reps.db"
URL = "https://github.com/google?tab=repositories"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def parse_stars(container) -> int:
    
    star_link = container.select_one("a[href$='/stargazers']")
    if not star_link:
        return 0

    raw_text = star_link.get_text(" ", strip=True).replace(",", "").lower()
   
    match = re.search(r"(\d+(?:\.\d+)?)\s*(k)?", raw_text)
    if not match:
        return 0

    num = float(match.group(1))
    if match.group(2) == "k":
        return int(num * 1000)
    return int(num)


def scrape_google_repos(url: str) -> list[tuple[str, str, int]]:
   
    print("ページを取得しています...")
    time.sleep(1)
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

   
    repo_links = soup.select("a[href^='/google/']")
    containers = []
    seen_ids = set()

    for link in repo_links:
        href = link.get("href", "").strip("/")
        parts = href.split("/")
       
        if len(parts) != 2 or parts[0].lower() != "google":
            continue
        repo_name = parts[1]
        if not repo_name or repo_name.startswith("?"):
            continue

        container = link.find_parent(["li", "div"])
        
        parent = link
        chosen = None
        for _ in range(5):
            parent = parent.parent
            if not parent:
                break
            if parent.name in ("li", "article"):
                chosen = parent
                break
            if parent.find("span", attrs={"itemprop": "programmingLanguage"}) or parent.select_one("a[href$='/stargazers']"):
                chosen = parent
                break

        target = chosen or container
        if target and id(target) not in seen_ids:
            seen_ids.add(id(target))
            containers.append((repo_name, target))

    results: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()

    for fallback_name, item in containers:
        name_tag = item.find("a", attrs={"itemprop": "name codeRepository"})
        name = name_tag.get_text(strip=True) if name_tag else fallback_name
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        lang_tag = item.find("span", attrs={"itemprop": "programmingLanguage"})
        language = lang_tag.get_text(strip=True) if lang_tag else "Unknown"

        stars = parse_stars(item)
        results.append((name, language, stars))

    return results


def init_and_save_db(db_path: str, records: list[tuple[str, str, int]]) -> None:
    
    con = sqlite3.connect(db_path)
    cursor = con.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            language TEXT,
            stars INTEGER
        )
        """
    )

    for name, language, stars in records:
        cursor.execute(
            """
            INSERT INTO repositories (name, language, stars)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                language = excluded.language,
                stars = excluded.stars
            """,
            (name, language, stars),
        )

    con.commit()
    con.close()
    print("データベースに保存されました")


def display_repositories(db_path: str) -> None:
   
    con = sqlite3.connect(db_path)
    cursor = con.cursor()

    print("== データベースの取得結果 ==")
    cursor.execute(
        """
        SELECT id, name, language, stars
        FROM repositories
        ORDER BY stars DESC, id ASC
        """
    )
    rows = cursor.fetchall()

    for row in rows:
        print(
            f"ID: {row[0]} | リポジトリ名: {row[1]} | "
            f"言語: {row[2]} | スター数: {row[3]}"
        )

    print(f"合計件数: {len(rows)} 件")
    con.close()


def main() -> None:
    records = scrape_google_repos(URL)
    init_and_save_db(DB_PATH, records)
    display_repositories(DB_PATH)


if __name__ == "__main__":
    main()