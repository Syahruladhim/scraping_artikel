import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pymongo
import matplotlib.pyplot as plt
from datetime import datetime

# Setup MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["tarian"]
collection = db["apawis"]

# (Opsional) Buat index unik pada field link agar mencegah duplikasi
collection.create_index("link", unique=True)

# Daftar nama tari
nama_tari = [
    "gambyong", "bedhaya", "serimpi", "kuda lumping", "tayub",
    "lengger", "tari topeng", "bambangan cakil", "reog", "jatilan"
]

# Fungsi mengambil isi artikel
def get_article_text(url):
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.content, 'html.parser')
        paragraphs = soup.find_all('p')
        return " ".join([p.get_text() for p in paragraphs])
    except Exception as e:
        print(f"Gagal ambil isi artikel: {e}")
        return ""

# Fungsi scraping Detik dengan pengecekan duplikasi
def scrape_detik():
    articles = []
    base_url = "https://www.detik.com/tag/tarian"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.content, 'html.parser')
        articles_container = soup.find_all('article')

        for article in articles_container:
            title_el = article.find('h2', class_='title')
            link_el = article.find('a')
            date_el = article.find('span', class_='date')
            cat_el = article.find('span', class_='category')

            if all([title_el, link_el, date_el]):
                title = title_el.text.strip()
                link  = link_el['href']

                # Cek duplikasi berdasarkan link
                if collection.find_one({'link': link}):
                    print(f"Lewati (duplikat): {link}")
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

# Simpan hasil ke MongoDB
def save_to_mongodb(articles):
    if articles:
        try:
            collection.insert_many(articles)
            st.success(f"{len(articles)} artikel berhasil disimpan.")
        except pymongo.errors.BulkWriteError:
            st.warning("Beberapa artikel mungkin sudah ada.")
    else:
        st.warning("Tidak ada artikel untuk disimpan.")

# Visualisasi 1: Frekuensi penyebutan nama tari
def visualize_tari_frequency():
    data = list(collection.find())
    if not data:
        st.warning("Tidak ada data untuk visualisasi.")
        return

    df = pd.DataFrame(data)
    freq = {tari: 0 for tari in nama_tari}

    for content in df['content']:
        if not content: continue
        lower_content = content.lower()
        for tari in nama_tari:
            freq[tari] += lower_content.count(tari)

    freq_series = pd.Series(freq).sort_values(ascending=False)
    st.subheader("Frekuensi Penyebutan Nama Tari")
    fig, ax = plt.subplots()
    freq_series.plot(kind='bar', ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Jumlah Penyebutan")
    st.pyplot(fig)

# Visualisasi 2: Jumlah artikel per kategori
def visualize_category_distribution():
    data = list(collection.find())
    if not data:
        st.warning("Tidak ada data untuk visualisasi.")
        return

    df = pd.DataFrame(data)
    category_counts = df['category'].value_counts()
    st.subheader("Distribusi Artikel per Kategori")
    fig, ax = plt.subplots()
    category_counts.plot(kind='bar', ax=ax)
    plt.xticks(rotation=45)
    plt.ylabel("Jumlah Artikel")
    st.pyplot(fig)

# Visualisasi 3: Tren scraping berdasarkan waktu
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

# Streamlit App
def main():
    st.title("Scraper & Visualisasi Tarian Jawa Tengah")

    # Scraping otomatis saat aplikasi pertama kali dibuka di sesi ini
    if "scraped_once" not in st.session_state:
        articles = scrape_detik()
        save_to_mongodb(articles)
        st.session_state.scraped_once = True

    tab1, tab2 = st.tabs(["Artikel Terbaru", "Visualisasi"])

    with tab1:
        st.subheader("Artikel Terbaru")
        recent_articles = list(collection.find().sort('scraped_at', -1).limit(10))
        for art in recent_articles:
            st.write(f"**{art['title']}**")
            st.write(f"Tanggal: {art['date']} | Kategori: {art['category']}")
            st.write(f"[Baca Selengkapnya]({art['link']})")
            st.markdown("---")

    with tab2:
        st.subheader("Daftar Nama Tari yang Dilacak dan Sumber")
        data_tari = [{"Nama Tari": tari, "Sumber": "Detik"} for tari in nama_tari]
        df_tari = pd.DataFrame(data_tari)
        st.table(df_tari)

        visualize_tari_frequency()
        visualize_category_distribution()
        visualize_scraping_trend()

if __name__ == "__main__":
    main()
