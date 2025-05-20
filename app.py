import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pymongo
import matplotlib.pyplot as plt
from datetime import datetime

# Setup MongoDB dengan timeout
try:
    client = pymongo.MongoClient(
        "mongodb+srv://admin:admin0010@bigdata.97avssw.mongodb.net/"
        "?retryWrites=true&w=majority&appName=bigdata",
        serverSelectionTimeoutMS=5000  # 5 detik timeout
    )
    # Cek koneksi singkat
    client.admin.command('ping')
except Exception as e:
    st.error(f"Gagal koneksi ke MongoDB: {e}")
    st.stop()  # hentikan eksekusi jika tidak bisa connect

db = client["bigdata"]
collection = db["tarian"]

# (Opsional) Buat index unik pada field link agar mencegah duplikasi
try:
    collection.create_index("link", unique=True)
except Exception as e:
    st.warning(f"Tidak dapat membuat index unik pada 'link': {e}")

# Daftar nama tari
nama_tari = [
    "gambyong", "bedhaya", "serimpi", "kuda lumping", "tayub",
    "lengger", "tari topeng", "bambangan cakil", "reog", "jatilan"
]

def get_article_text(url):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')
        paragraphs = soup.find_all('p')
        return " ".join(p.get_text() for p in paragraphs)
    except Exception as e:
        st.warning(f"Gagal ambil isi artikel dari {url}: {e}")
        return ""

def scrape_detik():
    articles = []
    base_url = "https://www.detik.com/tag/tarian"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(base_url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')
        articles_container = soup.find_all('article')
        for article in articles_container:
            title_el = article.find('h2', class_='title')
            link_el  = article.find('a')
            date_el  = article.find('span', class_='date')
            cat_el   = article.find('span', class_='category')
            if not (title_el and link_el and date_el):
                continue
            title = title_el.text.strip()
            link  = link_el['href']
            if collection.find_one({'link': link}):
                # sudah ada, skip
                continue
            date     = date_el.text.strip()
            category = cat_el.text.strip() if cat_el else "Unknown"
            content  = get_article_text(link)
            articles.append({
                'source':     'Detik',
                'title':      title,
                'date':       date,
                'link':       link,
                'category':   category,
                'content':    content,
                'scraped_at': datetime.now()
            })
    except Exception as e:
        st.error(f"Scraping error: {e}")
    return articles

def save_to_mongodb(articles):
    if not articles:
        st.warning("Tidak ada artikel untuk disimpan.")
        return
    try:
        collection.insert_many(articles, ordered=False)
        st.success(f"{len(articles)} artikel berhasil disimpan.")
    except pymongo.errors.BulkWriteError as bwe:
        st.warning("Beberapa artikel mungkin sudah ada: " + str(bwe.details))

def visualize_tari_frequency():
    data = list(collection.find())
    if not data:
        st.warning("Tidak ada data untuk visualisasi.")
        return
    df = pd.DataFrame(data)
    freq = {t:0 for t in nama_tari}
    for content in df['content'].fillna(""):
        lower = content.lower()
        for t in nama_tari:
            freq[t] += lower.count(t)
    freq_series = pd.Series(freq).sort_values(ascending=False)
    st.subheader("Frekuensi Penyebutan Nama Tari")
    fig, ax = plt.subplots()
    freq_series.plot(kind='bar', ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Jumlah Penyebutan")
    st.pyplot(fig)

def visualize_category_distribution():
    data = list(collection.find())
    if not data:
        st.warning("Tidak ada data untuk visualisasi.")
        return
    df = pd.DataFrame(data)
    counts = df['category'].value_counts()
    st.subheader("Distribusi Artikel per Kategori")
    fig, ax = plt.subplots()
    counts.plot(kind='bar', ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Jumlah Artikel")
    st.pyplot(fig)

def visualize_scraping_trend():
    data = list(collection.find())
    if not data:
        st.warning("Tidak ada data untuk visualisasi.")
        return
    df = pd.DataFrame(data)
    df['scraped_at'] = pd.to_datetime(df['scraped_at'])
    trend = df.groupby(df['scraped_at'].dt.date).size()
    st.subheader("Tren Jumlah Artikel dari Waktu ke Waktu")
    fig, ax = plt.subplots()
    trend.plot(ax=ax, marker='o', linestyle='-')
    plt.xticks(rotation=45)
    plt.ylabel("Jumlah Artikel")
    st.pyplot(fig)

def main():
    st.title("Scraper & Visualisasi Tarian Jawa Tengah")
    if "scraped_once" not in st.session_state:
        articles = scrape_detik()
        save_to_mongodb(articles)
        st.session_state.scraped_once = True

    tab1, tab2 = st.tabs(["Artikel Terbaru", "Visualisasi"])
    with tab1:
        st.subheader("Artikel Terbaru")
        recent = list(collection.find().sort('scraped_at', -1).limit(10))
        for art in recent:
            st.markdown(f"**{art['title']}**")
            st.markdown(f"_{art['date']} | {art['category']}_")
            st.markdown(f"[Baca Selengkapnya]({art['link']})")
            st.markdown("---")

    with tab2:
        st.subheader("Daftar Nama Tari yang Dilacak")
        df_tari = pd.DataFrame([{"Nama Tari": t, "Sumber": "Detik"} for t in nama_tari])
        st.table(df_tari)
        visualize_tari_frequency()
        visualize_category_distribution()
        visualize_scraping_trend()

if __name__ == "__main__":
    main()
