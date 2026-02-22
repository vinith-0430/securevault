import streamlit as st
import sqlite3
import json
import hashlib
import os
import pandas as pd
import random
from cryptography.fernet import Fernet
from datetime import datetime

# =========================
# CONFIG & STYLING
# =========================
st.set_page_config(page_title="Enterprise Secure Vault", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{
    background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
    color:white;
}
.stButton>button{
    background:linear-gradient(90deg,#2563eb,#06b6d4);
    color:white;
    border-radius:8px;
    height:42px;
}
.sidebar .sidebar-content { background:#111827; }
</style>
""", unsafe_allow_html=True)

# =========================
# KEY + SALT (Backend Logic)
# =========================
KEY_FILE = "secret.key"
SALT_FILE = "salt.key"

if not os.path.exists(KEY_FILE):
    key = Fernet.generate_key()
    open(KEY_FILE, "wb").write(key)
else:
    key = open(KEY_FILE, "rb").read()

cipher = Fernet(key)

if not os.path.exists(SALT_FILE):
    salt = os.urandom(16)
    open(SALT_FILE, "wb").write(salt)
else:
    salt = open(SALT_FILE, "rb").read()

def get_trapdoor(word, secret_key, salt):
    normalized = word.lower().strip().encode()
    data = secret_key + salt + normalized
    return hashlib.sha256(data).hexdigest()

# =========================
# DATABASE INITIALIZATION
# =========================
def init_db():
    conn = sqlite3.connect("vault.db", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS data_store(id INTEGER PRIMARY KEY, payload BLOB)") 
    cur.execute("CREATE TABLE IF NOT EXISTS search_index(trapdoor TEXT, data_id INTEGER)") 
    cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, phone TEXT)") 
    cur.execute("CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY, username TEXT, action TEXT, time TEXT)") 
    
    # Create default admin
    if not cur.execute("SELECT * FROM users WHERE username='admin'").fetchone():
        cur.execute("INSERT INTO users VALUES(NULL,?,?,?,?)",
                    ("admin", hashlib.sha256("admin123".encode()).hexdigest(), "admin", "+1-555-0199")) 
    
    # Insert dummy data only if the store is empty
    if cur.execute("SELECT COUNT(*) FROM data_store").fetchone()[0] == 0:
        customers = [
            {"id": 1, "name": "Alice ", "acc_no": "10001", "balance": "5000"},
            {"id": 2, "name": "Bob Jones", "acc_no": "10002", "balance": "1200"},
            {"id": 3, "name": "Charlie Brown", "acc_no": "10003", "balance": "4500"},
            {"id": 4, "name": "Diana Prince", "acc_no": "10004", "balance": "9000"}
        ]
        print("[*] Encrypting and storing records securely...")
        for person in customers:
            encrypted_blob = cipher.encrypt(json.dumps(person).encode())
            cur.execute("INSERT INTO data_store (payload) VALUES (?)", (encrypted_blob,))
            row_id = cur.lastrowid
            terms = person['name'].split() + [person['acc_no']] + [str(person['balance'])]
            
            for term in set(terms):
                td = get_trapdoor(term, key, salt)
                cur.execute("INSERT INTO search_index (trapdoor, data_id) VALUES (?, ?)", (td, row_id))
    
    conn.commit()
    return conn

conn = init_db()
cur = conn.cursor()

def log_action(user, action):
    cur.execute("INSERT INTO logs VALUES(NULL,?,?,?)",
                (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# =========================
# SESSION MANAGEMENT
# =========================
if "logged" not in st.session_state:
    st.session_state.logged = False
    st.session_state.user = None
    st.session_state.role = None
    st.session_state.otp_step = False
    st.session_state.gen_otp = None
    st.session_state.temp_user = None
    st.session_state.temp_role = None

# =========================
# LOGIN / SIGN UP
# =========================
if not st.session_state.logged:
    st.title("Secure Vault")

    if st.session_state.otp_step:
        st.subheader("Mobile Verification")
        st.info(f"Enter the code for **{st.session_state.temp_user}**.")
        
        with st.expander("DEV ONLY: Mobile SMS Received"):
            st.success(f"SMS Message: Your Vault Login Code is {st.session_state.gen_otp}")

        otp_in = st.text_input("Enter OTP Code", max_chars=6)
        
        c1, c2 = st.columns(2)
        if c1.button("Verify OTP"):
            if otp_in == st.session_state.gen_otp:
                st.session_state.logged = True
                st.session_state.user = st.session_state.temp_user
                st.session_state.role = st.session_state.temp_role
                log_action(st.session_state.user, "Successful 2FA Login")
                st.rerun()
            else:
                st.error("Invalid OTP.")
        
        if c2.button("Cancel"):
            st.session_state.otp_step = False
            st.rerun()

    else:
        t1, t2, t3 = st.tabs(["Admin Login", "Customer Login", "Sign Up"])
        
        # --- ADMIN LOGIN ---
        with t1:
            u = st.text_input("Admin Username")
            p = st.text_input("Admin Password", type="password")
            if st.button("Send OTP (Admin)"):
                hp = hashlib.sha256(p.encode()).hexdigest()
                res = cur.execute("SELECT role FROM users WHERE username=? AND password=?", (u, hp)).fetchone()
                if res and res[0] == "admin":
                    st.session_state.otp_step = True
                    st.session_state.gen_otp = str(random.randint(100000, 999999))
                    st.session_state.temp_user, st.session_state.temp_role = u, "admin"
                    st.rerun()
                else: st.error("Invalid Credentials")
                
        # --- CUSTOMER LOGIN ---
        with t2:
            u = st.text_input("Customer Username")
            p = st.text_input("Customer Password", type="password")
            if st.button("Send OTP (Customer)"):
                hp = hashlib.sha256(p.encode()).hexdigest()
                res = cur.execute("SELECT role FROM users WHERE username=? AND password=?", (u, hp)).fetchone()
                if res:
                    st.session_state.otp_step = True
                    st.session_state.gen_otp = str(random.randint(100000, 999999))
                    st.session_state.temp_user, st.session_state.temp_role = u, res[0]
                    st.rerun()
                else: st.error("Invalid Credentials")
                
        # --- SIGN UP ---
        with t3:
            st.subheader("Create a New Account")
            new_name = st.text_input("Full Name (This will be your Username)")
            new_acc = st.text_input("Account Number (Choose a unique ID)")
            new_phone = st.text_input("Phone Number")
            new_pass = st.text_input("Password", type="password")
            
            if st.button("Sign Up"):
                if new_name and new_acc and new_pass:
                    try:
                        # Create User in database
                        hp = hashlib.sha256(new_pass.encode()).hexdigest()
                        cur.execute("INSERT INTO users VALUES(NULL,?,?,?,?)", (new_name, hp, "customer", new_phone))
                        
                        # Create Record with 0 Balance in encrypted data_store
                        payload = cipher.encrypt(json.dumps({"name":new_name, "acc_no":new_acc, "balance":0}).encode())
                        cur.execute("INSERT INTO data_store(payload) VALUES(?)", (payload,))
                        row_id = cur.lastrowid
                        
                        # Update Search Index
                        for term in set(new_name.split() + [new_acc]):
                            cur.execute("INSERT INTO search_index VALUES(?,?)", (get_trapdoor(term, key, salt), row_id))
                        
                        conn.commit()
                        st.success("Account created successfully! You can now log in using the 'Customer Login' tab.")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists. Please choose another name.")
                else:
                    st.error("Please fill in your Name, Account Number, and Password.")
    st.stop()

# =========================
# MAIN DASHBOARD NAVIGATION
# =========================
st.sidebar.title("Secure Vault")

# Dynamic Menu based on role
if st.session_state.role == "admin":
    menu_options = ["Dashboard","Search","User Management","Delete Record","Logs","My Activity"]
else:
    menu_options = ["User Management", "My Activity"]

menu = st.sidebar.radio("Navigation", menu_options)

if st.sidebar.button("Logout"):
    log_action(st.session_state.user, "Logout")
    st.session_state.logged = False
    st.rerun()

# --- Dashboard View ---
if menu == "Dashboard":
    total_records = cur.execute("SELECT COUNT(*) FROM data_store").fetchone()[0]
    total_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_logs = cur.execute("SELECT COUNT(*) FROM logs").fetchone()[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Encrypted Records", total_records)
    col2.metric("Total Users", total_users)
    col3.metric("System Activities", total_logs)
    st.divider()

    if st.session_state.role == "admin":
        st.subheader("System Analytics")
        df_logs = pd.read_sql_query("SELECT * FROM logs", conn)
        if not df_logs.empty:
            df_logs["date"] = pd.to_datetime(df_logs["time"], errors='coerce').dt.date
            st.line_chart(df_logs.groupby("date").size())
    else:
        st.info("Secure searchable encryption is active.")

# --- Search View (Admin Only) ---
if menu == "Search":
    if st.session_state.role != "admin": 
        st.error("Admin access required. Customers are not permitted to search the vault.")
    else:
        st.subheader("Secure Search")
        query = st.text_input("Enter name or account number")
        if query:
            td = get_trapdoor(query, key, salt)
            results = cur.execute("""
                SELECT ds.payload FROM data_store ds
                JOIN search_index si ON ds.id=si.data_id
                WHERE si.trapdoor=?""", (td,)).fetchall()
            
            log_action(st.session_state.user, f"Searched: {query}")
            if results:
                for r in results:
                    data = json.loads(cipher.decrypt(r[0]).decode())
                    st.success("Record Found")
                    st.json(data)
            else: st.error("No results found")

# --- Delete Record (Admin Only) ---
if menu == "Delete Record":
    if st.session_state.role != "admin": st.error("Admin access required")
    else:
        records = cur.execute("SELECT id, payload FROM data_store").fetchall()
        table_data = []
        for r in records:
            data = json.loads(cipher.decrypt(r[1]).decode())
            table_data.append({"ID": r[0], "Name": data["name"], "Account": data["acc_no"]})
        st.table(table_data)
        rid = st.number_input("Enter Record ID to Delete", min_value=1)
        if st.button("Delete Permanent"):
            cur.execute("DELETE FROM data_store WHERE id=?", (rid,))
            cur.execute("DELETE FROM search_index WHERE data_id=?", (rid,))
            conn.commit()
            log_action(st.session_state.user, f"Deleted Record {rid}")
            st.rerun()

# --- User Management (Combined Add Record + Add User) ---
if menu == "User Management":
    if st.session_state.role == "admin":
        # ADMIN VIEW: Create Customer Profile and Encrypted Record simultaneously
        st.subheader("Add New Customer Record & User Account")
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Customer Name (Username)")
            new_acc = st.text_input("Account Number")
            new_bal = st.number_input("Starting Balance", value=0)
        with c2:
            new_phone = st.text_input("Phone Number")
            new_pass = st.text_input("Password (Leave blank for 'user123')", type="password")
            
        if st.button("Create Customer & Record"):
            if new_name and new_acc:
                try:
                    # Logic: If password is empty, use 'user123'
                    final_pass = new_pass if new_pass else "user123"
                    hp = hashlib.sha256(final_pass.encode()).hexdigest()
                    
                    # 1. Insert into plaintext Users table
                    cur.execute("INSERT INTO users VALUES(NULL,?,?,?,?)", (new_name, hp, "customer", new_phone))
                    
                    # 2. Insert into Encrypted data_store
                    payload = cipher.encrypt(json.dumps({"name":new_name,"acc_no":new_acc,"balance":new_bal}).encode())
                    cur.execute("INSERT INTO data_store(payload) VALUES(?)", (payload,))
                    row_id = cur.lastrowid
                    
                    # 3. Insert secure trapdoors into search_index
                    for term in set(new_name.split() + [new_acc]):
                        cur.execute("INSERT INTO search_index VALUES(?,?)", (get_trapdoor(term, key, salt), row_id))
                        
                    conn.commit()
                    log_action(st.session_state.user, f"Added User & Record: {new_name}")
                    st.success(f"User '{new_name}' and secure record created! (Default Password: {final_pass})")
                except sqlite3.IntegrityError:
                    st.error("Username/Customer Name already exists in the system!")
            else:
                st.error("Customer Name and Account Number are required.")
        
        st.divider()
        st.subheader("All System Users")
        users = pd.read_sql_query("SELECT id, username, role, phone FROM users", conn)
        st.table(users)
        
    else:
        # CUSTOMER VIEW: Account Details + Encrypted Balance
        st.subheader("My Account Details")
        user_info = cur.execute("SELECT id, username, role, phone FROM users WHERE username=?", (st.session_state.user,)).fetchone()
        
        # --- Fetch Encrypted Balance securely ---
        # Search index uses split parts of the name. We'll search by the first part of the user's name.
        first_name = st.session_state.user.split()[0]
        td = get_trapdoor(first_name, key, salt)
        results = cur.execute("""
            SELECT ds.payload FROM data_store ds
            JOIN search_index si ON ds.id=si.data_id
            WHERE si.trapdoor=?""", (td,)).fetchall()
        
        balance = "0"
        if results:
            for r in results:
                # Decrypt the payload
                data = json.loads(cipher.decrypt(r[0]).decode())
                # Ensure we matched the exact user to prevent false positives from similar first names
                if data.get("name") == st.session_state.user:
                    balance = data.get("balance", 0)
                    break
        # ----------------------------------------

        if user_info:
            col1, col2, col3 = st.columns(3)
            col1.write(f"**User ID:** {user_info[0]}")
            col1.write(f"**Username:** {user_info[1]}")
            col2.write(f"**Role:** {user_info[2].capitalize()}")
            col2.write(f"**Phone Number:** {user_info[3]}")
            
            # Display decrypted balance
            col3.metric("Account Balance", f"${balance}")
            
            st.divider()
            st.subheader("Update Information")
            update_phone = st.text_input("Update Phone Number", value=user_info[3])
            update_pass = st.text_input("Update Password (leave blank to keep current)", type="password")
            
            if st.button("Save Changes"):
                if update_pass:
                    hp = hashlib.sha256(update_pass.encode()).hexdigest()
                    cur.execute("UPDATE users SET phone=?, password=? WHERE username=?", (update_phone, hp, st.session_state.user))
                else:
                    cur.execute("UPDATE users SET phone=? WHERE username=?", (update_phone, st.session_state.user))
                
                conn.commit()
                log_action(st.session_state.user, "Updated account details")
                st.success("Account successfully updated!")
                st.rerun()

# --- Logs (Admin Only) ---
if menu == "Logs":
    if st.session_state.role == "admin":
        df = pd.read_sql_query("SELECT * FROM logs ORDER BY id DESC", conn)
        st.dataframe(df)

# --- My Activity (All Users) ---
if menu == "My Activity":
    df = pd.read_sql_query("SELECT action, time FROM logs WHERE username=? ORDER BY id DESC", 
                           conn, params=(st.session_state.user,))
    st.table(df)