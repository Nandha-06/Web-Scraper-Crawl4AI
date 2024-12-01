import os
import json
from typing import List, Dict
import google.generativeai as genai
from dotenv import load_dotenv
import logging
from urllib.parse import urljoin
import re

# Configure logging
logging.basicConfig(level=logging.INFO)

def configure_gemini_api() -> bool:
    """Configure Gemini API with key from environment"""
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logging.error("GEMINI_API_KEY not found in environment variables")
            return False
        
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        logging.error(f"Failed to configure Gemini API: {str(e)}")
        return False

def read_first_page_content(output_dir: str) -> tuple[str, str]:
    """Read the content of page_1.md from the specified output directory"""
    page_file = os.path.join(output_dir, "page_1.md")
    if not os.path.exists(page_file):
        logging.error(f"First page file not found in {output_dir}")
        return None, None
    
    try:
        with open(page_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract base URL from second line
            lines = content.split('\n')
            for line in lines:
                if line.startswith('URL: '):
                    base_url = line.replace('URL: ', '').strip()
                    return content, base_url
    except Exception as e:
        logging.error(f"Error reading first page content: {str(e)}")
    return None, None

def detect_pagination_elements(markdown_content: str, base_url: str) -> List[str]:
    """Use Gemini to detect pagination links from markdown content"""
    try:
        if not configure_gemini_api():
            return []

        # Enhanced pagination patterns
        pagination_patterns = [
            # Existing patterns
            r'page-\d+\.html',
            r'page_num=\d+',
            r'/page/\d+/?',
            r'page=\d+',
            r'/p/\d+',
            r'[?&]p=\d+',
            # New patterns
            r'offset=\d+',
            r'start=\d+',
            r'[?&]from=\d+',
            r'/load-more/\d+',
            r'cursor=[\w-]+',  # For cursor-based pagination
        ]

        # Enhanced prompt with more specific instructions
        prompt = f"""
        Extract all pagination URLs from this markdown content.
        Base URL: {base_url}

        Rules:
        1. Look for these pagination patterns:
           - Links containing page numbers (page=N, page-N, /page/N)
           - Navigation elements with text: Next, Previous, Load More, Show More
           - Numeric page indicators (1, 2, 3...)
           - Infinite scroll markers or load more buttons
           - Arrow symbols (», ›, ⟩) indicating next page
        2. Return only the pagination-related URLs
        3. Format: one URL per line
        4. Include the full URL path
        5. Exclude the current page URL
        6. Look for both visible text and href attributes
        7. Check for data-* attributes that might indicate pagination

        Content to analyze:
        {markdown_content}
        """

        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config={
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40
            }
        )

        completion = model.generate_content(prompt)
        response_text = completion.text.strip()
        
        # Process URLs with validation
        urls = []
        for line in response_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Validate and normalize URL
            try:
                # Handle relative URLs
                if not line.startswith('http'):
                    from urllib.parse import urlparse, urljoin
                    parsed_base = urlparse(base_url)
                    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
                    
                    if line.startswith('//'):
                        url = f"{parsed_base.scheme}:{line}"
                    elif line.startswith('/'):
                        url = urljoin(base_domain, line)
                    else:
                        url = urljoin(base_url, line)
                else:
                    url = line

                # Validate URL matches pagination patterns
                if any(re.search(pattern, url, re.IGNORECASE) for pattern in pagination_patterns):
                    urls.append(url)
                    
            except Exception as e:
                logging.warning(f"Invalid URL found: {line} - {str(e)}")
                continue

        # Remove duplicates while preserving order
        unique_urls = list(dict.fromkeys(urls))
        
        if unique_urls:
            logging.info(f"Found {len(unique_urls)} pagination URLs: {unique_urls}")
        
        return unique_urls

    except Exception as e:
        logging.error(f"Error in pagination detection: {str(e)}")
        return []

def get_pagination_urls(output_dir: str) -> List[str]:
    """Get pagination URLs from the specified output directory"""
    try:
        content, base_url = read_first_page_content(output_dir)
        if not content or not base_url:
            return []

        return detect_pagination_elements(content, base_url)

    except Exception as e:
        logging.error(f"Error getting pagination URLs: {str(e)}")
        return []