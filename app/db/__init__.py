import sqlite3
import os

# Pega o caminho raiz do projeto para salvar o ifpass.db no lugar certo
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'ifpass.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Cria a tabela seguindo as regras do PO
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_acessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            resultado TEXT NOT NULL,
            detalhes_erro TEXT
        )
    ''')
    conn.commit()
    conn.close()
