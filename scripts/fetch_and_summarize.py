#!/usr/bin/env python3
"""
每日新闻自动抓取与 AI 总结脚本
- 从多个官方媒体 RSS 抓取今日要闻
- 使用 Claude API 进行智能总结
- 输出 JSON 供前端读取
"""

import os
import json
import time
import hashlib
import logging
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from dateutil import parser as dateparser
import anthropic

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ─── 北京时间 ────────────────────────────────────────────
BJT = timezone(timedelta(hours=8))

def now_bjt():
    return datetime.now(BJT)

def today_str():
    return now_bjt().strftime('%Y-%m-%d')

# ─── 新闻源配置 ──────────────────────────────────────────
NEWS_SOURCES = {
    "cctv_type": [
        # 新华社 RSS（最接近新闻联播内容）
        {
            "name": "新华社要闻",
            "url": "http://www.xinhuanet.com/politics/news_politics.xml",
            "label": "新华社",
            "category": "cctv"
        },
        {
            "name": "新华社时政",
            "url": "https://www.xinhuanet.com/rss/shizheng.xml",
            "label": "新华社时政",
            "category": "cctv"
        },
        # 人民日报
        {
            "name": "人民日报要闻",
            "url": "http://www.people.com.cn/rss/politics.xml",
            "label": "人民日报",
            "category": "cctv"
        },
    ],
    "tech": [
        {
            "name": "Hacker News Top",
            "url": "https://hnrss.org/frontpage",
            "label": "HackerNews",
            "category": "tech"
        },
        {
            "name": "MIT Technology Review",
            "url": "https://www.technologyreview.com/feed/",
            "label": "MIT-TR",
            "category": "tech"
        },
        {
            "name": "The Verge",
            "url": "https://www.theverge.com/rss/index.xml",
            "label": "TheVerge",
            "category": "tech"
        },
        {
            "name": "Ars Technica",
            "url": "http://feeds.arstechnica.com/arstechnica/index",
            "label": "ArsTechnica",
            "category": "tech"
        },
    ],
    "ai": [
        {
            "name": "VentureBeat AI",
            "url": "https://venturebeat.com/category/ai/feed/",
            "label": "VentureBeat",
            "category": "ai"
        },
        {
            "name": "AI News",
            "url": "https://www.artificialintelligence-news.com/feed/",
            "label": "AI-News",
            "category": "ai"
        },
        {
            "name": "DeepLearning.AI Blog",
            "url": "https://www.deeplearning.ai/blog/feed/",
            "label": "DeepLearning.AI",
            "category": "ai"
        },
    ],
    "general": [
        {
            "name": "BBC Chinese",
            "url": "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",
            "label": "BBC中文",
            "category": "general"
        },
        {
            "name": "Reuters Top News",
            "url": "https://feeds.reuters.com/reuters/topNews",
            "label": "路透社",
            "category": "general"
        },
        {
            "name": "Associated Press",
            "url": "https://feeds.apnews.com/apnews/topnews",
            "label": "AP通讯",
            "category": "general"
        },
    ]
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; DailyBriefBot/1.0; +https://github.com)',
    'Accept': 'application/rss+xml, application/xml, text/xml'
}

def fetch_rss(source: dict, max_items: int = 10) -> list:
    """抓取单个 RSS 源"""
    try:
        resp = requests.get(source['url'], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries[:max_items]:
            pub = getattr(entry, 'published', None) or getattr(entry, 'updated', None) or ''
            try:
                pub_dt = dateparser.parse(pub).astimezone(BJT) if pub else now_bjt()
            except Exception:
                pub_dt = now_bjt()

            # 过滤最近 24 小时内的新闻
            if (now_bjt() - pub_dt).total_seconds() > 86400:
                continue

            summary = getattr(entry, 'summary', '') or ''
            # 清理 HTML 标签
            import re
            summary = re.sub(r'<[^>]+>', '', summary).strip()[:200]

            items.append({
                'id': hashlib.md5((entry.get('link','') + entry.get('title','')).encode()).hexdigest()[:8],
                'title': entry.get('title', '').strip(),
                'link': entry.get('link', '#'),
                'summary': summary,
                'source': source['label'],
                'category': source['category'],
                'pub_time': pub_dt.strftime('%Y-%m-%d %H:%M'),
                'timestamp': pub_dt.timestamp(),
            })
        log.info(f"✅ {source['name']}: {len(items)} 条")
        return items
    except Exception as e:
        log.warning(f"❌ {source['name']} 抓取失败: {e}")
        return []

def fetch_all_news() -> dict:
    """并发抓取所有新闻源"""
    result = {'cctv': [], 'tech': [], 'ai': [], 'general': []}
    
    for category, sources in NEWS_SOURCES.items():
        cat_key = 'cctv' if category == 'cctv_type' else category
        for source in sources:
            items = fetch_rss(source)
            result[cat_key].extend(items)
            time.sleep(0.5)  # 礼貌抓取

    # 按时间排序，去重
    for cat in result:
        seen = set()
        unique = []
        for item in sorted(result[cat], key=lambda x: -x['timestamp']):
            if item['id'] not in seen:
                seen.add(item['id'])
                unique.append(item)
        result[cat] = unique

    return result

def build_cctv_prompt(items: list) -> str:
    """构建新闻联播总结的提示词"""
    if not items:
        return "今日暂无抓取到官方媒体要闻。"
    
    news_text = "\n".join([
        f"【{i+1}】{item['title']}" + (f"\n   {item['summary']}" if item['summary'] else "")
        for i, item in enumerate(items[:20])
    ])
    return f"""以下是今日（{today_str()}）从新华社、人民日报等官方媒体自动抓取的要闻标题和摘要：

{news_text}

请模仿"新闻联播"的风格和内容结构，进行专业总结。输出格式严格如下（用中文）：

## 今日头条
（1-2句话概括今日最重要的政治/外交/经济大事，语气庄重）

## 要点速览
• [要点1]
• [要点2]
• [要点3]
• [要点4]
• [要点5]

## 今日点评
（1句话总结今日新闻整体基调和重要性，客观中立）

注意：仅使用提供的新闻内容，不要添加未提及的信息。"""

def summarize_with_claude(news_items: list) -> dict:
    """使用 Claude API 进行 AI 总结"""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        log.warning("未找到 ANTHROPIC_API_KEY，跳过 AI 总结")
        return {
            'headline': '暂无 AI 总结（未配置 API Key）',
            'points': ['请在 GitHub 仓库 Secrets 中配置 ANTHROPIC_API_KEY'],
            'comment': '配置方法：Settings → Secrets → New secret',
            'generated_at': now_bjt().strftime('%Y-%m-%d %H:%M'),
            'model': 'none',
            'item_count': len(news_items)
        }
    
    prompt = build_cctv_prompt(news_items)
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            system="你是一个专业的中国官方媒体新闻总结助手，擅长以新闻联播风格总结要闻，语言简洁权威，格式规范。",
            messages=[{"role": "user", "content": prompt}]
        )
        raw_text = message.content[0].text
        log.info(f"✅ Claude 总结完成，输出 {len(raw_text)} 字")
        
        # 解析结构化内容
        return parse_summary(raw_text, len(news_items))
    
    except Exception as e:
        log.error(f"Claude API 调用失败: {e}")
        return {
            'headline': f'AI 总结失败: {str(e)[:100]}',
            'points': [],
            'comment': '请检查 API Key 是否有效',
            'raw': '',
            'generated_at': now_bjt().strftime('%Y-%m-%d %H:%M'),
            'model': 'error',
            'item_count': len(news_items)
        }

def parse_summary(text: str, item_count: int) -> dict:
    """解析 Claude 输出的结构化总结"""
    import re
    
    headline = ''
    points = []
    comment = ''
    raw = text

    # 提取头条
    h_match = re.search(r'## 今日头条\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if h_match:
        headline = h_match.group(1).strip()

    # 提取要点
    p_match = re.search(r'## 要点速览\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if p_match:
        raw_points = p_match.group(1).strip()
        points = [p.lstrip('•·- ').strip() for p in raw_points.split('\n') if p.strip().startswith(('•', '·', '-', '【'))]
        if not points:
            points = [p.strip() for p in raw_points.split('\n') if p.strip()]

    # 提取点评
    c_match = re.search(r'## 今日点评\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if c_match:
        comment = c_match.group(1).strip()

    return {
        'headline': headline or text[:100],
        'points': points[:6],
        'comment': comment,
        'raw': raw,
        'generated_at': now_bjt().strftime('%Y-%m-%d %H:%M'),
        'model': 'claude-opus-4-6',
        'item_count': item_count
    }

def save_output(news: dict, summary: dict):
    """保存数据到 JSON 文件"""
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
    os.makedirs(data_dir, exist_ok=True)
    today = today_str()

    # 1. 今日完整数据
    daily_data = {
        'date': today,
        'generated_at': now_bjt().isoformat(),
        'summary': summary,
        'news': news
    }
    daily_path = os.path.join(data_dir, f'{today}.json')
    with open(daily_path, 'w', encoding='utf-8') as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)
    log.info(f"✅ 保存今日数据: {daily_path}")

    # 2. 更新 latest.json（前端默认加载）
    latest_path = os.path.join(data_dir, 'latest.json')
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)
    log.info(f"✅ 更新 latest.json")

    # 3. 更新 index.json（历史列表）
    index_path = os.path.join(data_dir, 'index.json')
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
    except Exception:
        index = {'dates': []}
    
    if today not in index['dates']:
        index['dates'].insert(0, today)
    index['dates'] = index['dates'][:90]  # 保留最近90天
    index['last_updated'] = now_bjt().isoformat()
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    log.info(f"✅ 更新 index.json，共 {len(index['dates'])} 天记录")

def main():
    log.info("=" * 50)
    log.info(f"🚀 开始执行 每日简报 自动抓取 [{today_str()}]")
    log.info("=" * 50)

    # 1. 抓取新闻
    log.info("📡 抓取各平台新闻...")
    news = fetch_all_news()
    total = sum(len(v) for v in news.values())
    log.info(f"共抓取 {total} 条新闻 | CCTV类:{len(news['cctv'])} 科技:{len(news['tech'])} AI:{len(news['ai'])} 综合:{len(news['general'])}")

    # 2. AI 总结新闻联播内容
    log.info("🤖 调用 Claude AI 进行新闻总结...")
    cctv_items = news['cctv'] + news['general'][:5]  # 官媒+综合作为总结素材
    summary = summarize_with_claude(cctv_items)

    # 3. 保存结果
    log.info("💾 保存数据...")
    save_output(news, summary)

    log.info("✅ 全部完成！")
    print(f"\n📋 今日总结预览:\n{summary.get('headline', '')}")

if __name__ == '__main__':
    main()
