import os
import json
import feedparser
from datetime import datetime
from google import genai

def get_all_news():
    sources = {
        "tech": "https://www.theverge.com/rss/index.xml",
        "general": "https://feeds.bbci.co.uk/news/world/rss.xml"
    }
    news_data = {}
    for category, url in sources.items():
        feed = feedparser.parse(url)
        news_data[category] = [{"title": e.title, "link": e.link} for e in feed.entries[:5]]
    return news_data

def generate_ai_summary(news_dict):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    all_titles = "\n".join([item['title'] for cat in news_dict.values() for item in cat])
    prompt = f"请将以下新闻总结成一段150字以内的中文精炼简报，要求语气专业，包含重点资讯：\n\n{all_titles}"
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"AI 生成失败: {e}")
        return "今日资讯已更新，请查看下方列表。"

def save_data(news_dict, ai_summary):
    os.makedirs("data", exist_ok=True)
    final_data = {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ai_summary": ai_summary,
        "news_list": news_dict,
        "model_used": "Gemini-2.0-Flash"
    }
    with open("data/data.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    print("🚀 开始执行新闻抓取...")
    news = get_all_news()
    print("🤖 正在请求 Gemini 生成总结...")
    summary = generate_ai_summary(news)
    print("💾 正在保存数据到 data/data.json...")
    save_data(news, summary)
    print("✅ 执行完毕！请刷新网页查看。")
