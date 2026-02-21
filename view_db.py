import sqlite3

def peek_inside():
    conn = sqlite3.connect('encrypted_vault.db')
    cursor = conn.cursor()

    print("\n--- TABLE: data_store (The Encrypted Blobs) ---")
    cursor.execute("SELECT * FROM data_store")
    for row in cursor.fetchall():
        # row[1] is the BLOB. We show the first 50 chars to see the encryption.
        print(f"ID: {row[0]} | Encrypted Data: {row[1][:50]}...")

    print("\n--- TABLE: search_index (The Hashed Trapdoors) ---")
    cursor.execute("SELECT * FROM search_index")
    for row in cursor.fetchall():
        print(f"Trapdoor: {row[0]} | Points to ID: {row[1]}")

    conn.close()

if __name__ == "__main__":
    peek_inside()