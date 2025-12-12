from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin

def clean_html_for_ai(html: str, url: str) -> str:
    """
    清理 HTML 并保留链接信息
    将 <a href="...">text</a> 转换为 [text](href) 格式，以便 AI 识别链接
    """
    if not html:
        return ""
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # 移除噪音
    for tag in soup(['script', 'style', 'svg', 'iframe', 'noscript', 'headers', 'footer']):
        tag.decompose()
        
    # 尝试定位主要内容区域（可选，如果太严格可能会漏掉新闻列表）
    for selector in ['nav', '.nav', '.header', '.menu']:
        for tag in soup.select(selector):
            tag.decompose()

    # 针对 Amazon News 的特殊清洗
    if "aboutamazon.com" in url:
        # 移除明显的导航和页脚部分
        for selector in ['header', 'footer', '.Navigation', '.Footer', '.SocialShare']:
            for tag in soup.select(selector):
                tag.decompose()
        
        # 移除 "More news" 这种区块
        for tag in soup.find_all(['div', 'section']):
            text = tag.get_text().strip().lower()
            if text.startswith("more news") or text == "see all news":
                tag.decompose()

    # 递归处理文本和链接
    def process_element(element):
        text_parts = []
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    text_parts.append(text)
            elif isinstance(child, Tag):
                if child.name == 'a' and child.has_attr('href'):
                    # 处理链接
                    link_text = child.get_text(separator=' ', strip=True)
                    href = child['href']
                    # 转换为绝对路径
                    full_url = urljoin(url, href) # Use actual URL for base
                    if link_text and len(link_text) > 2: # 忽略太短的链接文本
                        text_parts.append(f"[{link_text}]({full_url})")
                elif child.name in ['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'article', 'section']:
                    # 块级元素，处理子元素并添加换行
                    child_text = process_element(child)
                    if child_text:
                        text_parts.append(f"\n{child_text}\n")
                else:
                    # 其他内联元素或容器
                    child_text = process_element(child)
                    if child_text:
                        text_parts.append(child_text)
        return " ".join(text_parts).strip()

    # 从 body 开始处理
    body = soup.find('body')
    if not body:
        return ""
        
    cleaned_text = process_element(body)
    
    # 清理多余空行
    lines = [line.strip() for line in cleaned_text.split('\n') if line.strip()]
    final_text = '\n'.join(lines)
    
    return final_text[:60000] # 限制长度
