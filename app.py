import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pymongo
import matplotlib.pyplot as plt
from datetime import datetime

# ———————————————————————————
# 1) Koneksi MongoDB via Streamlit Secrets
# Tambahkan di .streamlit/secrets.toml:
#
# [mongo]
# uri = "mongodb+srv://admin:admin0010@bigdata.97avssw.mongodb.net/bigdata?retryWrites=true&w=majority"
# ———————————————————————————

# Setup MongoDB dengan timeout dan pengecekan ping
try:
    mongo_uri = st.secrets["mongo"]["uri"]
    client = pymongo.MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=5000  # timeout 5 detik
    )
    client.admin.command('ping')  # ping untuk cek koneksi
    st.success("✔️ Koneksi ke MongoDB Atlas berhasil")
except Exception as e:
    # Tampilkan error lengkap untuk debug
    st.error(f"❌ Gagal koneksi ke MongoDB Atlas:\n{e}")
    st.stop()  # hentikan eksekusi aplikasi jika koneksi gagal

db = client["bigdata"]
collection = db["tarian"]

# Buat index unik pada field 'link', tangani jika gagal
try:
    idx_name = collection.create_index("link", unique=True)
    st.info(f"✔️ Index unik pada 'link' berhasil dibuat (name: {idx_name})")
except Exception as e:
    st.warning(f"⚠️ Gagal membuat index unik pada 'link':\n{e}")

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
        print(f"[Warning] Gagal ambil isi artikel dari {url}: {e}")
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
            # Skip jika sudah tersimpan
            if collection.find_one({'link': link}):
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
        st.error(f"[Error] Scraping Detik gagal: {e}")
    return articles

def save_to_mongodb(articles):
    if not articles:
        st.warning("Tidak ada artikel baru untuk disimpan.")
        return
    try:
        collection.insert_many(articles, ordered=False)
        st.success(f"{len(articles)} artikel berhasil disimpan.")
    except pymongo.errors.BulkWriteError as bwe:
        st.warning(f"Beberapa artikel mungkin sudah ada: {bwe.details}")

def visualize_tari_frequency():
    data = list(collection.find())
    if not data:
        st.warning("Tidak ada data untuk visualisasi frekuensi.")
        return
    df = pd.DataFrame(data)
    freq = {t: 0 for t in nama_tari}
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
        st.warning("Tidak ada data untuk visualisasi kategori.")
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
        st.warning("Tidak ada data untuk visualisasi tren.")
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
    # Scrape & simpan satu kali per sesi
    if "scraped_once" not in st.session_state:
        new_articles = scrape_detik()
        save_to_mongodb(new_articles)
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
