import asyncio
import os
from datetime import datetime
from urllib.parse import urljoin
from crawl4ai import AsyncWebCrawler
from typing import Dict, Any, List
from pydantic import BaseModel

class PaginationResult(BaseModel):
    """Represents the result of pagination detection and scraping"""
    pages_content: List[Dict[str, Any]]
    total_pages: int
    success: bool
    error: str = None

async def scrape_webpage(url: str, handle_pagination: bool = False, max_pages: int = 10) -> Dict[str, Any]:
    """
    Scrapes a webpage and returns markdown content and statistics
    
    Args:
        url (str): The URL to scrape
        handle_pagination (bool): Whether to handle pagination
        max_pages (int): Maximum number of pages to scrape if pagination is enabled
    """
    try:
        pages_content = []
        current_page = 1
        current_url = url
        combined_stats = {
            "total_internal_links": 0,
            "total_external_links": 0,
            "total_images": 0,
            "total_videos": 0,
            "total_audios": 0
        }

        async with AsyncWebCrawler(verbose=True) as crawler:
            while True:
                result = await crawler.arun(
                    url=current_url,
                    exclude_external_links=False,
                    exclude_social_media_links=False,
                    exclude_external_images=False,
                    load_more_selectors=[
                        'button:contains("More")',
                        'button:contains("Load More")',
                        'a:contains("More")',
                        '.load-more',
                        '#more',
                        '.more-button'
                    ]
                )

                if not result.success:
                    return {
                        "success": False,
                        "error": result.error_message,
                        "status_code": result.status_code
                    }

                # Calculate statistics for current page
                stats = {
                    "total_internal_links": len(result.links.get("internal", [])),
                    "total_external_links": len(result.links.get("external", [])),
                    "total_images": len(result.media.get("images", [])),
                    "total_videos": len(result.media.get("videos", [])),
                    "total_audios": len(result.media.get("audios", []))
                }

                # Update combined statistics
                for key in combined_stats:
                    combined_stats[key] += stats[key]

                # Store page content
                pages_content.append({
                    "url": current_url,
                    "content": result.markdown,
                    "page_number": current_page,
                    "statistics": stats
                })

                if not handle_pagination or current_page >= max_pages:
                    break

                # Try to find and click "Load More" button first
                next_page_url = None
                load_more_clicked = False
                
                for link in result.links.get("internal", []):
                    href = link.get("href", "")
                    text = link.get("text", "").lower()
                    if "more" in text:
                        if link.get("is_button", False):
                            # This is a "Load More" button that was clicked
                            load_more_clicked = True
                            current_url = url  # Stay on same URL since content is loaded dynamically
                            break
                        else:
                            # This might be a "Next Page" link
                            next_page_url = urljoin(current_url, href)
                            break

                if load_more_clicked:
                    # Content was loaded dynamically, continue with same URL
                    current_page += 1
                    await asyncio.sleep(1.0)  # Rate limiting
                    continue
                elif not next_page_url:
                    break

                current_url = next_page_url
                current_page += 1
                await asyncio.sleep(1.0)  # Rate limiting

            return {
                "success": True,
                "pages": pages_content,
                "total_pages": current_page,
                "combined_statistics": combined_stats,
                "status_code": result.status_code
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status_code": None
        }

def print_statistics(stats: Dict[str, int], total_pages: int = 1) -> None:
    """
    Prints the statistics in a formatted way
    """
    print("\n=== Statistics Report ===")
    print(f"Total Pages Scraped: {total_pages}")
    print(f"Internal Links Found: {stats['total_internal_links']}")
    print(f"External Links Found: {stats['total_external_links']}")
    print(f"Images Found: {stats['total_images']}")
    print(f"Videos Found: {stats['total_videos']}")
    print(f"Audio Elements Found: {stats['total_audios']}")
    print("=====================")

async def main():
    # Get URL from user
    url = input("Enter the webpage URL to scrape: ")
    handle_pagination = input("Handle pagination? (y/n): ").lower() == 'y'
    max_pages = 10
    
    if handle_pagination:
        try:
            max_pages = int(input("Maximum number of pages to scrape (default 10): ") or 10)
        except ValueError:
            print("Invalid input, using default value of 10 pages")
    
    print(f"\nScraping {url}...")
    result = await scrape_webpage(url, handle_pagination, max_pages)

    if not result["success"]:
        print(f"Error: {result.get('error')}")
        print(f"Status Code: {result.get('status_code')}")
        return

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y_%m_%d__%H_%M_%S")
    output_dir = f"output/{url.split('//')[1].split('/')[0]}_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    # Print combined statistics
    print_statistics(result["combined_statistics"], result["total_pages"])

    # Save content from all pages
    for page in result["pages"]:
        page_filename = f"page_{page['page_number']}.md"
        with open(os.path.join(output_dir, page_filename), "w", encoding="utf-8") as f:
            f.write(f"# Page {page['page_number']}\n")
            f.write(f"URL: {page['url']}\n\n")
            # Remove extra whitespace and empty lines while preserving markdown formatting
            cleaned_content = "\n".join(line.strip() for line in page["content"].splitlines() if line.strip())
            f.write(cleaned_content)

    print(f"\nFiles saved in directory: {output_dir}")
    print(f"Total pages scraped: {result['total_pages']}")

if __name__ == "__main__":
    asyncio.run(main())
