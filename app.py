import streamlit as st
import sqlite3
import json
import hashlib
import os
from cryptography.fernet import Fernet

# ==============================
#  1. KEY + SALT MANAGEMENT
# ==============================

KEY_FILE = "secret.key"
SALT_FILE = "salt.key"

# --- Load/Create Encryption Key ---
if not os.path.exists(KEY_FILE):
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
else:
    with open(KEY_FILE, "rb") as f:
        key = f.read()

cipher = Fernet(key)

# --- Load/Create Salt ---
if not os.path.exists(SALT_FILE):
    salt = os.urandom(16)
    with open(SALT_FILE, "wb") as f:
        f.write(salt)
else:
    with open(SALT_FILE, "rb") as f:
        salt = f.read()

# ==============================
#  2. TRAPDOOR FUNCTION (SALTED)
# ==============================

def get_trapdoor(word):
    normalized = word.lower().strip().encode()
    data = key + salt + normalized
    return hashlib.sha256(data).hexdigest()

# ==============================
#  3. DATABASE INIT
# ==============================

def init_db():
    conn = sqlite3.connect('encrypted_vault.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_store (
            id INTEGER PRIMARY KEY,
            payload BLOB
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_index (
            trapdoor TEXT,
            data_id INTEGER
        )
    ''')

    conn.commit()
    return conn

conn = init_db()

# ==============================
#  4. ADD CUSTOMER (ENCRYPT + INDEX)
# ==============================

def add_customer(name, acc_no, balance):
    cursor = conn.cursor()

    person = {
        "name": name,
        "acc_no": acc_no,
        "balance": balance
    }

    encrypted_blob = cipher.encrypt(json.dumps(person).encode())

    cursor.execute("INSERT INTO data_store (payload) VALUES (?)", (encrypted_blob,))
    row_id = cursor.lastrowid

    # searchable terms
    terms = name.split() + [acc_no]

    for term in set(terms):
        td = get_trapdoor(term)
        cursor.execute(
            "INSERT INTO search_index (trapdoor, data_id) VALUES (?, ?)",
            (td, row_id)
        )

    conn.commit()

# ==============================
#  5. STREAMLIT UI
# ==============================

st.set_page_config(page_title="Secure Encrypted Vault", layout="wide")

st.title(" Military-Grade Secure Searchable Vault")
st.markdown("""
This vault uses **Searchable Encryption + Salting**.  
Even if database is stolen, data cannot be read or searched without secret key & salt.
""")

# ==============================
#  SIDEBAR: ADD RECORD
# ==============================

with st.sidebar:
    st.header("➕ Add Secure Record")

    new_name = st.text_input("Full Name")
    new_acc = st.text_input("Account Number")
    new_bal = st.number_input("Balance", min_value=0)

    if st.button(" Encrypt & Store"):
        if new_name and new_acc:
            add_customer(new_name, new_acc, str(new_bal))
            st.success("Record encrypted & stored securely!")
        else:
            st.error("Enter all fields")

# ==============================
# 🔍 SEARCH SECTION
# ==============================

st.subheader("🔍 Secure Search")
query = st.text_input("Search by Name or Account Number")

if query:
    search_td = get_trapdoor(query)

    cursor = conn.cursor()
    cursor.execute('''
        SELECT ds.payload FROM data_store ds
        JOIN search_index si ON ds.id = si.data_id
        WHERE si.trapdoor = ?
    ''', (search_td,))

    results = cursor.fetchall()

    if results:
        st.success(f" {len(results)} Match Found")

        for row in results:
            decrypted_data = json.loads(cipher.decrypt(row[0]).decode())

            with st.expander(f"👤 {decrypted_data['name']}"):
                st.json(decrypted_data)

    else:
        st.error("❌ No match found (Encrypted search failed)")

# ==============================
# 📈 DATABASE STATS
# ==============================

st.divider()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM data_store")
total_records = cursor.fetchone()[0]

st.info(f" Vault currently protecting **{total_records} encrypted records**")