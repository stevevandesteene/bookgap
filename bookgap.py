import streamlit as st
import pandas as pd
import requests
from rapidfuzz import process
import io

# --- Cache OpenLibrary requests so we don’t hammer the API ---
@st.cache_data
def get_author_works(author_name):
    url = f"https://openlibrary.org/search.json?author={author_name}&limit=100"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    data = resp.json()
    works = [doc["title"] for doc in data.get("docs", []) if "title" in doc]
    return list(set(works))  # dedupe


# --- Core Logic: find missing works by an author ---
def find_missing_books(user_books, author_name, newest_only=False):
    all_works = get_author_works(author_name)
    owned = []
    missing = []

    # Fuzzy match owned titles against OpenLibrary titles
    for book in user_books:
        match, score, _ = process.extractOne(book, all_works)
        if score > 80:
            owned.append(match)

    missing = [book for book in all_works if book not in owned]

    if newest_only and missing:
        return owned, [missing[-1]]  # last one as "latest release"
    return owned, missing


# --- Streamlit UI ---
st.title("📚 Book Collection Gap Finder (Powered by OpenLibrary)")
st.write("Upload your book collection (CSV/Excel) with at least `Title` and `Author` columns. "
         "The app will find missing books by each author in your collection and highlight gaps in series.")

uploaded_file = st.file_uploader("Upload your file", type=["csv", "xlsx"])

# Toggle newest-only mode
newest_only = st.checkbox("Show only newest missing release per author", value=False)

if uploaded_file:
    # Load file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.write("### Preview of your collection:")
    st.dataframe(df.head())

    if "Title" not in df.columns or "Author" not in df.columns:
        st.error("Your file needs 'Title' and 'Author' columns.")
    else:
        user_books = df["Title"].dropna().tolist()
        authors = df["Author"].dropna().unique().tolist()

        st.write(f"🔎 Found {len(authors)} unique authors in your collection.")
        st.write("Checking OpenLibrary for missing works...")

        results = {}
        export_rows = []

        for author in authors:
            owned, missing = find_missing_books(user_books, author, newest_only=newest_only)
            if missing:
                results[author] = {"owned": owned, "missing": missing}
                for m in missing:
                    export_rows.append({"Author": author, "Missing Title": m})

        if results:
            st.write("### 📖 Missing Books by Author")
            for author, data in results.items():
                st.subheader(author)
                st.success(f"✅ Owned: {len(data['owned'])}")
                st.write(", ".join(data["owned"][:10]))  # preview first 10

                st.warning(f"📖 Missing: {len(data['missing'])}")
                with st.expander("See missing titles"):
                    st.write(", ".join(data["missing"]))

            # --- Export missing list ---
            if export_rows:
                export_df = pd.DataFrame(export_rows)
                csv_buffer = io.StringIO()
                export_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="⬇️ Download Missing Books as CSV",
                    data=csv_buffer.getvalue(),
                    file_name="missing_books.csv",
                    mime="text/csv",
                )
        else:
            st.balloons()
            st.success("🎉 You’re up to date on all detected authors!")
