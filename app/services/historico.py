from app.db import get_db_connection
from datetime import datetime

def registrar_tentativa_acesso(matricula: str, status: str, erro: str = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        """pega a hora atual"""
        data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO historico_acessos (matricula, data_hora, resultado, detalhes_erro)
            VALUES (?, ?, ?, ?)
        ''', (matricula, data_atual, status, erro))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao salvar log: {e}")
        return False
