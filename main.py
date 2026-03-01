import os
import feedparser
import google.generativeai as genai

# 1. 抓取新闻
def get_news():
    rss_url = "https://www.theverge.com/rss/index.xml"
    feed = feedparser.parse(rss_url)
    # 提取前10条标题
    titles = [entry.title for entry in feed.entries[:10]]
    return "\n".join(titles)

# 2. 调用 Gemini 生成简报 (替换了原来的 Anthropic 逻辑)
def generate_summary(news_text):
    # 配置 API Key，从 GitHub Secrets 中读取 GEMINI_API_KEY
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # 使用最新的 Gemini 2.0 Flash 模型，速度快且免费额度高
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"请将以下新闻标题总结成一份中文简报，要求排版精美，适合网页阅读：\n\n{news_text}"
    
    response = model.generate_content(prompt)
    return response.text

# 3. 写入 HTML 文件
def save_to_html(content):
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        # 简单加一点样式，让页面好看点
        html_style = "<style>body{font-family:sans-serif; line-height:1.6; padding:20px; max-width:800px; margin:auto;}</style>"
        f.write(f"<html><head>{html_style}</head><body>{content}</body></html>")

if __name__ == "__main__":
    print("正在抓取新闻...")
    news = get_news()
    if not news:
        print("未抓取到新闻内容。")
    else:
        print("正在调用 Gemini AI 生成简报...")
        try:
            summary = generate_summary(news)
            save_to_html(summary)
            print("任务完成！网页已生成在 docs 目录下。")
        except Exception as e:
            print(f"生成失败: {e}")
