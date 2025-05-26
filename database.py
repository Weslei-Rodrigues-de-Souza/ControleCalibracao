import sqlite3
import os
import json
import datetime

class DatabaseManager:
    def __init__(self, db_file_path):
        self.db_path = db_file_path

    def _get_conn(self):
        db_dir_path = os.path.dirname(self.db_path)
        if db_dir_path and not os.path.exists(db_dir_path):
            try:
                os.makedirs(db_dir_path, exist_ok=True)
                print(f"INFO: Diretório do banco de dados criado: {db_dir_path}")
            except OSError as e:
                print(f"AVISO: Não foi possível criar o diretório do banco de dados {db_dir_path}. Erro: {e}")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False, commit=False, is_ddl=False):
        conn = self._get_conn()
        cursor = conn.cursor()
        last_row_id = None
        success = False
        result_data = None
        try:
            cursor.execute(query, params or ())
            if commit or is_ddl: 
                conn.commit()
                if "INSERT" in query.upper(): 
                    last_row_id = cursor.lastrowid
                success = True
            
            if fetch_one:
                result_data = cursor.fetchone()
                success = True 
            elif fetch_all: 
                result_data = cursor.fetchall()
                success = True
            
            if not (commit or fetch_one or fetch_all or is_ddl): 
                success = True

        except sqlite3.Error as e:
            print(f"Erro BD SQLite: {e} | Query: {query} | Params: {params}")
            success = False
        finally:
            conn.close() 
        
        if commit and success: return last_row_id if last_row_id is not None else True
        if (fetch_one or fetch_all) and success: return result_data
        return success
    
    def create_tables_if_not_exist(self):
        queries = [
            """CREATE TABLE IF NOT EXISTS equipamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, fabricante TEXT, modelo TEXT, 
                numero_serie TEXT UNIQUE, tag TEXT, status TEXT, localizacao TEXT, observacoes_equipamento TEXT,
                tipo_equipamento_id INTEGER, faixa_de_uso TEXT, ultimo_numero_certificado TEXT, 
                ultima_data_calibracao TEXT, proxima_data_calibracao TEXT, 
                ultimo_resultado_geral_certificado TEXT, ativo INTEGER DEFAULT 1, 
                empresa_id INTEGER, 
                requer_calibracao INTEGER DEFAULT 1, em_calibracao INTEGER DEFAULT 0, destino_inativo TEXT,
                FOREIGN KEY (tipo_equipamento_id) REFERENCES tipos_equipamento (id) ON DELETE SET NULL
            )""",
            """CREATE TABLE IF NOT EXISTS tipos_equipamento (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nome_tipo TEXT NOT NULL UNIQUE
            )""",
            """CREATE TABLE IF NOT EXISTS analises_certificado (
                id INTEGER PRIMARY KEY AUTOINCREMENT, equipamento_id INTEGER NOT NULL, 
                data_registro_sistema TEXT NOT NULL, data_analise_manual TEXT, responsavel_analise TEXT,
                numero_certificado_analisado TEXT NOT NULL, data_calibracao_analisada TEXT, 
                data_prox_calibracao_analisada TEXT, resultado_geral_certificado TEXT, observacoes_analise TEXT,
                FOREIGN KEY (equipamento_id) REFERENCES equipamentos (id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS anexos_analise (
                id INTEGER PRIMARY KEY AUTOINCREMENT, analise_id INTEGER NOT NULL, 
                nome_arquivo_original TEXT NOT NULL, nome_arquivo_armazenado TEXT NOT NULL, 
                caminho_relativo_armazenado TEXT NOT NULL, data_anexo TEXT NOT NULL,
                FOREIGN KEY (analise_id) REFERENCES analises_certificado (id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS unidades_medida_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tipo_equipamento_id INTEGER NOT NULL,
                nome_unidade TEXT NOT NULL, simbolo_unidade TEXT,
                FOREIGN KEY (tipo_equipamento_id) REFERENCES tipos_equipamento (id) ON DELETE CASCADE,
                UNIQUE (tipo_equipamento_id, nome_unidade)
            )""",
            """CREATE TABLE IF NOT EXISTS pontos_analisados_certificado (
                id INTEGER PRIMARY KEY AUTOINCREMENT, analise_certificado_id INTEGER NOT NULL,
                nome_ponto TEXT NOT NULL, simbolo_ponto TEXT, valor_nominal_ponto REAL, 
                amplitude_A_ponto REAL, desvio_B_ponto REAL, regra_aplicada_ponto TEXT,
                resultado_ponto TEXT, observacoes_ponto TEXT,
                FOREIGN KEY (analise_certificado_id) REFERENCES analises_certificado (id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS empresas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                razao_social TEXT,
                nome_fantasia TEXT,
                cnpj TEXT UNIQUE NOT NULL,
                logradouro TEXT,
                numero TEXT,
                complemento TEXT,
                bairro TEXT,
                cep TEXT,
                municipio TEXT,
                uf TEXT,
                telefone TEXT,
                email TEXT,
                categoria TEXT NOT NULL CHECK(categoria IN ('Calibração', 'Unidade')),
                certificado_iso_path TEXT 
            )"""
        ]
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            for query in queries:
                cursor.execute(query)
            conn.commit()
            print(f"Tabelas SQLite criadas/verificadas com sucesso em: {self.db_path}")
        except sqlite3.Error as e:
            print(f"Erro BD SQLite ao criar tabelas: {e}")
            conn.rollback()
        finally:
            conn.close()

    def update_schema(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(equipamentos)")
            cols_equip_rows = cursor.fetchall()
            cols_equip = {row['name']: dict(row) for row in cols_equip_rows} if cols_equip_rows else {}

            if 'observacoes' in cols_equip and 'observacoes_equipamento' not in cols_equip:
                 cursor.execute("ALTER TABLE equipamentos RENAME COLUMN observacoes TO observacoes_equipamento")

            campos_equip = {
                "tag": "TEXT", 
                "tipo_equipamento_id": "INTEGER", "faixa_de_uso": "TEXT",
                "ultimo_numero_certificado": "TEXT", "ultima_data_calibracao": "TEXT",
                "proxima_data_calibracao": "TEXT",
                "ultimo_resultado_geral_certificado": "TEXT",
                "observacoes_equipamento": "TEXT",
                "empresa_id": "INTEGER",
                "ativo": "INTEGER DEFAULT 1",
                "requer_calibracao": "INTEGER DEFAULT 1",
                "em_calibracao": "INTEGER DEFAULT 0",
                "destino_inativo": "TEXT"
            }
            for col_name, col_type in campos_equip.items():
                if col_name not in cols_equip:
                    cursor.execute(f"ALTER TABLE equipamentos ADD COLUMN {col_name} {col_type}")

            cursor.execute("PRAGMA table_info(analises_certificado)")
            cols_analise_rows = cursor.fetchall()
            cols_analise = {row['name']: dict(row) for row in cols_analise_rows} if cols_analise_rows else {}
            
            novas_cols_analise = {"data_analise_manual": "TEXT", "responsavel_analise": "TEXT", "resultado_geral_certificado": "TEXT"}
            if "data_registro_analise" in cols_analise and "data_registro_sistema" not in cols_analise:
                cursor.execute("ALTER TABLE analises_certificado RENAME COLUMN data_registro_analise TO data_registro_sistema")
            for col_name, col_type in novas_cols_analise.items():
                if col_name not in cols_analise:
                    cursor.execute(f"ALTER TABLE analises_certificado ADD COLUMN {col_name} {col_type}")
            
            cursor.execute("PRAGMA table_info(empresas)")
            cols_empresas_rows = cursor.fetchall()
            cols_empresas = {row['name']: dict(row) for row in cols_empresas_rows} if cols_empresas_rows else {}
            campos_empresas = {
                "razao_social": "TEXT", "nome_fantasia": "TEXT", "cnpj": "TEXT UNIQUE NOT NULL",
                "logradouro": "TEXT", "numero": "TEXT", "complemento": "TEXT", "bairro": "TEXT",
                "cep": "TEXT", "municipio": "TEXT", "uf": "TEXT", "telefone": "TEXT", "email": "TEXT",
                "categoria": "TEXT NOT NULL CHECK(categoria IN ('Calibração', 'Unidade'))",
                "certificado_iso_path": "TEXT" 
            }
            for col_name, col_type in campos_empresas.items():
                if col_name not in cols_empresas:
                    if "CHECK" in col_type:
                        col_type_only = col_type.split(" CHECK")[0]
                        cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col_name} {col_type_only}")
                    else:
                         cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col_name} {col_type}")
            conn.commit()
        except sqlite3.Error as e:
            print(f"Erro ao atualizar esquema SQLite: {e}")
        finally:
            conn.close()

    def fetch_all_equipamentos_completos(self):
        query = """SELECT e.*, te.nome_tipo as tipo_equipamento_nome, emp.nome_fantasia as empresa_nome 
                   FROM equipamentos e 
                   LEFT JOIN tipos_equipamento te ON e.tipo_equipamento_id = te.id
                   LEFT JOIN empresas emp ON e.empresa_id = emp.id
                   ORDER BY e.nome"""
        return self.execute_query(query, fetch_all=True) or []

    def fetch_equipamento_completo_by_id(self, equip_id):
        query = """SELECT e.*, te.nome_tipo as tipo_equipamento_nome, emp.nome_fantasia as empresa_nome
                   FROM equipamentos e
                   LEFT JOIN tipos_equipamento te ON e.tipo_equipamento_id = te.id
                   LEFT JOIN empresas emp ON e.empresa_id = emp.id
                   WHERE e.id = ?""" 
        return self.execute_query(query, (equip_id,), fetch_one=True)

    def add_equipamento(self, data):
        query = """INSERT INTO equipamentos (nome, fabricante, modelo, numero_serie, tag, status, localizacao,
                                          observacoes_equipamento, tipo_equipamento_id, faixa_de_uso,
                                          empresa_id, ativo, requer_calibracao, em_calibracao, destino_inativo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (
            data.get('nome'), data.get('fabricante'), data.get('modelo'), data.get('numero_serie'),
            data.get('tag'),
            data.get('status'), data.get('localizacao'), data.get('observacoes_equipamento'),
            data.get('tipo_equipamento_id'), data.get('faixa_de_uso'),
            1 if data.get('ativo') else 0,
            1 if data.get('requer_calibracao') else 0,
            1 if data.get('em_calibracao') else 0,
            data.get('destino_inativo'),
            data.get('empresa_id')
        )
        return self.execute_query(query, params, commit=True)

    def update_equipamento_principal(self, equip_id, data):
        query = """UPDATE equipamentos SET nome=?, fabricante=?, modelo=?, 
                          numero_serie=?, tag=?, status=?, localizacao=?, 
                          observacoes_equipamento=?, tipo_equipamento_id=?, empresa_id=?,
                          faixa_de_uso=?, ativo=?, requer_calibracao=?, 
                          em_calibracao=?, destino_inativo=?
                   WHERE id=?"""
        params = (
            data.get('nome'), data.get('fabricante'), data.get('modelo'), data.get('numero_serie'),
            data.get('tag'),
            data.get('status'), data.get('localizacao'), data.get('observacoes_equipamento'),
            data.get('tipo_equipamento_id'), data.get('faixa_de_uso'),
            data.get('empresa_id'),
            1 if data.get('ativo') else 0,
            1 if data.get('requer_calibracao') else 0,
            1 if data.get('em_calibracao') else 0,
            data.get('destino_inativo'),
            equip_id
        )
        return self.execute_query(query, params, commit=True)

    def delete_equipamento(self, equip_id, app_upload_folder, app_utils_instance=None): 
        analises = self.fetch_analises_by_equipamento_id(equip_id, app_utils_instance=app_utils_instance)
        for analise in analises: 
            self.delete_analise_certificado(analise['id'], app_upload_folder, app_utils_instance=app_utils_instance) 
        return self.execute_query("DELETE FROM equipamentos WHERE id=?", (equip_id,), commit=True)

    def fetch_all_tipos_equipamento(self):
        return self.execute_query("SELECT id, nome_tipo FROM tipos_equipamento ORDER BY nome_tipo", fetch_all=True) or []
    
    def fetch_tipo_equipamento_by_id(self, tipo_id):
        return self.execute_query("SELECT id, nome_tipo FROM tipos_equipamento WHERE id = ?", (tipo_id,), fetch_one=True)

    def add_tipo_equipamento(self, nome_tipo):
        return self.execute_query("INSERT INTO tipos_equipamento (nome_tipo) VALUES (?)", (nome_tipo,), commit=True)
            
    def update_tipo_equipamento(self, tipo_id, novo_nome_tipo):
        return self.execute_query("UPDATE tipos_equipamento SET nome_tipo = ? WHERE id = ?", (novo_nome_tipo, tipo_id), commit=True)

    def delete_tipo_equipamento(self, tipo_id):
        equip_usando = self.execute_query("SELECT 1 FROM equipamentos WHERE tipo_equipamento_id = ? LIMIT 1", (tipo_id,), fetch_one=True)
        if equip_usando:
            return "EM_USO" 
        return self.execute_query("DELETE FROM tipos_equipamento WHERE id = ?", (tipo_id,), commit=True)

    def fetch_unidades_by_tipo_id(self, tipo_equip_id):
        if tipo_equip_id is None:
            return []
        return self.execute_query("SELECT id, nome_unidade, simbolo_unidade FROM unidades_medida_config WHERE tipo_equipamento_id = ? ORDER BY nome_unidade", (tipo_equip_id,), fetch_all=True) or []

    def add_unidade_medida_config(self, tipo_equip_id, nome_unidade, simbolo_unidade):
        return self.execute_query("INSERT INTO unidades_medida_config (tipo_equipamento_id, nome_unidade, simbolo_unidade) VALUES (?, ?, ?)", (tipo_equip_id, nome_unidade, simbolo_unidade), commit=True)
            
    def delete_unidade_medida_config(self, unidade_id):
        return self.execute_query("DELETE FROM unidades_medida_config WHERE id = ?", (unidade_id,), commit=True)

    def fetch_analises_by_equipamento_id(self, equip_id, add_is_latest_flag=False, app_utils_instance=None):
        query = """SELECT a.*, 
                          (SELECT COUNT(*) FROM anexos_analise an WHERE an.analise_id = a.id) as anexos_count,
                          (SELECT COUNT(*) FROM pontos_analisados_certificado p WHERE p.analise_certificado_id = a.id) as pontos_count
                   FROM analises_certificado a 
                   WHERE a.equipamento_id = ? 
                   ORDER BY a.id DESC""" 
        analises_rows = self.execute_query(query, (equip_id,), fetch_all=True) or []
        
        analises_list = []
        for i, row_proxy in enumerate(analises_rows):
            analise_dict = dict(row_proxy) 
            if add_is_latest_flag:
                analise_dict['is_latest'] = (i == 0) 
            if app_utils_instance: 
                for date_field in ['data_analise_manual', 'data_calibracao_analisada', 'data_prox_calibracao_analisada', 'data_registro_sistema']:
                    analise_dict[date_field + '_fmt'] = app_utils_instance.format_date_for_display(analise_dict.get(date_field))
            analises_list.append(analise_dict)
        
        if add_is_latest_flag: 
            analises_list.sort(key=lambda x: (x['data_analise_manual'] or x['data_registro_sistema'] or str(x['id'])), reverse=True)
        
        return analises_list
    
    def fetch_analise_by_id(self, analise_id, app_utils_instance=None):
        analise_row = self.execute_query("SELECT * FROM analises_certificado WHERE id = ?", (analise_id,), fetch_one=True)
        if not analise_row:
            return None
        
        analise_data = dict(analise_row)
        todas_analises_equip = self.fetch_analises_by_equipamento_id(analise_data['equipamento_id'], add_is_latest_flag=True, app_utils_instance=app_utils_instance)
        
        is_latest_found = False
        for an_hist in todas_analises_equip:
            if an_hist['id'] == analise_id:
                analise_data['is_latest'] = an_hist['is_latest']
                is_latest_found = True
                break
        if not is_latest_found: 
             analise_data['is_latest'] = False 
        
        if app_utils_instance:
            for date_field in ['data_analise_manual', 'data_calibracao_analisada', 'data_prox_calibracao_analisada', 'data_registro_sistema']:
                analise_data[date_field + '_fmt'] = app_utils_instance.format_date_for_display(analise_data.get(date_field))
             
        return analise_data

    def add_analise_certificado(self, equip_id, data, pontos_analise_json=None):
        query = """INSERT INTO analises_certificado (equipamento_id, data_registro_sistema, data_analise_manual,
                                                 responsavel_analise, numero_certificado_analisado,
                                                 data_calibracao_analisada, data_prox_calibracao_analisada,
                                                 resultado_geral_certificado, observacoes_analise)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (
            equip_id, data.get('data_registro_sistema', datetime.date.today().isoformat()),
            data.get('data_analise_manual'), data.get('responsavel_analise'),
            data.get('numero_certificado_analisado'), data.get('data_calibracao_analisada'),
            data.get('data_prox_calibracao_analisada'), data.get('resultado_geral_certificado'),
            data.get('observacoes_analise')
        )
        analise_id = self.execute_query(query, params, commit=True)
        if analise_id and pontos_analise_json:
            try:
                pontos = json.loads(pontos_analise_json)
                for ponto_data in pontos:
                    self.add_ponto_analisado(analise_id, ponto_data)
            except json.JSONDecodeError:
                print("Erro ao processar pontos da análise (JSON inválido) ao adicionar.")
        return analise_id

    def update_analise_certificado(self, analise_id, data, pontos_analise_json=None, app_utils_instance=None):
        analise_atual = self.fetch_analise_by_id(analise_id, app_utils_instance=app_utils_instance)
        if not analise_atual:
            return "NOT_FOUND"
        if not analise_atual.get('is_latest', False): 
            return "NOT_LATEST"

        query = """UPDATE analises_certificado SET data_analise_manual = ?, 
                          responsavel_analise = ?,
                          numero_certificado_analisado = ?, 
                          data_calibracao_analisada = ?,
                          data_prox_calibracao_analisada = ?, 
                          resultado_geral_certificado = ?,
                          observacoes_analise = ?
                   WHERE id = ?"""
        params = (
            data.get('data_analise_manual'), data.get('responsavel_analise'),
            data.get('numero_certificado_analisado'), data.get('data_calibracao_analisada'),
            data.get('data_prox_calibracao_analisada'), data.get('resultado_geral_certificado'),
            data.get('observacoes_analise'), analise_id
        )
        success = self.execute_query(query, params, commit=True)
        if success and pontos_analise_json:
            self.delete_all_pontos_for_analise(analise_id) 
            try:
                pontos = json.loads(pontos_analise_json)
                for ponto_data in pontos:
                    self.add_ponto_analisado(analise_id, ponto_data)
            except json.JSONDecodeError:
                 print("Erro ao processar pontos da análise (JSON inválido) ao atualizar.")
        return success

    def delete_analise_certificado(self, analise_id, upload_folder, app_utils_instance=None): 
        analise_info = self.fetch_analise_by_id(analise_id, app_utils_instance=app_utils_instance)
        if not analise_info:
            print(f"Tentativa de excluir análise ID {analise_id} que não foi encontrada.")
            return False, None 
        
        equip_id = analise_info['equipamento_id']

        self.delete_all_pontos_for_analise(analise_id)
        self.delete_all_anexos_for_analise(analise_id, upload_folder)
        delete_success = self.execute_query("DELETE FROM analises_certificado WHERE id = ?", (analise_id,), commit=True)

        if delete_success:
            novas_analises_restantes = self.fetch_analises_by_equipamento_id(equip_id, add_is_latest_flag=True, app_utils_instance=app_utils_instance)
            if novas_analises_restantes:
                nova_analise_mais_recente = novas_analises_restantes[0] 
                dados_para_equip = {
                    'numero_certificado_analisado': nova_analise_mais_recente.get('numero_certificado_analisado'),
                    'data_calibracao_analisada': nova_analise_mais_recente.get('data_calibracao_analisada'),
                    'data_prox_calibracao_analisada': nova_analise_mais_recente.get('data_prox_calibracao_analisada'),
                    'resultado_geral_certificado': nova_analise_mais_recente.get('resultado_geral_certificado')
                }
                self.update_ultima_analise_em_equipamento(equip_id, dados_para_equip)
            else: 
                dados_para_equip_vazios = {
                    'numero_certificado_analisado': None, 'data_calibracao_analisada': None,
                    'data_prox_calibracao_analisada': None, 'resultado_geral_certificado': None
                }
                self.update_ultima_analise_em_equipamento(equip_id, dados_para_equip_vazios)
            return True, equip_id 
        return False, equip_id 

    def fetch_pontos_by_analise_id(self, analise_id):
        return self.execute_query("SELECT * FROM pontos_analisados_certificado WHERE analise_certificado_id = ? ORDER BY nome_ponto", (analise_id,), fetch_all=True) or []

    def add_ponto_analisado(self, analise_id, ponto_data):
        query = """INSERT INTO pontos_analisados_certificado
                   (analise_certificado_id, nome_ponto, simbolo_ponto, 
                    amplitude_A_ponto, desvio_B_ponto, regra_aplicada_ponto, resultado_ponto, observacoes_ponto, valor_nominal_ponto)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""" 
        params = (analise_id, ponto_data.get('nome_ponto'), ponto_data.get('simbolo_ponto'),
                  ponto_data.get('amplitude_A_ponto'), ponto_data.get('desvio_B_ponto'), 
                  ponto_data.get('regra_aplicada_ponto'), ponto_data.get('resultado_ponto'), 
                  ponto_data.get('observacoes_ponto'),
                  ponto_data.get('valor_nominal_ponto', None)) 
        return self.execute_query(query, params, commit=True)

    def delete_all_pontos_for_analise(self, analise_id):
        return self.execute_query("DELETE FROM pontos_analisados_certificado WHERE analise_certificado_id = ?", (analise_id,), commit=True)

    def add_anexo(self, analise_id, nome_original, nome_armazenado, caminho_relativo):
        query = """INSERT INTO anexos_analise
                   (analise_id, nome_arquivo_original, nome_arquivo_armazenado, caminho_relativo_armazenado, data_anexo)
                   VALUES (?, ?, ?, ?, ?)"""
        params = (analise_id, nome_original, nome_armazenado, caminho_relativo, datetime.date.today().isoformat())
        return self.execute_query(query, params, commit=True)
        
    def fetch_anexos_by_analise_id(self, analise_id):
        return self.execute_query("SELECT * FROM anexos_analise WHERE analise_id = ? ORDER BY nome_arquivo_original", (analise_id,), fetch_all=True) or []

    def delete_anexo(self, anexo_id, upload_folder):
        anexo = self.execute_query("SELECT caminho_relativo_armazenado FROM anexos_analise WHERE id = ?", (anexo_id,), fetch_one=True)
        if anexo:
            caminho_completo = os.path.join(upload_folder, anexo['caminho_relativo_armazenado'])
            if self.execute_query("DELETE FROM anexos_analise WHERE id = ?", (anexo_id,), commit=True):
                if os.path.exists(caminho_completo):
                    try:
                        os.remove(caminho_completo)
                        dir_analise = os.path.dirname(caminho_completo)
                        if not os.listdir(dir_analise): os.rmdir(dir_analise)
                    except OSError as e_os:
                        print(f"Aviso: Erro ao excluir arquivo/pasta do anexo {anexo_id}: {e_os}")
                return True
        print(f"Falha ao excluir anexo ID {anexo_id} do DB ou ficheiro não encontrado.")
        return False
        
    def delete_all_anexos_for_analise(self, analise_id, upload_folder):
        anexos = self.fetch_anexos_by_analise_id(analise_id)
        all_deleted_ok = True
        for anexo_data in anexos: 
            if not self.delete_anexo(anexo_data['id'], upload_folder):
                all_deleted_ok = False
        
        dir_analise_especifica = os.path.join(upload_folder, str(analise_id))
        if os.path.exists(dir_analise_especifica):
            try:
                if not os.listdir(dir_analise_especifica): 
                    os.rmdir(dir_analise_especifica)
            except OSError as e:
                print(f"Aviso: Não foi possível remover o diretório de anexos vazio para a análise {analise_id}: {e}")
        return all_deleted_ok

    def update_ultima_analise_em_equipamento(self, equip_id, analise_data_dict):
        query = """UPDATE equipamentos SET ultimo_numero_certificado = ?, 
                          ultima_data_calibracao = ?,
                          proxima_data_calibracao = ?, 
                          ultimo_resultado_geral_certificado = ?
                   WHERE id = ?"""
        params = (
            analise_data_dict.get('numero_certificado_analisado'),
            analise_data_dict.get('data_calibracao_analisada'),
            analise_data_dict.get('data_prox_calibracao_analisada'),
            analise_data_dict.get('resultado_geral_certificado'),
            equip_id
        )
        return self.execute_query(query, params, commit=True)
        
    def search_equipamentos(self, search_term):
        query = """SELECT e.*, te.nome_tipo as tipo_equipamento_nome
                   FROM equipamentos e LEFT JOIN tipos_equipamento te ON e.tipo_equipamento_id = te.id
                   WHERE e.nome LIKE ? OR e.modelo LIKE ? OR e.numero_serie LIKE ? OR e.fabricante LIKE ?
                         OR e.localizacao LIKE ? OR e.ultimo_numero_certificado LIKE ? OR e.tag LIKE ?
                         OR e.ultimo_resultado_geral_certificado LIKE ? OR te.nome_tipo LIKE ? OR e.faixa_de_uso LIKE ?
                         OR e.status LIKE ? OR e.destino_inativo LIKE ?
                   ORDER BY e.nome"""
        like_term = f"%{search_term}%"
        params = (like_term,) * 12 
        return self.execute_query(query, params, fetch_all=True) or []

    # --- Métodos CRUD para Empresas ---
    def add_empresa(self, data):
        query = """INSERT INTO empresas (razao_social, nome_fantasia, cnpj, logradouro, numero, complemento, 
                                        bairro, cep, municipio, uf, telefone, email, categoria, certificado_iso_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (
            data.get('razao_social'), data.get('nome_fantasia'), data.get('cnpj'),
            data.get('logradouro'), data.get('numero'), data.get('complemento'),
            data.get('bairro'), data.get('cep'), data.get('municipio'), data.get('uf'),
            data.get('telefone'), data.get('email'), data.get('categoria'),
            data.get('certificado_iso_path') 
        )
        return self.execute_query(query, params, commit=True)

    def fetch_all_empresas(self):
        return self.execute_query("SELECT * FROM empresas ORDER BY nome_fantasia, razao_social", fetch_all=True) or []

    def fetch_empresa_by_id(self, empresa_id):
        return self.execute_query("SELECT * FROM empresas WHERE id = ?", (empresa_id,), fetch_one=True)

    def update_empresa(self, empresa_id, data):
        campos_para_atualizar = []
        params = []
        
        campos_permitidos = ['razao_social', 'nome_fantasia', 'cnpj', 'logradouro', 'numero', 
                             'complemento', 'bairro', 'cep', 'municipio', 'uf', 'telefone', 
                             'email', 'categoria', 'certificado_iso_path']

        for campo in campos_permitidos:
            if campo in data or (campo == 'certificado_iso_path' and data.get('remover_certificado_iso_atual') == '1'): # Verifica se o campo existe ou se é para remover o certificado
                if campo == 'certificado_iso_path' and data.get(campo) is None and data.get('remover_certificado_iso_atual') != '1':
                    # Não atualiza o path se não for para remover e nenhum novo arquivo for enviado
                    # Mas se for para remover e não houver novo arquivo, data[campo] será None e será atualizado
                    continue
                
                campos_para_atualizar.append(f"{campo}=?")
                params.append(data.get(campo)) # Usa data.get(campo) para pegar o valor (pode ser None se for para limpar)
        
        if not campos_para_atualizar:
            return True 

        query = f"UPDATE empresas SET {', '.join(campos_para_atualizar)} WHERE id=?"
        params.append(empresa_id)
        
        return self.execute_query(query, tuple(params), commit=True)

    def delete_empresa(self, empresa_id, upload_folder_empresas):
        empresa = self.fetch_empresa_by_id(empresa_id)
        if empresa and empresa['certificado_iso_path']:
            caminho_completo = os.path.join(upload_folder_empresas, empresa['certificado_iso_path'])
            if os.path.exists(caminho_completo):
                try:
                    os.remove(caminho_completo)
                    dir_empresa = os.path.dirname(caminho_completo)
                    if os.path.exists(dir_empresa) and not os.listdir(dir_empresa): # Verifica se o diretório está vazio
                        os.rmdir(dir_empresa)
                except OSError as e:
                    print(f"Aviso: Erro ao excluir arquivo/pasta do certificado ISO da empresa {empresa_id}: {e}")
        
        return self.execute_query("DELETE FROM empresas WHERE id = ?", (empresa_id,), commit=True)

    def fetch_empresas_unidade(self):
        query = "SELECT * FROM empresas WHERE categoria = 'Unidade'"
        return self.execute_query(query, fetch_all=True) or []

    def fetch_tipo_by_id(self, tipo_id):
        query = "SELECT * FROM tipos_equipamento WHERE id = ?"
        return self.execute_query(query, (tipo_id,), fetch_one=True)

    def fetch_empresas_calibracao(self):
        query = "SELECT * FROM empresas WHERE categoria = 'Calibração'"
        return self.execute_query(query, fetch_all=True) or []