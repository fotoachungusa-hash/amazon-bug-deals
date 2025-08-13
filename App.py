# app.py
# 💥 Amazon Bug Deals 雷達（加強版，指定分類 + 最低折扣率）
import re, time, random, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import streamlit as st
import pandas as pd

BASE_URL = "https://www.amazon.com"
CATEGORY_PATHS = {
    "全部": "/gp/goldbox?ref=nav_cs_gb",
    "3C": "/b?node=172282&ref_=nav_cs_3c",
    "家電": "/b?node=667846011&ref_=nav_cs_appliances",
    "美妝": "/b?node=11060451&ref_=nav_cs_beauty"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)

def fetch(url, retry=3):
    for i in range(retry):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200 and "captcha" not in r.text.lower():
                return r.text
        except:
            pass
        time.sleep(0.5 + i*0.8 + random.random()*0.4)
    return None

def get_links(category_url):
    html = fetch(category_url)
    if not html: return []
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.select("a.a-link-normal[href*='/dp/']"):
        href = a.get("href")
        if href and "/dp/" in href:
            links.add(urljoin(BASE_URL, href.split("?")[0]))
    return list(links)

def safe_money(text):
    try:
        return float(text.replace("$","").replace(",","").strip())
    except:
        return None

def parse_prices(soup):
    original, deal = None, None
    strike = soup.select_one(".a-text-price .a-offscreen")
    if strike: original = safe_money(strike.get_text())
    now = soup.select_one("#corePriceDisplay_desktop_feature_div .a-offscreen") or soup.select_one(".a-price .a-offscreen")
    if now: deal = safe_money(now.get_text())
    if original is None and deal is not None:
        prices = [safe_money(x.get_text()) for x in soup.select(".a-offscreen") if safe_money(x.get_text())]
        if prices: original = max(prices)
    return original, deal

def parse_coupon(soup, deal_price):
    texts = []
    for sel in ["#couponBadge_feature_div","#couponText_feature_div",".a-color-success",".a-row"]:
        for node in soup.select(sel):
            t = node.get_text(" ", strip=True)
            if t and "coupon" in t.lower(): texts.append(t)
    coupon_text = " | ".join(texts[:5])
    coupon_value = 0.0
    m = re.search(r'\$([0-9]+(?:\.[0-9]{2})?)', coupon_text)
    if m: coupon_value = float(m.group(1))
    else:
        m = re.search(r'(\d{1,2})\s*%', coupon_text)
        if m and deal_price: coupon_value = round(deal_price*(float(m.group(1))/100),2)
    return coupon_value, coupon_text

def check_item(url, loose=False):
    html = fetch(url)
    if not html: return None
    soup = BeautifulSoup(html,"html.parser")
    title = soup.select_one("#productTitle")
    title = title.get_text(strip=True) if title else ""
    original, deal = parse_prices(soup)
    coupon_value, coupon_text = parse_coupon(soup, deal)
    final_price = deal - coupon_value if deal and coupon_value>0 else deal
    discount_rate = round((1-(final_price/original))*100,1) if final_price and original else None
    if loose and "coupon" in coupon_text.lower(): return {"title":title,"url":url,"original":original,"deal":deal,"coupon_value":coupon_value,"coupon_text":coupon_text,"final":final_price,"discount_rate":discount_rate}
    if coupon_value>0: return {"title":title,"url":url,"original":original,"deal":deal,"coupon_value":coupon_value,"coupon_text":coupon_text,"final":final_price,"discount_rate":discount_rate}
    return None

# ---------------- UI ----------------
st.set_page_config(page_title="Amazon Bug Deals Radar 加強版", layout="wide")
st.title("💥 Amazon Bug Deals Radar 加強版（免 Telegram）")
st.caption("指定分類 + 最低折扣率 + CSV 下載")

col1,col2,col3,col4 = st.columns([1,1,1,1])
with col1: category = st.selectbox("選擇分類", list(CATEGORY_PATHS.keys()))
with col2: max_items = st.slider("檢查商品數量",5,80,30,5)
with col3: loose_mode = st.toggle("寬鬆模式", value=True)
with col4: min_discount = st.slider("最低折扣率 (%)",0,100,30,5)
show_debug = st.toggle("顯示除錯資訊", True)

if st.button("開始搜尋 🚀"):
    cat_url = BASE_URL+CATEGORY_PATHS[category]
    st.info("抓取分類商品連結…")
    links = get_links(cat_url)
    st.write(f"抓到 {len(links)} 個商品")
    if not links: st.warning("沒有抓到任何商品連結"); st.stop()
    rows = []
    for i, link in enumerate(links[:max_items],1):
        item = check_item(link, loose_mode)
        if item and (item.get("discount_rate") or 0) >= min_discount:
            rows.append(item)
            if show_debug: st.write(f"✅ {item['title'][:60]} ({item.get('discount_rate')}% OFF)")
        elif show_debug: st.write(f"— 跳過：{link}")
        time.sleep(random.uniform(0.8,1.5))
    if not rows: st.warning("沒有符合條件的商品")
    else:
        for r in rows:
            r["原價"] = f"${r.pop('original',0):,.2f}" if r.get("original") else ""
            r["特價"] = f"${r.pop('deal',0):,.2f}" if r.get("deal") else ""
            r["Coupon金額"] = f"${r.get('coupon_value',0):,.2f}" if r.get("coupon_value") else ""
            r["最終價(估)"] = f"${r.pop('final',0):,.2f}" if r.get("final") else ""
            r["折扣率(估)"] = f"{r.pop('discount_rate','')}%" if r.get("discount_rate") else ""
            r["標題"] = r.pop("title","")
            r["商品連結"] = r.pop("url","")
            r["Coupon文字"] = r.pop("coupon_text","")
        df = pd.DataFrame(rows, columns=["標題","原價","特價","Coupon金額","最終價(估)","折扣率(估)","Coupon文字","商品連結"])
        st.success(f"🎉 找到 {len(df)} 筆符合條件的商品")
        st.dataframe(df,use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下載結果（CSV）",data=csv,file_name="amazon_coupon_results.csv",mime="text/csv")
