import requests
from bs4 import BeautifulSoup
import re
import time
import streamlit as st

BASE_URL = "https://www.amazon.com"
DEALS_URL = f"{BASE_URL}/gp/goldbox?ref=nav_cs_gb"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1",
}

def get_deal_links():
    r = requests.get(DEALS_URL, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.select("a.a-link-normal[href*='/dp/']"):
        href = a.get("href")
        if href and "/dp/" in href:
            full_link = BASE_URL + href.split("?")[0]
            if full_link not in links:
                links.append(full_link)
    return links

def check_coupon_and_discount(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    # 原價
    original_price = None
    orig_tag = soup.select_one(".a-price .a-offscreen")
    if orig_tag:
        try:
            original_price = float(orig_tag.text.replace("$", "").replace(",", ""))
        except:
            pass

    # deal price
    deal_price = None
    deal_tag = soup.find("span", class_="a-price-whole")
    if deal_tag:
        try:
            deal_price = float(deal_tag.text.replace(",", ""))
        except:
            pass

    # coupon
    coupon_value = 0
    coupon_tag = soup.find(text=re.compile(r"coupon", re.I))
    if coupon_tag:
        match = re.search(r"\$([\d\.]+)", coupon_tag)
        if match:
            coupon_value = float(match.group(1))
        elif "%" in coupon_tag.lower():
            match = re.search(r"(\d+)%", coupon_tag)
            if match and deal_price:
                coupon_value = deal_price * (float(match.group(1))/100)

    if original_price and deal_price:
        final_price = deal_price - coupon_value
        discount_rate = 1 - (final_price / original_price)
        if coupon_value > 0 and discount_rate > 0.05:
            return {
                "url": url,
                "original": original_price,
                "deal_price": deal_price,
                "coupon_value": coupon_value,
                "final_price": final_price,
                "discount_rate": round(discount_rate*100, 1)
            }
    # 除錯輸出
    print("DEBUG:", url, original_price, deal_price, coupon_value)
    return None

st.title("💥 Amazon 閃電特賣 + coupon 疊加檢測器")
max_items = st.slider("檢查商品數量", 5, 100, 10)
if st.button("開始搜尋"):
    st.write("⏳ 正在搜尋，請稍等...")
    links = get_deal_links()
    st.write(f"✅ 找到 {len(links)} 個閃電特賣商品連結")
    st.write("前 5 個商品連結：")
    for l in links[:5]:
        st.write(l)
    results = []
    for link in links[:max_items]:
        try:
            deal = check_coupon_and_discount(link)
            if deal:
                results.append(deal)
        except:
            pass
        time.sleep(1)
    if results:
        st.success(f"找到 {len(results)} 個疑似折上折好康！")
        for r in results:
            st.markdown(f"[{r['discount_rate']}% OFF | ${r['final_price']}]({r['url']})  原價 ${r['original']} → 特價 ${r['deal_price']} 再減 ${r['coupon_value']}")
    else:
        st.warning("沒有找到符合條件的商品。")
