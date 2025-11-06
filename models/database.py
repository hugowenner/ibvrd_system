import sqlite3
import os
import shutil
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Any

from config.settings import Config, logger
from utils.validators import Validators as V

# models/entities.py ficaria com classes de dados simples (TypedDict ou dataclasses)

class DatabaseManager:
    """Gerenciador de banco de dados com cache e otimizações"""
    
    def __init__(self, db_name: str = Config.DB_NAME):
        self.db_name = db_name
        self._cache: Dict[str, Any] = {}
        self._ensure_db()
        self._last_backup = self._get_last_backup_time()
        logger.info(f'Database inicializado: {db_name}')
    
    @contextmanager
    def _get_connection(self):
        """Context manager para conexões"""
        conn = sqlite3.connect(
            self.db_name,
            detect_types=sqlite3.PARSE_DECLTYPES,
            # Permite que a UI thread acesse o DB sem erro, se necessário
            check_same_thread=False 
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _ensure_db(self):
        """Cria estrutura do banco e índices"""
        # ... (O código _ensure_db é o mesmo que o original)
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # Tabela pessoas
            cur.execute('''
                CREATE TABLE IF NOT EXISTS pessoas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    cpf TEXT UNIQUE,
                    telefone TEXT,
                    cidade TEXT,
                    bairro TEXT,
                    data_nascimento TEXT,
                    email TEXT,
                    rede_social TEXT,
                    observacoes TEXT,
                    ativo INTEGER DEFAULT 1,
                    data_cadastro TEXT NOT NULL,
                    data_atualizacao TEXT
                )
            ''')
            
            # Tabela eventos
            cur.execute('''
                CREATE TABLE IF NOT EXISTS eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    descricao TEXT,
                    data_evento TEXT NOT NULL,
                    tipo TEXT DEFAULT 'geral',
                    local TEXT,
                    responsavel TEXT,
                    ativo INTEGER DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT
                )
            ''')
            
            # Tabela de configurações
            cur.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    chave TEXT PRIMARY KEY,
                    valor TEXT,
                    atualizado_em TEXT
                )
            ''')
            
            # Índices
            indices = [
                'CREATE INDEX IF NOT EXISTS idx_pessoas_cpf ON pessoas(cpf)',
                'CREATE INDEX IF NOT EXISTS idx_pessoas_nome ON pessoas(nome)',
                'CREATE INDEX IF NOT EXISTS idx_pessoas_cidade ON pessoas(cidade)',
                'CREATE INDEX IF NOT EXISTS idx_pessoas_ativo ON pessoas(ativo)',
                'CREATE INDEX IF NOT EXISTS idx_eventos_data ON eventos(data_evento)',
                'CREATE INDEX IF NOT EXISTS idx_eventos_tipo ON eventos(tipo)',
                'CREATE INDEX IF NOT EXISTS idx_eventos_ativo ON eventos(ativo)'
            ]
            
            for idx in indices:
                cur.execute(idx)
            
            conn.commit()
    
    def clear_cache(self):
        """Limpa cache"""
        self._cache.clear()
    
    # ========== Métodos de acesso direto ao DB (CRUD Básico e Consultas) ==========
    
    def execute_query(self, query: str, params: Optional[Tuple] = None, fetch_one: bool = False) -> Any:
        """Executa uma query customizada (SELECT)"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params or ())
            return cur.fetchone() if fetch_one else cur.fetchall()

    def execute_command(self, query: str, params: Optional[Tuple] = None, get_last_row_id: bool = False) -> int:
        """Executa um comando customizado (INSERT, UPDATE, DELETE)"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params or ())
            conn.commit()
            if get_last_row_id:
                return cur.lastrowid
            return cur.rowcount

    # ... (Os métodos CRUD originais de pessoa, evento e config permanecem aqui para manter a responsabilidade do DB)
    
    # Exemplo: refatorando add_pessoa para usar V.normalize_cpf
    def add_pessoa(self, pessoa: Dict) -> int:
        """Adiciona pessoa"""
        pessoa = pessoa.copy()
        pessoa['cpf'] = V.normalize_cpf(pessoa.get('cpf', ''))
        pessoa['telefone'] = V.normalize_phone(pessoa.get('telefone', ''))
        pessoa['data_cadastro'] = datetime.now().strftime(Config.DATETIME_FORMAT)
        
        # ... (Query de INSERT e commit)
        query = '''
            INSERT INTO pessoas (
                nome, cpf, telefone, cidade, bairro, data_nascimento,
                email, rede_social, observacoes, data_cadastro
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            pessoa.get('nome'), pessoa.get('cpf'), pessoa.get('telefone'),
            pessoa.get('cidade'), pessoa.get('bairro'), pessoa.get('data_nascimento'),
            pessoa.get('email'), pessoa.get('rede_social'), pessoa.get('observacoes'),
            pessoa.get('data_cadastro')
        )
        
        pessoa_id = self.execute_command(query, params, get_last_row_id=True)
        
        self.clear_cache()
        logger.info(f"Pessoa cadastrada: {pessoa.get('nome')} (ID: {pessoa_id})")
        return pessoa_id
    
    # Os métodos search_pessoas e search_eventos serão movidos para os services
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do sistema (mantido aqui por ser uma consulta agregada)"""
        # ... (O código get_statistics é o mesmo que o original)
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            stats: Dict[str, Any] = {}
            
            # Total de pessoas
            cur.execute('SELECT COUNT(*) as total FROM pessoas WHERE ativo=1')
            stats['total_pessoas'] = cur.fetchone()['total']
            
            # Aniversariantes do mês
            mes_atual = datetime.now().strftime('%m')
            cur.execute('''
                SELECT COUNT(*) as total FROM pessoas
                WHERE ativo=1 AND substr(data_nascimento, 4, 2)=?
            ''', (mes_atual,))
            stats['aniversariantes_mes'] = cur.fetchone()['total']
            
            # Total de eventos
            cur.execute('SELECT COUNT(*) as total FROM eventos WHERE ativo=1')
            stats['total_eventos'] = cur.fetchone()['total']
            
            # Eventos próximos (30 dias)
            hoje = datetime.now().strftime('%Y-%m-%d')
            futuro = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cur.execute('''
                SELECT COUNT(*) as total FROM eventos
                WHERE ativo=1 AND date(
                    substr(data_evento,7,4)||'-'||
                    substr(data_evento,4,2)||'-'||
                    substr(data_evento,1,2)
                ) BETWEEN date(?) AND date(?)
            ''', (hoje, futuro))
            stats['eventos_proximos'] = cur.fetchone()['total']
            
            # Cidades
            cur.execute('''
                SELECT COUNT(DISTINCT cidade) as total FROM pessoas
                WHERE ativo=1 AND cidade IS NOT NULL AND cidade != ''
            ''')
            stats['total_cidades'] = cur.fetchone()['total']
            
            return stats
    
    # Backup/Config (métodos _get_last_backup_time, should_backup, _set_config, _get_config)
    # ... (O código é o mesmo que o original)
    def create_backup(self) -> str:
        """Cria backup do banco"""
        Path(Config.BACKUP_DIR).mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(Config.BACKUP_DIR, f'backup_{timestamp}.db')
        
        shutil.copy2(self.db_name, backup_path)
        
        self._cleanup_old_backups()
        self._set_config('last_backup', datetime.now().isoformat())
        
        logger.info(f'Backup criado: {backup_path}')
        return backup_path

    def _cleanup_old_backups(self):
        """Remove backups antigos"""
        backups = sorted(Path(Config.BACKUP_DIR).glob('backup_*.db'))
        while len(backups) > Config.MAX_BACKUPS:
            oldest = backups.pop(0)
            oldest.unlink()
            logger.info(f'Backup removido: {oldest}')
    
    def _get_last_backup_time(self) -> Optional[datetime]:
        """Retorna data do último backup"""
        val = self._get_config('last_backup')
        if val:
            try:
                return datetime.fromisoformat(val)
            except:
                pass
        return None
    
    def should_backup(self) -> bool:
        """Verifica se deve fazer backup"""
        if not self._last_backup:
            return True
        
        hours_since = (datetime.now() - self._last_backup).total_seconds() / 3600
        return hours_since >= Config.AUTO_BACKUP_INTERVAL

    def _set_config(self, key: str, value: str):
        """Salva configuração"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO config (chave, valor, atualizado_em)
                VALUES (?, ?, ?)
            ''', (key, value, datetime.now().isoformat()))
            conn.commit()
    
    def _get_config(self, key: str) -> Optional[str]:
        """Obtém configuração"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT valor FROM config WHERE chave=?', (key,))
            row = cur.fetchone()
            return row['valor'] if row else None