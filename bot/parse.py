import requests
import re

from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin


HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }

def parselink(link):
    # парсим ИД из ссылки
    try:
        return re.search(r'/([^/]+)/?$', link).group(1)
    except:
        return None

def parseFoto(link):
    
    try:
        response = requests.get(link, headers=HEADERS, timeout=15)
        soup = bs(response.text, 'html.parser')
        
        """
        # Поиск изображения через Open Graph теги
        og_image = soup.find('meta', property='og:image')
        if og_image and 'content' in og_image.attrs:
            image_url = urljoin(link, og_image['content'])
            # Проверяем, что URL ведет на изображение
            try:
                img_response = requests.head(image_url, headers=HEADERS, timeout=10)
                print(img_response)
                content_type = img_response.headers.get('Content-Type', '')
                print(content_type)
                if content_type.startswith('image/'):
                    return image_url
                else:
                    print(f"URL {image_url} имеет неверный Content-Type: {content_type}")
            except Exception as e:
                print(f"Ошибка проверки изображения {image_url}: {e}")
        """

        # Резервный поиск
        image_div = soup.find('div', class_='main_img')
        if image_div:
            img_tag = image_div.find('img')
            if img_tag and 'src' in img_tag.attrs:
                image_url = urljoin(link, img_tag['src'])
                # Проверяем Content-Type для резервного URL
                try:
                    img_response = requests.head(image_url, headers=HEADERS, timeout=10)
                    content_type = img_response.headers.get('Content-Type', '')
                    if content_type.startswith('image/'):
                        return image_url
                    else:
                        print(f"Резервный URL {image_url} имеет неверный Content-Type: {content_type}")
                except Exception as e:
                    print(f"Ошибка проверки резервного изображения {image_url}: {e}")
        
        return None

    except Exception as e:
        print(f"Ошибка парсинга изображения: {e}")
        return None

def parseMainText(link):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }
    
    try:
        response = requests.get(link, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    
    try:
        soup = bs(response.text, 'html.parser')
    
        # Поиск основного изображения
        text_div = soup.find('div', class_='text')

        return text_div.get_text(strip=True) if text_div else ""
    except Exception as e:
        print(f"Ошибка парсинга текста: {e}")
        return ""

def parselink_sb(link: str) -> str:
    """Извлекает ID из URL sb.by"""
    match = re.search(r'/articles/(.+?)\.html', link)
    return match.group(1) if match else None

def parseFoto_sb(link: str) -> str:
    """Парсит фото из статьи sb.by с обработкой CDN"""
    try:
        response = requests.get(link, headers=HEADERS, timeout=15)
        soup = bs(response.text, 'html.parser')
        
        # Попробуем найти изображение в Open Graph
        og_image = soup.find('meta', property='og:image')
        if og_image and 'content' in og_image.attrs:
            image_url = urljoin(link, og_image['content'])
            return image_url  # Возвращаем URL без проверки
        
        # Альтернативный поиск в контенте статьи
        img_tag = soup.find('div', class_='article-text').find('img')
        if img_tag and 'src' in img_tag.attrs:
            return urljoin(link, img_tag['src'])
            
        return None
        
    except Exception as e:
        print(f"Ошибка парсинга фото (sb.by): {e}")
        return None

def parseMainText_sb(link: str) -> str:
    """Парсит основной текст статьи sb.by"""
    try:
        response = requests.get(link, headers=HEADERS, timeout=15)
        soup = bs(response.text, 'html.parser')
        text_div = soup.find('div', class_='article-text')
        return text_div.get_text(strip=True) if text_div else ""
    except Exception as e:
        print(f"Ошибка парсинга текста (sb.by): {e}")
        return ""

def parse_summary_sb(link: str) -> str:
    """Парсит краткое описание из тега <b> для sb.by"""
    try:
        response = requests.get(link, headers=HEADERS, timeout=15)
        soup = bs(response.text, 'html.parser')
        article_body = soup.find('div', itemprop='articleBody')
        
        if article_body:
            # Ищем первый тег <b> внутри articleBody
            summary_tag = article_body.find('b')
            if summary_tag:
                # Удаляем все вложенные теги из summary
                return re.sub(r'\s+', ' ', summary_tag.get_text(strip=True))
        
        # Фолбэк: возвращаем пустую строку
        return ""
    
    except Exception as e:
        print(f"Ошибка парсинга summary (sb.by): {e}")
        return ""


def main():
    link = 'https://www.sb.by/articles/rss/'
    print(parseFoto_sb(link))
    response = requests.get(link, headers=HEADERS, timeout=15)
    soup = bs(response.text, 'html.parser')
    print(soup)

if __name__ == '__main__':
    main()