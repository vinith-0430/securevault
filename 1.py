import sqlite3
import json
import hashlib
import os
from cryptography.fernet import Fernet
# 1. KEY + SALT MANAGEMENT
KEY_FILE = "secret.key"
SALT_FILE = "salt.key"
# --- Encryption Key ---
if not os.path.exists(KEY_FILE):
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
else:
    with open(KEY_FILE, "rb") as f:
        key = f.read()
cipher = Fernet(key)
# --- Salt ---
if not os.path.exists(SALT_FILE):
    salt = os.urandom(16)
    with open(SALT_FILE, "wb") as f:
        f.write(salt)
else:
    with open(SALT_FILE, "rb") as f:
        salt = f.read()
# 2. TRAPDOOR FUNCTION (Salted)
def get_trapdoor(word, secret_key, salt):
    normalized = word.lower().strip().encode()
    data = secret_key + salt + normalized
    return hashlib.sha256(data).hexdigest()
# 3. DATABASE + ENCRYPTION
def initialize_and_store():
    conn = sqlite3.connect('encrypted_vault.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS data_store')
    cursor.execute('DROP TABLE IF EXISTS search_index')
    cursor.execute('CREATE TABLE data_store (id INTEGER PRIMARY KEY, payload BLOB)')
    cursor.execute('CREATE TABLE search_index (trapdoor TEXT, data_id INTEGER)')
    customers = [
        {"id": 1, "name": "Alice ", "acc_no": "10001", "balance": "5000"},
        {"id": 2, "name": "Bob Jones", "acc_no": "10002", "balance": "1200"},
        {"id": 3, "name": "Charlie Brown", "acc_no": "10003", "balance": "4500"},
        {"id": 4, "name": "Diana Prince", "acc_no": "10004", "balance": "9000"},
        {"id": 5, "name": "Edward Norton", "acc_no": "10005", "balance": "3200"},
        {"id": 6, "name": "Fiona Gallagher", "acc_no": "10006", "balance": "2100"},
        {"id": 7, "name": "George Miller", "acc_no": "10007", "balance": "7800"},
        {"id": 8, "name": "Hannah Abbott", "acc_no": "10008", "balance": "1500"},
        {"id": 9, "name": "Ian Wright", "acc_no": "10009", "balance": "6600"},
        {"id": 10, "name": "Jack Sparrow", "acc_no": "10010", "balance": "0"},
        {"id": 11, "name": "Kevin Hart", "acc_no": "10011", "balance": "8900"},
        {"id": 12, "name": "Laura Croft", "acc_no": "10012", "balance": "5400"},
        {"id": 13, "name": "Mike Tyson", "acc_no": "10013", "balance": "2300"},
        {"id": 14, "name": "Nancy Drew", "acc_no": "10014", "balance": "4100"},
        {"id": 15, "name": "Oscar Wilde", "acc_no": "10015", "balance": "1100"},
        {"id": 16, "name": "Peter Parker", "acc_no": "10016", "balance": "300"},
        {"id": 17, "name": "Quinn Fabray", "acc_no": "10017", "balance": "9200"},
        {"id": 18, "name": "Riley Reid", "acc_no": "10018", "balance": "5500"},
        {"id": 19, "name": "Steven Strange", "acc_no": "10019", "balance": "7700"},
        {"id": 20, "name": "Tony Stark", "acc_no": "10020", "balance": "99999"},
        {"id": 21, "name": "Ursula Dittman", "acc_no": "10021", "balance": "4300"},
        {"id": 22, "name": "Victor Doom", "acc_no": "10022", "balance": "6100"},
        {"id": 23, "name": "Wanda Maximoff", "acc_no": "10023", "balance": "8800"},
        {"id": 24, "name": "Xavier Woods", "acc_no": "10024", "balance": "2500"},
        {"id": 25, "name": "Yara Greyjoy", "acc_no": "10025", "balance": "3700"},
        {"id": 26, "name": "Zack Morris", "acc_no": "10026", "balance": "1900"},
        {"id": 27, "name": "Arthur Curry", "acc_no": "10027", "balance": "5200"},
        {"id": 28, "name": "Bruce Wayne", "acc_no": "10028", "balance": "85000"},
        {"id": 29, "name": "Clark Kent", "acc_no": "10029", "balance": "4000"},
        {"id": 30, "name": "Diana Ross", "acc_no": "10030", "balance": "7100"}
    ]
    print("[*] Encrypting and storing records securely...")
    for person in customers:
        encrypted_blob = cipher.encrypt(json.dumps(person).encode())
        cursor.execute("INSERT INTO data_store (payload) VALUES (?)", (encrypted_blob,))
        row_id = cursor.lastrowid
        #terms = person['name'].split() + [person['acc_no']]+[person['balance']]
        terms = person['name'].split() + [person['acc_no']]
        for term in set(terms):
            td = get_trapdoor(term, key, salt)
            cursor.execute("INSERT INTO search_index (trapdoor, data_id) VALUES (?, ?)", (td, row_id))
    conn.commit()
    return conn
# 4. SEARCH FUNCTION
def search_db(query, conn):
    cursor = conn.cursor()
    search_td = get_trapdoor(query, key, salt)
    query_str = '''
        SELECT ds.payload FROM data_store ds
        JOIN search_index si ON ds.id = si.data_id
        WHERE si.trapdoor = ?
    '''
    cursor.execute(query_str, (search_td,))
    rows = cursor.fetchall()
    return [json.loads(cipher.decrypt(row[0]).decode()) for row in rows]
    
# 5. HACKER ATTACK SIMULATION

def hacker_attack_simulation():
    print("\n --- HACKER ATTACK SIMULATION ---")

    conn = sqlite3.connect('encrypted_vault.db')
    cursor = conn.cursor()

    print("\n[Hacker] Viewing database directly:")
    cursor.execute("SELECT * FROM data_store LIMIT 3")
    rows = cursor.fetchall()

    for r in rows:
        print(r)  # encrypted garbage

    print("\n[Hacker] Trying to search 'Alice' without key & salt...")
    fake_trapdoor = hashlib.sha256("alice".encode()).hexdigest()

    cursor.execute("SELECT * FROM search_index WHERE trapdoor=?", (fake_trapdoor,))
    result = cursor.fetchall()

    if not result:
        print("[Hacker]  Failed! Cannot search encrypted DB")

    print("\n[Hacker] Trying to decrypt without key...")
    try:
        print(rows[0][1].decode())
    except:
        print("[Hacker]  Decryption failed!")

    print(" --- ATTACK FAILED ---\n")
    conn.close()


# 6. MAIN


if __name__ == "__main__":
    db_connection = initialize_and_store()
    hacker_attack_simulation()

    try:
        while True:
            term = input("\nSearch (or type 'exit'): ")
            if term.lower() == 'exit':
                break

            results = search_db(term, db_connection)

            if results:
                for r in results:
                    print(f"[+] Match Found: {r}")
            else:
                print("[-] No results found.")

    finally:
        db_connection.close()
        print("[*] Vault closed securely.")