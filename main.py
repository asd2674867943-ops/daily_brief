import os
import feedparser
from anthropic import Anthropic

# 1. 抓取新闻 (这里以科技新闻为例)
def get_news():
    rss_url = "https://www.theverge.com/rss/index.xml"
    feed = feedparser.parse(rss_url)
    titles = [entry.title for entry in feed.entries[:10]]
    return "\n".join(titles)

# 2. 调用 Claude 生成简报
def generate_summary(news_text):
    client = Anthropic(api_key=os.environ.get("CLAUDE_API_KEY"))
    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        messages=[{"role": "user", "content": f"请将以下新闻标题总结成一份中文简报，要求排版精美，适合网页阅读：\n\n{news_text}"}]
    )
    return message.content[0].text

# 3. 写入 HTML 文件
def save_to_html(content):
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(f"<html><body>{content}</body></html>")

if __name__ == "__main__":
    print("正在抓取新闻...")
    news = get_news()
    print("正在调用 AI 生成简报...")
    summary = generate_summary(news)
    save_to_html(summary)
    print("任务完成！网页已生成在 docs 目录下。")
