import os
import json
import feedparser
from datetime import datetime
from openai import OpenAI  # 切换为 OpenAI 库

def get_all_news():
    sources = {
        "tech": "https://hnrss.org/frontpage",
        "general": "https://rss.nytimes.com/services/xml/rss/nyt/world.xml"
    }
    news_data = {}
    for category, url in sources.items():
        feed = feedparser.parse(url)
        # 保持你原来的逻辑：取前5条
        news_data[category] = [{"title": e.title, "link": e.link} for e in feed.entries[:5]]
    return news_data

def generate_ai_summary(news_dict):
    # 从环境变量获取 DEEPSEEK_API_KEY
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "未配置 API Key，请检查 GitHub Secrets。"

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
    # 提取所有标题用于总结
    all_titles = "\n".join([item['title'] for cat in news_dict.values() for item in cat])
    prompt = f"请将以下新闻总结成一段150字以内的中文精炼简报，要求语气专业，包含重点资讯：\n\n{all_titles}"
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的新闻摘要助手。"},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI 生成失败: {e}")
        return "今日资讯已更新，请查看下方列表。"

def save_data(news_dict, ai_summary):
    os.makedirs("data", exist_ok=True)
    final_data = {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ai_summary": ai_summary,
        "news": news_dict,
        "model_used": "DeepSeek-V3" # 更新模型标识
    }
    with open("data/data.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    print("开始执行新闻抓取...")
    news = get_all_news()
    print("正在请求 DeepSeek 生成总结...")
    summary = generate_ai_summary(news)
    print("正在保存数据...")
    save_data(news, summary)
    print("执行完毕！")
