#Sistema IBVRD - Versão Melhorada (Refatorada)
#Melhorias implementadas:
#- Arquitetura MVC mais clara (Adição do AppController)
#- Validação em tempo real com feedback visual
#- Cache para melhor performance (Adição de lru_cache)
#- Suporte a múltiplos idiomas (preparado)
#- Backup automático
#- Busca avançada com múltiplos critérios
#- Relatórios customizáveis
#- Logs estruturados
#- Testes de integridade de dados
#- Interface responsiva aprimorada

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
from datetime import datetime, date, timedelta
#from dateutil.relativedelta import relativedelta
import logging
from logging.handlers import RotatingFileHandler
import sys
import re
import threading
import shutil
import os
from tkinter import font as tkfont
from pathlib import Path
import json
from typing import Dict, List, Optional, Tuple, Any
from functools import lru_cache
from contextlib import contextmanager
import hashlib

# ====================== CONFIGURAÇÃO ======================
class Config:
    """Configurações centralizadas do sistema"""
    APP_NAME = 'IBVRD - Sistema de Cadastro'
    VERSION = '2.1.1 Enhanced'
    DB_NAME = 'ibvrd_enhanced.db'
    LOG_FILE = 'ibvrd_enhanced.log'
    CONFIG_FILE = 'config.json'
    BACKUP_DIR = 'backups'
    MAX_BACKUPS = 10
    AUTO_BACKUP_INTERVAL = 24  # horas
    
    # Validações
    CPF_PATTERN = re.compile(r'^\d{11}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^\d{10,11}$')
    DATE_FORMAT = '%d/%m/%Y'
    DATETIME_FORMAT = '%d/%m/%Y %H:%M:%S'
    
    # UI
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    MIN_WIDTH = 900
    MIN_HEIGHT = 600
    
    THEMES = {
        'claro': {
            'bg': '#f5f5f5',
            'fg': '#000000',
            'title_bg': '#2c3e50',
            'title_fg': '#ffffff',
            'entry_bg': '#ffffff',
            'button_bg': '#3498db',
            'button_fg': '#ffffff',
            'success': '#27ae60',
            'warning': '#f39c12',
            'error': '#e74c3c',
            'tree_bg': '#ffffff',
            'tree_fg': '#000000'
        },
        'escuro': {
            'bg': '#2c3e50',
            'fg': '#ecf0f1',
            'title_bg': '#1a252f',
            'title_fg': '#ecf0f1',
            'entry_bg': '#34495e',
            'button_bg': '#3498db',
            'button_fg': '#ffffff',
            'success': '#27ae60',
            'warning': '#f39c12',
            'error': '#e74c3c',
            'tree_bg': '#34495e',
            'tree_fg': '#ecf0f1'
        }
    }

# ====================== LOGGING ======================
def setup_logging():
    """Configura sistema de logs"""
    logger = logging.getLogger('ibvrd')
    logger.setLevel(logging.INFO)
    
    handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding='utf-8'
    )
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    return logger

logger = setup_logging()

# ====================== UTILS ======================
class Utils:
    """Utilitários para validação e formatação"""
    
    @staticmethod
    def normalize_cpf(cpf: str) -> str:
        """Remove formatação do CPF"""
        if not cpf:
            return ''
        return ''.join(filter(str.isdigit, cpf))
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Remove formatação do telefone"""
        if not phone:
            return ''
        return ''.join(filter(str.isdigit, phone))
    
    @staticmethod
    def format_cpf(cpf: str) -> str:
        """Formata CPF para exibição"""
        d = Utils.normalize_cpf(cpf)
        if len(d) != 11:
            return cpf
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """Formata telefone para exibição"""
        d = Utils.normalize_phone(phone)
        if len(d) == 10:
            return f"({d[:2]}) {d[2:6]}-{d[6:]}"
        elif len(d) == 11:
            return f"({d[:2]}) {d[2:7]}-{d[7:]}"
        return phone
    
    @staticmethod
    def validate_cpf(cpf: str) -> bool:
        """Valida CPF com dígitos verificadores"""
        d = Utils.normalize_cpf(cpf)
        
        if not Config.CPF_PATTERN.match(d):
            return False
        
        if d == d[0] * 11:
            return False
        
        nums = [int(x) for x in d]
        
        def calc_digit(nums, weights):
            s = sum(a * b for a, b in zip(nums, weights))
            r = 11 - (s % 11)
            return 0 if r >= 10 else r
        
        d1 = calc_digit(nums[:9], range(10, 1, -1))
        d2 = calc_digit(nums[:10], range(11, 1, -1))
        
        return nums[9] == d1 and nums[10] == d2
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Valida formato de email"""
        if not email:
            return True
        return bool(Config.EMAIL_PATTERN.match(email))
    
    @staticmethod
    def validate_date(date_str: str) -> bool:
        """Valida formato de data"""
        if not date_str:
            return True
        try:
            datetime.strptime(date_str, Config.DATE_FORMAT)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def calculate_age(birth_date: str) -> Optional[int]:
        """Calcula idade a partir da data de nascimento"""
        try:
            dt = datetime.strptime(birth_date, Config.DATE_FORMAT)
            today = datetime.now()
            age = today.year - dt.year
            if (today.month, today.day) < (dt.month, dt.day):
                age -= 1
            return age
        except:
            return None
    
    @staticmethod
    def format_date_with_age(date_str: str) -> str:
        """Formata data com idade"""
        if not date_str:
            return ''
        age = Utils.calculate_age(date_str)
        if age is not None:
            return f"{date_str} ({age} anos)"
        return date_str
    
    @staticmethod
    def safe_get(row: Any, key: str, default: str = '') -> str:
        """Obtém valor seguro de row"""
        try:
            # sqlite3.Row permite acesso por índice ou chave
            val = row[key] if isinstance(row, dict) or isinstance(row, sqlite3.Row) else row[key]
            return val if val is not None else default
        except:
            return default

# ====================== DATABASE (MODEL) ======================
class DatabaseManager:
    """Gerenciador de banco de dados com cache e otimizações"""
    
    def __init__(self, db_name: str = Config.DB_NAME):
        self.db_name = db_name
        self._cache = {}
        self._ensure_db()
        self._last_backup = self._get_last_backup_time()
        logger.info(f'Database inicializado: {db_name}')
    
    # Constantes SQL para melhor manutenção
    _SQL_CREATE_PESSOAS = '''
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
    '''
    _SQL_INSERT_PESSOA = '''
        INSERT INTO pessoas (
            nome, cpf, telefone, cidade, bairro, data_nascimento,
            email, rede_social, observacoes, data_cadastro
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    _SQL_UPDATE_PESSOA = '''
        UPDATE pessoas SET
            nome=?, cpf=?, telefone=?, cidade=?, bairro=?,
            data_nascimento=?, email=?, rede_social=?,
            observacoes=?, data_atualizacao=?
        WHERE id=?
    '''
    
    @contextmanager
    def _get_connection(self):
        """Context manager para conexões"""
        conn = sqlite3.connect(
            self.db_name,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _ensure_db(self):
        """Cria estrutura do banco"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # Tabela pessoas
            cur.execute(self._SQL_CREATE_PESSOAS)
            
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
    
    # O cache explícito é removido daqui para usar @lru_cache nos métodos, se aplicável
    # Mantemos este método para limpar qualquer cache não-lru_cache ou forçar a atualização.
    def clear_cache(self):
        """Limpa cache de consultas (se houver)"""
        # Invalida o cache do método get_cidades (se decorado)
        self.get_cidades.cache_clear()
        logger.info("Cache de consultas limpo.")
    
    # ========== PESSOAS ==========
    def add_pessoa(self, pessoa: Dict) -> int:
        """Adiciona pessoa (dados já normalizados)"""
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(self._SQL_INSERT_PESSOA, (
                pessoa.get('nome'),
                pessoa.get('cpf'),
                pessoa.get('telefone'),
                pessoa.get('cidade'),
                pessoa.get('bairro'),
                pessoa.get('data_nascimento'),
                pessoa.get('email'),
                pessoa.get('rede_social'),
                pessoa.get('observacoes'),
                pessoa.get('data_cadastro')
            ))
            conn.commit()
            pessoa_id = cur.lastrowid
            
        # O DatabaseManager não chama clear_cache, o AppController fará isso
        return pessoa_id
    
    def update_pessoa(self, pessoa_id: int, pessoa: Dict) -> bool:
        """Atualiza pessoa (dados já normalizados)"""
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(self._SQL_UPDATE_PESSOA, (
                pessoa.get('nome'),
                pessoa.get('cpf'),
                pessoa.get('telefone'),
                pessoa.get('cidade'),
                pessoa.get('bairro'),
                pessoa.get('data_nascimento'),
                pessoa.get('email'),
                pessoa.get('rede_social'),
                pessoa.get('observacoes'),
                pessoa.get('data_atualizacao'),
                pessoa_id
            ))
            conn.commit()
            affected = cur.rowcount
        
        # O DatabaseManager não chama clear_cache, o AppController fará isso
        return affected > 0
    
    def delete_pessoa(self, pessoa_id: int, soft: bool = True) -> bool:
        """Exclui pessoa (soft delete por padrão)"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            if soft:
                cur.execute('UPDATE pessoas SET ativo=0 WHERE id=?', (pessoa_id,))
            else:
                cur.execute('DELETE FROM pessoas WHERE id=?', (pessoa_id,))
            conn.commit()
            affected = cur.rowcount
        
        # O DatabaseManager não chama clear_cache, o AppController fará isso
        logger.info(f"Pessoa {'desativada' if soft else 'excluída'}: ID {pessoa_id}")
        return affected > 0
    
    def search_pessoas(self, filters: Dict = None, only_active: bool = True) -> List[sqlite3.Row]:
        """Busca pessoas com filtros avançados"""
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            query = 'SELECT * FROM pessoas WHERE 1=1'
            params = []
            
            if only_active:
                query += ' AND ativo=1'
            
            if filters:
                if filters.get('nome'):
                    query += ' AND nome LIKE ?'
                    params.append(f"%{filters['nome']}%")
                
                if filters.get('cpf'):
                    # O CPF já deve ter vindo normalizado se o filtro veio da UI
                    cpf_normalizado = Utils.normalize_cpf(filters['cpf']) 
                    query += ' AND cpf LIKE ?'
                    params.append(f"%{cpf_normalizado}%")
                
                if filters.get('cidade'):
                    query += ' AND cidade LIKE ?'
                    params.append(f"%{filters['cidade']}%")
                
                if filters.get('mes_aniversario'):
                    query += ' AND substr(data_nascimento, 4, 2)=?'
                    params.append(filters['mes_aniversario'].zfill(2))
            
            query += ' ORDER BY nome'
            
            cur.execute(query, params)
            results = cur.fetchall()
        
        return results
    
    def cpf_exists(self, cpf: str, exclude_id: int = None) -> bool:
        """Verifica se CPF já existe (CPF deve ser normalizado antes de chamar)"""
        if not cpf:
            return False
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            if exclude_id:
                cur.execute('SELECT id FROM pessoas WHERE cpf=? AND id!=?', (cpf, exclude_id))
            else:
                cur.execute('SELECT id FROM pessoas WHERE cpf=?', (cpf,))
            return cur.fetchone() is not None
    
    def get_aniversariantes(self, mes: str = None) -> List[sqlite3.Row]:
        """Retorna aniversariantes do mês"""
        if not mes:
            mes = datetime.now().strftime('%m')
        
        mes = mes.zfill(2)
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT * FROM pessoas
                WHERE ativo=1
                AND data_nascimento IS NOT NULL
                AND data_nascimento != ''
                AND substr(data_nascimento, 4, 2) = ?
                ORDER BY substr(data_nascimento, 1, 2), nome
            ''', (mes,))
            return cur.fetchall()
    
    def get_pessoa_by_id(self, pessoa_id: int) -> Optional[sqlite3.Row]:
        """Retorna pessoa pelo ID"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM pessoas WHERE id=?', (pessoa_id,))
            return cur.fetchone()
    
    @lru_cache(maxsize=32) # Adição de cache para otimizar
    def get_cidades(self) -> List[str]:
        """Retorna lista de cidades cadastradas (cacheada)"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT DISTINCT cidade FROM pessoas
                WHERE ativo=1 AND cidade IS NOT NULL AND cidade != ''
                ORDER BY cidade
            ''')
            return [row[0] for row in cur.fetchall()]
    
    def get_duplicate_cpfs(self) -> List[str]:
        """Retorna CPFs duplicados"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT cpf FROM pessoas
                WHERE cpf IS NOT NULL AND cpf != '' AND ativo=1
                GROUP BY cpf HAVING COUNT(*) > 1
            ''')
            return [row[0] for row in cur.fetchall()]
    
    # ========== EVENTOS ==========
    def add_evento(self, evento: Dict) -> int:
        """Adiciona evento"""
        # Lógica de timestamp movida para AppController
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO eventos (
                    titulo, descricao, data_evento, tipo, local,
                    responsavel, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                evento.get('titulo'),
                evento.get('descricao'),
                evento.get('data_evento'),
                evento.get('tipo', 'geral'),
                evento.get('local'),
                evento.get('responsavel'),
                evento.get('criado_em')
            ))
            conn.commit()
            evento_id = cur.lastrowid
        
        logger.info(f"Evento criado: {evento.get('titulo')} (ID: {evento_id})")
        return evento_id
    
    def search_eventos(self, filters: Dict = None, only_active: bool = True) -> List[sqlite3.Row]:
        """Busca eventos"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            query = 'SELECT * FROM eventos WHERE 1=1'
            params = []
            
            if only_active:
                query += ' AND ativo=1'
            
            if filters:
                if filters.get('tipo'):
                    query += ' AND tipo=?'
                    params.append(filters['tipo'])
                
                if filters.get('data_inicio') and filters.get('data_fim'):
                    query += ''' AND date(
                        substr(data_evento,7,4)||'-'||
                        substr(data_evento,4,2)||'-'||
                        substr(data_evento,1,2)
                    ) BETWEEN date(?) AND date(?)'''
                    params.extend([filters['data_inicio'], filters['data_fim']])
            
            query += ''' ORDER BY
                substr(data_evento,7,4) DESC,
                substr(data_evento,4,2) DESC,
                substr(data_evento,1,2) DESC
            '''
            
            cur.execute(query, params)
            return cur.fetchall()
    
    # ========== CONFIG / BACKUP / STATS (sem alteração) ==========
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
        
    
    def _create_ui(self):
        """Cria interface"""
        # Header
        self._create_header()
        
        # Main container
        main = tk.Frame(self.root, bg=self.theme['bg'])
        main.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Notebook
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill='both', expand=True)
        
        # Tabs
        self._create_tab_cadastro()
        self._create_tab_consulta()
        self._create_tab_aniversariantes()
        self._create_tab_eventos()
        self._create_tab_relatorios()
        self._create_tab_configuracoes()
        self._create_tab_sobre()  # Adicione esta linha
        
        # Status bar
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side='bottom', fill='x')
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do sistema"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            stats = {}
            
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
            hoje = datetime.now()
            futuro = hoje + timedelta(days=30)
            cur.execute('''
                SELECT COUNT(*) as total FROM eventos
                WHERE ativo=1 AND date(
                    substr(data_evento,7,4)||'-'||
                    substr(data_evento,4,2)||'-'||
                    substr(data_evento,1,2)
                ) BETWEEN date(?) AND date(?)
            ''', (hoje.strftime('%Y-%m-%d'), futuro.strftime('%Y-%m-%d')))
            stats['eventos_proximos'] = cur.fetchone()['total']
            
            # Cidades
            cur.execute('''
                SELECT COUNT(DISTINCT cidade) as total FROM pessoas
                WHERE ativo=1 AND cidade IS NOT NULL AND cidade != ''
            ''')
            stats['total_cidades'] = cur.fetchone()['total']
            
            return stats

# ====================== BUSINESS LOGIC (CONTROLLER) ======================
class AppController:
    """Gerencia a lógica de negócios e orquestra o DatabaseManager"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    # --- PESSOAS ---
    def salvar_pessoa(self, pessoa: Dict, pessoa_id: Optional[int] = None) -> int:
        """Salva ou atualiza uma pessoa, incluindo validações de negócio e normalização."""
        
        # 1. Normalização de dados (ANTES de salvar)
        pessoa['cpf'] = Utils.normalize_cpf(pessoa.get('cpf', ''))
        pessoa['telefone'] = Utils.normalize_phone(pessoa.get('telefone', ''))
        
        # 2. Validação de Negócio: CPF duplicado
        if pessoa.get('cpf') and self.db.cpf_exists(pessoa['cpf'], pessoa_id):
            raise ValueError('CPF já cadastrado para outra pessoa!')
            
        # 3. Escolha da Ação (Salvar ou Atualizar)
        if pessoa_id:
            pessoa['data_atualizacao'] = datetime.now().strftime(Config.DATETIME_FORMAT)
            success = self.db.update_pessoa(pessoa_id, pessoa)
            if not success:
                raise Exception('Falha ao atualizar a pessoa no banco de dados.')
            result_id = pessoa_id
            logger.info(f"Pessoa atualizada: ID {pessoa_id}")
        else:
            pessoa['data_cadastro'] = datetime.now().strftime(Config.DATETIME_FORMAT)
            result_id = self.db.add_pessoa(pessoa)
            logger.info(f"Pessoa cadastrada: {pessoa.get('nome')} (ID: {result_id})")
        
        # 4. Limpeza de cache após alterações de escrita
        self.db.clear_cache()
        return result_id

    def excluir_pessoa(self, pessoa_id: int, nome: str) -> bool:
        """Exclui (soft delete) uma pessoa e limpa o cache."""
        success = self.db.delete_pessoa(pessoa_id)
        if success:
            self.db.clear_cache()
        return success
    
    # --- EVENTOS ---
    def salvar_evento(self, evento: Dict) -> int:
        """Salva um novo evento com timestamp."""
        evento['criado_em'] = datetime.now().strftime(Config.DATETIME_FORMAT)
        return self.db.add_evento(evento)
    
    # --- INTEGRIDADE ---
    def verificar_integridade(self) -> Dict:
        """Executa verificações de integridade de dados."""
        
        cpf_duplicados = self.db.get_duplicate_cpfs()
        
        # Exemplo de verificação de consistência (pode ser expandido)
        pessoas_total = len(self.db.search_pessoas(only_active=False))
        eventos_total = len(self.db.search_eventos(only_active=False))
        
        return {
            'pessoas_total': pessoas_total,
            'eventos_total': eventos_total,
            'cpfs_duplicados': cpf_duplicados
        }

# ====================== REPORTS (sem alteração) ======================
class ReportGenerator:
    """Gerador de relatórios"""
    # ... (Os métodos ReportGenerator.export_html, export_aniversariantes_html, export_csv permanecem inalterados) ...
    @staticmethod
    def export_html(pessoas: List, eventos: List, filepath: str, title: str = "Relatório IBVRD") -> str:
        """Exporta relatório HTML"""
        html = ['<!DOCTYPE html>']
        html.append('<html lang="pt-BR">')
        html.append('<head>')
        html.append('<meta charset="utf-8">')
        html.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
        html.append(f'<title>{title}</title>')
        html.append('<style>')
        html.append('''
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                padding: 20px;
                background: #f5f5f5;
                color: #333;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
                margin-bottom: 10px;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            .meta {
                color: #7f8c8d;
                margin-bottom: 30px;
                font-size: 14px;
            }
            h2 {
                color: #34495e;
                margin: 30px 0 15px 0;
                padding: 10px;
                background: #ecf0f1;
                border-left: 4px solid #3498db;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 30px;
                background: white;
            }
            th {
                background: #3498db;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
            }
            td {
                padding: 10px 12px;
                border-bottom: 1px solid #ecf0f1;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .empty {
                padding: 20px;
                text-align: center;
                color: #95a5a6;
                font-style: italic;
            }
            @media print {
                body { background: white; }
                .container { box-shadow: none; }
            }
        ''')
        html.append('</style>')
        html.append('</head>')
        html.append('<body>')
        html.append('<div class="container">')
        
        html.append(f'<h1>{title}</h1>')
        html.append(f'<div class="meta">Gerado em {datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}</div>')
        
        # Pessoas
        html.append('<h2>Pessoas Cadastradas</h2>')
        if pessoas:
            html.append('<table>')
            html.append('<thead><tr>')
            html.append('<th>ID</th><th>Nome</th><th>CPF</th><th>Telefone</th>')
            html.append('<th>Cidade</th><th>Nascimento</th><th>E-mail</th>')
            html.append('</tr></thead>')
            html.append('<tbody>')
            
            for p in pessoas:
                cpf = Utils.format_cpf(Utils.safe_get(p, 'cpf'))
                tel = Utils.format_phone(Utils.safe_get(p, 'telefone'))
                html.append(f'<tr>')
                html.append(f'<td>{Utils.safe_get(p, "id")}</td>')
                html.append(f'<td>{Utils.safe_get(p, "nome")}</td>')
                html.append(f'<td>{cpf}</td>')
                html.append(f'<td>{tel}</td>')
                html.append(f'<td>{Utils.safe_get(p, "cidade")}</td>')
                html.append(f'<td>{Utils.safe_get(p, "data_nascimento")}</td>')
                html.append(f'<td>{Utils.safe_get(p, "email")}</td>')
                html.append(f'</tr>')
            
            html.append('</tbody></table>')
        else:
            html.append('<div class="empty">Nenhuma pessoa para exibir</div>')
        
        # Eventos
        html.append('<h2>Eventos / Agenda</h2>')
        if eventos:
            html.append('<table>')
            html.append('<thead><tr>')
            html.append('<th>ID</th><th>Título</th><th>Data</th><th>Tipo</th>')
            html.append('<th>Local</th><th>Responsável</th>')
            html.append('</tr></thead>')
            html.append('<tbody>')
            
            for e in eventos:
                html.append(f'<tr>')
                html.append(f'<td>{Utils.safe_get(e, "id")}</td>')
                html.append(f'<td>{Utils.safe_get(e, "titulo")}</td>')
                html.append(f'<td>{Utils.safe_get(e, "data_evento")}</td>')
                html.append(f'<td>{Utils.safe_get(e, "tipo")}</td>')
                html.append(f'<td>{Utils.safe_get(e, "local")}</td>')
                html.append(f'<td>{Utils.safe_get(e, "responsavel")}</td>')
                html.append(f'</tr>')
            
            html.append('</tbody></table>')
        else:
            html.append('<div class="empty">Nenhum evento para exibir</div>')
        
        html.append('</div>')
        html.append('</body>')
        html.append('</html>')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html))
        
        logger.info(f'Relatório HTML gerado: {filepath}')
        return filepath
    
    @staticmethod
    def export_aniversariantes_html(pessoas: List, filepath: str, mes: str) -> str:
        """Exporta relatório de aniversariantes em HTML"""
        html = ['<!DOCTYPE html>']
        html.append('<html lang="pt-BR">')
        html.append('<head>')
        html.append('<meta charset="utf-8">')
        html.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
        html.append(f'<title>Aniversariantes do Mês {mes}</title>')
        html.append('<style>')
        html.append('''
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                padding: 20px;
                background: #f5f5f5;
                color: #333;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
                margin-bottom: 10px;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            .meta {
                color: #7f8c8d;
                margin-bottom: 30px;
                font-size: 14px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 30px;
                background: white;
            }
            th {
                background: #3498db;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
            }
            td {
                padding: 10px 12px;
                border-bottom: 1px solid #ecf0f1;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .empty {
                padding: 20px;
                text-align: center;
                color: #95a5a6;
                font-style: italic;
            }
            @media print {
                body { background: white; }
                .container { box-shadow: none; }
            }
        ''')
        html.append('</style>')
        html.append('</head>')
        html.append('<body>')
        html.append('<div class="container">')
        
        html.append(f'<h1>Aniversariantes do Mês {mes}</h1>')
        html.append(f'<div class="meta">Gerado em {datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}</div>')
        
        if pessoas:
            html.append('<table>')
            html.append('<thead><tr>')
            html.append('<th>ID</th><th>Nome</th><th>Data de Nascimento</th><th>Idade</th>')
            html.append('<th>Telefone</th><th>E-mail</th><th>Cidade</th>')
            html.append('</tr></thead>')
            html.append('<tbody>')
            
            for p in pessoas:
                data_nasc = Utils.safe_get(p, 'data_nascimento')
                idade = Utils.calculate_age(data_nasc) if data_nasc else ''
                tel = Utils.format_phone(Utils.safe_get(p, 'telefone'))
                
                html.append(f'<tr>')
                html.append(f'<td>{Utils.safe_get(p, "id")}</td>')
                html.append(f'<td>{Utils.safe_get(p, "nome")}</td>')
                html.append(f'<td>{data_nasc}</td>')
                html.append(f'<td>{idade} anos</td>' if idade else f'<td></td>')
                html.append(f'<td>{tel}</td>')
                html.append(f'<td>{Utils.safe_get(p, "email")}</td>')
                html.append(f'<td>{Utils.safe_get(p, "cidade")}</td>')
                html.append(f'</tr>')
            
            html.append('</tbody></table>')
        else:
            html.append('<div class="empty">Nenhum aniversariante para exibir</div>')
        
        html.append('</div>')
        html.append('</body>')
        html.append('</html>')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html))
        
        logger.info(f'Relatório de aniversariantes gerado: {filepath}')
        return filepath
    
    @staticmethod
    def export_csv(pessoas: List, filepath: str) -> str:
        """Exporta relatório CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            
            headers = [
                'ID', 'Nome', 'CPF', 'Telefone', 'Cidade', 'Bairro',
                'Data Nascimento', 'E-mail', 'Rede Social', 'Data Cadastro'
            ]
            writer.writerow(headers)
            
            for p in pessoas:
                writer.writerow([
                    Utils.safe_get(p, 'id'),
                    Utils.safe_get(p, 'nome'),
                    Utils.safe_get(p, 'cpf'),
                    Utils.safe_get(p, 'telefone'),
                    Utils.safe_get(p, 'cidade'),
                    Utils.safe_get(p, 'bairro'),
                    Utils.safe_get(p, 'data_nascimento'),
                    Utils.safe_get(p, 'email'),
                    Utils.safe_get(p, 'rede_social'),
                    Utils.safe_get(p, 'data_cadastro')
                ])
        
        logger.info(f'Relatório CSV gerado: {filepath}')
        return filepath

# ====================== UI COMPONENTS (sem alteração) ======================
class ValidatedEntry(tk.Entry):
    """Entry com validação em tempo real"""
    
    def __init__(self, master, validator=None, on_valid=None, on_invalid=None, **kwargs):
        super().__init__(master, **kwargs)
        self.validator = validator
        self.on_valid = on_valid
        self.on_invalid = on_invalid
        self._original_bg = self.cget('bg')
        
        self.bind('<KeyRelease>', self._validate)
        self.bind('<FocusOut>', self._validate)
    
    def _validate(self, event=None):
        """Valida conteúdo"""
        if not self.validator:
            return True
        
        value = self.get().strip()
        if not value:
            self.config(bg=self._original_bg)
            return True
        
        is_valid = self.validator(value)
        
        if is_valid:
            self.config(bg='#d4edda')
            if self.on_valid:
                self.on_valid(value)
        else:
            self.config(bg='#f8d7da')
            if self.on_invalid:
                self.on_invalid(value)
        
        return is_valid
    
    def reset(self):
        """Reseta validação"""
        self.config(bg=self._original_bg)

class SearchBar(tk.Frame):
    """Barra de busca avançada"""
    
    def __init__(self, master, on_search, **kwargs):
        super().__init__(master, **kwargs)
        self.on_search = on_search
        
        tk.Label(self, text='Buscar:', font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 5))
        
        self.entry = tk.Entry(self, width=40, font=('Arial', 10))
        self.entry.pack(side='left', padx=5)
        self.entry.bind('<KeyRelease>', lambda e: self._do_search())
        
        tk.Button(
            self, 
            text='🔍',
            command=self._do_search,
            width=3
        ).pack(side='left', padx=2)
        
        tk.Button(
            self,
            text='✕',
            command=self._clear,
            width=3
        ).pack(side='left', padx=2)
    
    def _do_search(self):
        """Executa busca"""
        if self.on_search:
            self.on_search(self.entry.get().strip())
    
    def _clear(self):
        """Limpa busca"""
        self.entry.delete(0, 'end')
        self._do_search()
    
    def get(self):
        """Retorna texto da busca"""
        return self.entry.get().strip()

class StatusBar(tk.Frame):
    """Barra de status melhorada"""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, relief=tk.SUNKEN, bd=1, **kwargs)
        
        self.label = tk.Label(self, text='Pronto', anchor='w')
        self.label.pack(side='left', fill='x', expand=True, padx=5)
        
        self.stats_label = tk.Label(self, text='', anchor='e')
        self.stats_label.pack(side='right', padx=5)
    
    def set_message(self, message: str, duration: int = 3000):
        """Define mensagem temporária"""
        self.label.config(text=message)
        if duration > 0:
            self.after(duration, lambda: self.set_message('Pronto', 0))
    
    def set_stats(self, stats: str):
        """Define estatísticas"""
        self.stats_label.config(text=stats)

# ====================== MAIN APPLICATION (VIEW) ======================
class IBVRDApp:
    """Aplicação principal (View e Controller de UI)"""
    
    def __init__(self, root):
        self.root = root
        self.db = DatabaseManager()
        self.controller = AppController(self.db) # Novo Controller de Negócios
        self.current_pessoa_id = None
        
        self._setup_window()
        self._setup_theme()
        self._create_ui()
        self._load_initial_data()
        self._check_auto_backup()
        self._create_tab_sobre()  # Adicione esta linha

        # Tratamento de exceções
        sys.excepthook = self._handle_exception
        
        logger.info(f'{Config.APP_NAME} v{Config.VERSION} iniciado')
    
    # --- SETUP & UI (mantido) ---
    def _setup_window(self):
        """Configura janela principal"""
        self.root.title(f'{Config.APP_NAME} v{Config.VERSION}')
        self.root.geometry(f'{Config.WINDOW_WIDTH}x{Config.WINDOW_HEIGHT}')
        self.root.minsize(Config.MIN_WIDTH, Config.MIN_HEIGHT)
        
        # Centraliza janela
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (Config.WINDOW_WIDTH // 2)
        y = (self.root.winfo_screenheight() // 2) - (Config.WINDOW_HEIGHT // 2)
        self.root.geometry(f'+{x}+{y}')
    
    def _setup_theme(self):
        """Configura tema"""
        self.current_theme = 'claro'
        self.theme = Config.THEMES[self.current_theme]
        
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except:
            pass
        
        self._apply_theme()
    
    def _apply_theme(self):
        """Aplica tema atual"""
        theme = Config.THEMES[self.current_theme]
        
        self.root.configure(bg=theme['bg'])
        
        # Configurar ttk styles
        self.style.configure('TNotebook', background=theme['bg'])
        self.style.configure('TNotebook.Tab', padding=[10, 5])
        self.style.configure('TFrame', background=theme['bg'])
        self.style.configure('TLabel', background=theme['bg'], foreground=theme['fg'])
        self.style.configure('TButton', padding=6)
    
    def _create_ui(self):
        """Cria interface"""
        # Header
        self._create_header()
        
        # Main container
        main = tk.Frame(self.root, bg=self.theme['bg'])
        main.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Notebook
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill='both', expand=True)
        
        # Tabs
        self._create_tab_cadastro()
        self._create_tab_consulta()
        self._create_tab_aniversariantes()
        self._create_tab_eventos()
        self._create_tab_relatorios()
        self._create_tab_configuracoes()
        
        # Status bar
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side='bottom', fill='x')
    
    def _create_header(self):
        """Cria cabeçalho"""
        header = tk.Frame(self.root, bg=self.theme['title_bg'], height=80)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        title = tk.Label(
            header,
            text='IBVRD - Igreja Batista Vida no Reino de Deus',
            font=('Arial', 18, 'bold'),
            bg=self.theme['title_bg'],
            fg=self.theme['title_fg']
        )
        title.pack(pady=10)
        
        subtitle = tk.Label(
            header,
            text=f'Sistema de Cadastro v{Config.VERSION}',
            font=('Arial', 10),
            bg=self.theme['title_bg'],
            fg=self.theme['title_fg']
        )
        subtitle.pack()
    
    def _create_tab_cadastro(self):
        """Cria aba de cadastro"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text='📝 Cadastro')
        
        # Form container
        form_frame = tk.LabelFrame(
            tab,
            text='Dados da Pessoa',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=20
        )
        form_frame.pack(fill='x', padx=10, pady=10)
        
        self.entries = {}
        
        # Nome
        row = 0
        tk.Label(form_frame, text='Nome *', font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky='w', pady=5
        )
        self.entries['nome'] = tk.Entry(form_frame, width=50, font=('Arial', 10))
        self.entries['nome'].grid(row=row, column=1, columnspan=3, sticky='ew', pady=5)
        
        # CPF
        row += 1
        tk.Label(form_frame, text='CPF', font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        self.entries['cpf'] = ValidatedEntry(
            form_frame,
            width=25,
            font=('Arial', 10),
            validator=Utils.validate_cpf
        )
        self.entries['cpf'].grid(row=row, column=1, sticky='w', pady=5, padx=(0, 10))
        self.entries['cpf'].bind('<KeyRelease>', lambda e: self._format_cpf())
        
        # Telefone
        tk.Label(form_frame, text='Telefone', font=('Arial', 10)).grid(
            row=row, column=2, sticky='w', pady=5
        )
        self.entries['telefone'] = tk.Entry(form_frame, width=25, font=('Arial', 10))
        self.entries['telefone'].grid(row=row, column=3, sticky='w', pady=5)
        self.entries['telefone'].bind('<KeyRelease>', lambda e: self._format_phone())
        
        # Cidade
        row += 1
        tk.Label(form_frame, text='Cidade', font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        self.entries['cidade'] = tk.Entry(form_frame, width=25, font=('Arial', 10))
        self.entries['cidade'].grid(row=row, column=1, sticky='w', pady=5, padx=(0, 10))
        
        # Bairro
        tk.Label(form_frame, text='Bairro', font=('Arial', 10)).grid(
            row=row, column=2, sticky='w', pady=5
        )
        self.entries['bairro'] = tk.Entry(form_frame, width=25, font=('Arial', 10))
        self.entries['bairro'].grid(row=row, column=3, sticky='w', pady=5)
        
        # Data Nascimento
        row += 1
        tk.Label(form_frame, text='Data Nasc.', font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        self.entries['data_nascimento'] = ValidatedEntry(
            form_frame,
            width=25,
            font=('Arial', 10),
            validator=Utils.validate_date
        )
        self.entries['data_nascimento'].grid(row=row, column=1, sticky='w', pady=5, padx=(0, 10))
        self.entries['data_nascimento'].bind('<KeyRelease>', lambda e: self._format_date())
        tk.Label(form_frame, text='(DD/MM/AAAA)', font=('Arial', 8), fg='gray').grid(
            row=row, column=1, sticky='e', pady=5
        )
        
        # Email
        tk.Label(form_frame, text='E-mail', font=('Arial', 10)).grid(
            row=row, column=2, sticky='w', pady=5
        )
        self.entries['email'] = ValidatedEntry(
            form_frame,
            width=25,
            font=('Arial', 10),
            validator=Utils.validate_email
        )
        self.entries['email'].grid(row=row, column=3, sticky='w', pady=5)
        
        # Rede Social
        row += 1
        tk.Label(form_frame, text='Rede Social', font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        self.entries['rede_social'] = tk.Entry(form_frame, width=50, font=('Arial', 10))
        self.entries['rede_social'].grid(row=row, column=1, columnspan=3, sticky='ew', pady=5)
        
        # Observações
        row += 1
        tk.Label(form_frame, text='Observações', font=('Arial', 10)).grid(
            row=row, column=0, sticky='nw', pady=5
        )
        self.entries['observacoes'] = tk.Text(form_frame, width=50, height=4, font=('Arial', 10))
        self.entries['observacoes'].grid(row=row, column=1, columnspan=3, sticky='ew', pady=5)
        
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)
        
        # Botões
        btn_frame = tk.Frame(tab)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        buttons = [
            ('💾 Salvar', self._save_pessoa, self.theme['success']),
            ('🔄 Atualizar', self._update_pessoa, self.theme['button_bg']),
            ('🗑️ Excluir', self._delete_pessoa, self.theme['error']),
            ('✨ Limpar', self._clear_form, self.theme['fg'])
        ]
        
        for text, cmd, color in buttons:
            btn = tk.Button(
                btn_frame,
                text=text,
                command=cmd,
                bg=color,
                fg='white',
                font=('Arial', 10, 'bold'),
                width=15,
                height=2,
                cursor='hand2'
            )
            btn.pack(side='left', padx=5)
    
    def _create_tab_consulta(self):
        """Cria aba de consulta"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text='🔍 Consulta')
        
        # Barra de busca
        search_frame = tk.Frame(tab)
        search_frame.pack(fill='x', padx=10, pady=10)
        
        self.search_bar = SearchBar(search_frame, on_search=self._search_pessoas)
        self.search_bar.pack(fill='x')
        
        # Filtros adicionais
        filter_frame = tk.LabelFrame(tab, text='Filtros Avançados', padx=10, pady=10)
        filter_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        tk.Label(filter_frame, text='Cidade:').grid(row=0, column=0, sticky='w', padx=5)
        self.filter_cidade = ttk.Combobox(filter_frame, width=20, state='readonly')
        self.filter_cidade.grid(row=0, column=1, padx=5)
        self.filter_cidade.bind('<<ComboboxSelected>>', lambda e: self._search_pessoas())
        
        tk.Button(
            filter_frame,
            text='Limpar Filtros',
            command=self._clear_filters
        ).grid(row=0, column=2, padx=10)
        
        # Treeview
        tree_frame = tk.LabelFrame(tab, text='Pessoas Cadastradas', padx=5, pady=5)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical')
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal')
        
        columns = ('ID', 'Nome', 'CPF', 'Telefone', 'Cidade', 'Bairro', 'Nascimento', 'Email')
        self.tree_pessoas = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        
        vsb.config(command=self.tree_pessoas.yview)
        hsb.config(command=self.tree_pessoas.xview)
        
        # Configurar colunas
        widths = {'ID': 50, 'Nome': 200, 'CPF': 120, 'Telefone': 120, 
                  'Cidade': 120, 'Bairro': 120, 'Nascimento': 100, 'Email': 180}
        
        for col in columns:
            self.tree_pessoas.heading(col, text=col, command=lambda c=col: self._sort_tree(c))
            self.tree_pessoas.column(col, width=widths.get(col, 100))
        
        self.tree_pessoas.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        
        self.tree_pessoas.bind('<<TreeviewSelect>>', self._on_pessoa_select)
        self.tree_pessoas.bind('<Double-1>', lambda e: self._edit_selected_pessoa())
    
    def _create_tab_aniversariantes(self):
        """Cria aba de aniversariantes"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text='🎂 Aniversariantes')
        
        # Controles
        ctrl_frame = tk.Frame(tab)
        ctrl_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(ctrl_frame, text='Mês:', font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        
        self.mes_var = tk.StringVar(value=datetime.now().strftime('%m'))
        mes_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.mes_var,
            values=[f'{i:02d}' for i in range(1, 13)],
            width=5,
            state='readonly'
        )
        mes_combo.pack(side='left', padx=5)
        mes_combo.bind('<<ComboboxSelected>>', lambda e: self._load_aniversariantes())
        
        tk.Button(
            ctrl_frame,
            text='🔄 Atualizar',
            command=self._load_aniversariantes
        ).pack(side='left', padx=5)
        
        tk.Button(
            ctrl_frame,
            text='📄 Exportar HTML',
            command=self._export_aniversariantes
        ).pack(side='right', padx=5)
        
        # Treeview
        tree_frame = tk.LabelFrame(tab, text='Aniversariantes do Mês', padx=5, pady=5)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        vsb = ttk.Scrollbar(tree_frame, orient='vertical')
        
        columns = ('ID', 'Nome', 'Data/Idade', 'Telefone', 'Email', 'Cidade')
        self.tree_aniversariantes = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            yscrollcommand=vsb.set
        )
        
        vsb.config(command=self.tree_aniversariantes.yview)
        
        for col in columns:
            self.tree_aniversariantes.heading(col, text=col)
            self.tree_aniversariantes.column(col, width=150)
        
        self.tree_aniversariantes.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
    
    def _create_tab_eventos(self):
        """Cria aba de eventos"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text='📅 Eventos')
        
        # Form
        form_frame = tk.LabelFrame(tab, text='Novo Evento', padx=15, pady=15)
        form_frame.pack(fill='x', padx=10, pady=10)
        
        self.evento_entries = {}
        
        # Título
        tk.Label(form_frame, text='Título *').grid(row=0, column=0, sticky='w', pady=5)
        self.evento_entries['titulo'] = tk.Entry(form_frame, width=50)
        self.evento_entries['titulo'].grid(row=0, column=1, columnspan=3, sticky='ew', pady=5)
        
        # Data
        tk.Label(form_frame, text='Data *').grid(row=1, column=0, sticky='w', pady=5)
        self.evento_entries['data_evento'] = tk.Entry(form_frame, width=20)
        self.evento_entries['data_evento'].grid(row=1, column=1, sticky='w', pady=5)
        
        # Tipo
        tk.Label(form_frame, text='Tipo').grid(row=1, column=2, sticky='w', pady=5, padx=(20,0))
        self.evento_entries['tipo'] = ttk.Combobox(
            form_frame,
            values=['geral', 'culto', 'aniversario', 'comemorativo', 'reuniao'],
            width=18,
            state='readonly'
        )
        self.evento_entries['tipo'].current(0)
        self.evento_entries['tipo'].grid(row=1, column=3, sticky='w', pady=5)
        
        # Local
        tk.Label(form_frame, text='Local').grid(row=2, column=0, sticky='w', pady=5)
        self.evento_entries['local'] = tk.Entry(form_frame, width=30)
        self.evento_entries['local'].grid(row=2, column=1, sticky='ew', pady=5)
        
        # Responsável
        tk.Label(form_frame, text='Responsável').grid(row=2, column=2, sticky='w', pady=5, padx=(20,0))
        self.evento_entries['responsavel'] = tk.Entry(form_frame, width=30)
        self.evento_entries['responsavel'].grid(row=2, column=3, sticky='ew', pady=5)
        
        # Descrição
        tk.Label(form_frame, text='Descrição').grid(row=3, column=0, sticky='nw', pady=5)
        self.evento_entries['descricao'] = tk.Text(form_frame, width=50, height=4)
        self.evento_entries['descricao'].grid(row=3, column=1, columnspan=3, sticky='ew', pady=5)
        
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)
        
        # Botão salvar
        tk.Button(
            form_frame,
            text='💾 Adicionar Evento',
            command=self._save_evento,
            bg=self.theme['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            height=2
        ).grid(row=4, column=0, columnspan=4, pady=10, sticky='ew')
        
        # Lista de eventos
        tree_frame = tk.LabelFrame(tab, text='Próximos Eventos', padx=5, pady=5)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        vsb = ttk.Scrollbar(tree_frame, orient='vertical')
        
        columns = ('ID', 'Título', 'Data', 'Tipo', 'Local', 'Responsável')
        self.tree_eventos = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            yscrollcommand=vsb.set
        )
        
        vsb.config(command=self.tree_eventos.yview)
        
        for col in columns:
            self.tree_eventos.heading(col, text=col)
            self.tree_eventos.column(col, width=150)
        
        self.tree_eventos.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
    
    def _create_tab_relatorios(self):
        """Cria aba de relatórios"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text='📊 Relatórios')
        
        # Estatísticas
        stats_frame = tk.LabelFrame(tab, text='Estatísticas Gerais', padx=20, pady=20)
        stats_frame.pack(fill='x', padx=10, pady=10)
        
        self.stats_labels = {}
        stats_items = [
            ('total_pessoas', 'Total de Pessoas'),
            ('aniversariantes_mes', 'Aniversariantes Este Mês'),
            ('total_eventos', 'Total de Eventos'),
            ('eventos_proximos', 'Eventos Próximos (30 dias)'),
            ('total_cidades', 'Cidades Cadastradas')
        ]
        
        for i, (key, label) in enumerate(stats_items):
            row = i // 2
            col = (i % 2) * 2
            
            tk.Label(
                stats_frame,
                text=f'{label}:',
                font=('Arial', 10)
            ).grid(row=row, column=col, sticky='w', padx=10, pady=5)
            
            self.stats_labels[key] = tk.Label(
                stats_frame,
                text='0',
                font=('Arial', 12, 'bold'),
                fg=self.theme['button_bg']
            )
            self.stats_labels[key].grid(row=row, column=col+1, sticky='w', padx=10, pady=5)
        
        # Exportação
        export_frame = tk.LabelFrame(tab, text='Exportar Dados', padx=20, pady=20)
        export_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(export_frame, text='Selecione o formato:', font=('Arial', 10)).pack(anchor='w', pady=5)
        
        export_buttons = [
            ('📄 Exportar HTML Completo', lambda: self._export_html('completo')),
            ('📄 Exportar HTML Aniversariantes', self._export_aniversariantes),
            ('📊 Exportar CSV', self._export_csv),
            ('💾 Criar Backup do Banco', self._create_backup)
        ]
        
        for text, cmd in export_buttons:
            tk.Button(
                export_frame,
                text=text,
                command=cmd,
                width=30,
                height=2
            ).pack(pady=5)
    
    def _create_tab_configuracoes(self):
        """Cria aba de configurações"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text='⚙️ Configurações')
        
        # Tema
        theme_frame = tk.LabelFrame(tab, text='Aparência', padx=20, pady=20)
        theme_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(theme_frame, text='Tema:', font=('Arial', 10)).pack(anchor='w', pady=5)
        
        theme_buttons = tk.Frame(theme_frame)
        theme_buttons.pack(fill='x', pady=5)
        
        tk.Button(
            theme_buttons,
            text='☀️ Claro',
            command=lambda: self._change_theme('claro'),
            width=15
        ).pack(side='left', padx=5)
        
        tk.Button(
            theme_buttons,
            text='🌙 Escuro',
            command=lambda: self._change_theme('escuro'),
            width=15
        ).pack(side='left', padx=5)
        
        # Banco de dados
        db_frame = tk.LabelFrame(tab, text='Banco de Dados', padx=20, pady=20)
        db_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(
            db_frame,
            text='💾 Criar Backup',
            command=self._create_backup,
            width=20
        ).pack(side='left', padx=5, pady=5)
        
        tk.Button(
            db_frame,
            text='🔄 Restaurar Backup',
            command=self._restore_backup,
            width=20
        ).pack(side='left', padx=5, pady=5)
        
        # Sistema
        sys_frame = tk.LabelFrame(tab, text='Sistema', padx=20, pady=20)
        sys_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(
            sys_frame,
            text='🔍 Verificar Integridade',
            command=self._check_integrity,
            width=20
        ).pack(side='left', padx=5, pady=5)
        
        tk.Button(
            sys_frame,
            text='🧹 Limpar Cache',
            command=self._clear_cache,
            width=20
        ).pack(side='left', padx=5, pady=5)

    def _create_tab_sobre(self):
        """Cria aba Sobre com informações do criador"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text='ℹ️ Sobre')
        
        # Container principal
        main_frame = tk.Frame(tab, bg=self.theme['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Título
        title_label = tk.Label(
            main_frame,
            text='Sobre o Sistema',
            font=('Arial', 16, 'bold'),
            bg=self.theme['bg'],
            fg=self.theme['fg']
        )
        title_label.pack(pady=(10, 20))
        
        # Frame para informações do criador
        creator_frame = tk.LabelFrame(
            main_frame,
            text='Desenvolvedor',
            font=('Arial', 12, 'bold'),
            padx=20,
            pady=20
        )
        creator_frame.pack(fill='x', pady=10)
        
        # Informações do criador
        info_text = """
        Nome: Hugo Enrique Wenner
        Contato: hugowenner5@gmail.com - (31) 997183-6063
        Função: Desenvolvedor do Sistema
        
        Este sistema foi desenvolvido para a Igreja Batista 
        Vida no Reino de Deus (IBVRD) com o objetivo de 
        facilitar o cadastro e gestão de membros e eventos.
        """
        
        info_label = tk.Label(
            creator_frame,
            text=info_text,
            font=('Arial', 11),
            bg=self.theme['bg'],
            fg=self.theme['fg'],
            justify='left'
        )
        info_label.pack(anchor='w')
        
        # Frame para informações do sistema
        system_frame = tk.LabelFrame(
            main_frame,
            text='Informações do Sistema',
            font=('Arial', 12, 'bold'),
            padx=20,
            pady=20
        )
        system_frame.pack(fill='x', pady=10)
        
        # Informações do sistema
        system_info = f"""
        Nome: {Config.APP_NAME}
        Versão: {Config.VERSION}
        Tecnologia: Python com Tkinter
        Banco de Dados: SQLite
        
        Sistema desenvolvido com foco em:
        - Facilidade de uso
        - Organização de dados
        - Relatórios detalhados
        - Gestão de eventos
        """
        
        system_label = tk.Label(
            system_frame,
            text=system_info,
            font=('Arial', 11),
            bg=self.theme['bg'],
            fg=self.theme['fg'],
            justify='left'
        )
        system_label.pack(anchor='w')
        
        # Frame para direitos autorais
        copyright_frame = tk.Frame(main_frame, bg=self.theme['bg'])
        copyright_frame.pack(side='bottom', fill='x', pady=20)
        
        copyright_text = f"© {datetime.now().year} - [Seu Nome] - Todos os direitos reservados"
        
        copyright_label = tk.Label(
            copyright_frame,
            text=copyright_text,
            font=('Arial', 9),
            bg=self.theme['bg'],
            fg=self.theme['fg']
        )
        copyright_label.pack()
    
    # --- LOAD & UI UPDATE (mantido) ---
    def _load_initial_data(self):
        """Carrega dados iniciais"""
        self._load_pessoas()
        self._load_eventos()
        self._load_aniversariantes()
        self._load_cidades()
        self._update_statistics()
    
    def _load_pessoas(self):
        """Carrega pessoas na treeview"""
        for item in self.tree_pessoas.get_children():
            self.tree_pessoas.delete(item)
        
        # Usa o search_pessoas do DB (que não usa cache, pois a busca é dinâmica)
        pessoas = self.db.search_pessoas() 
        
        for p in pessoas:
            self.tree_pessoas.insert('', 'end', values=(
                p['id'],
                p['nome'],
                Utils.format_cpf(p['cpf']),
                Utils.format_phone(p['telefone']),
                p['cidade'],
                p['bairro'],
                p['data_nascimento'],
                p['email']
            ))
        
        self.status_bar.set_stats(f'Total: {len(pessoas)} pessoas')
    
    def _load_eventos(self):
        """Carrega eventos na treeview"""
        for item in self.tree_eventos.get_children():
            self.tree_eventos.delete(item)
        
        eventos = self.db.search_eventos()
        
        for e in eventos:
            self.tree_eventos.insert('', 'end', values=(
                e['id'],
                e['titulo'],
                e['data_evento'],
                e['tipo'],
                e['local'],
                e['responsavel']
            ))
    
    def _load_aniversariantes(self):
        """Carrega aniversariantes na treeview"""
        for item in self.tree_aniversariantes.get_children():
            self.tree_aniversariantes.delete(item)
        
        mes = self.mes_var.get()
        aniversariantes = self.db.get_aniversariantes(mes)
        
        for p in aniversariantes:
            data_idade = Utils.format_date_with_age(p['data_nascimento'])
            self.tree_aniversariantes.insert('', 'end', values=(
                p['id'],
                p['nome'],
                data_idade,
                Utils.format_phone(p['telefone']),
                p['email'],
                p['cidade']
            ))
    
    def _load_cidades(self):
        """Carrega cidades no combobox (método get_cidades está cacheado)"""
        cidades = self.db.get_cidades()
        self.filter_cidade['values'] = [''] + cidades
    
    def _update_statistics(self):
        """Atualiza estatísticas"""
        stats = self.db.get_statistics()
        
        for key, label in self.stats_labels.items():
            label.config(text=str(stats.get(key, 0)))
    
    # --- FORM & ACTIONS (Refatorados) ---

    def _get_form_data(self) -> Dict:
        """Coleta dados do formulário de pessoa."""
        return {
            'nome': self.entries['nome'].get().strip(),
            'cpf': self.entries['cpf'].get().strip(),
            'telefone': self.entries['telefone'].get().strip(),
            'cidade': self.entries['cidade'].get().strip(),
            'bairro': self.entries['bairro'].get().strip(),
            'data_nascimento': self.entries['data_nascimento'].get().strip(),
            'email': self.entries['email'].get().strip(),
            'rede_social': self.entries['rede_social'].get().strip(),
            'observacoes': self.entries['observacoes'].get('1.0', 'end').strip()
        }

    def _validate_form(self) -> bool:
        """Valida formulário (Validações de UI)"""
        data = self._get_form_data()
        
        if not data['nome']:
            messagebox.showerror('Erro', 'O nome é obrigatório!')
            return False
        
        if data['cpf'] and not Utils.validate_cpf(data['cpf']):
            messagebox.showerror('Erro', 'CPF inválido!')
            return False
        
        if data['email'] and not Utils.validate_email(data['email']):
            messagebox.showerror('Erro', 'E-mail inválido!')
            return False
        
        if data['data_nascimento'] and not Utils.validate_date(data['data_nascimento']):
            messagebox.showerror('Erro', 'Data de nascimento inválida! Use o formato DD/MM/AAAA')
            return False
        
        return True

    def _clear_entries(self, entries: Dict[str, Any]):
        """Função auxiliar para limpar um dicionário de Entries/Text widgets."""
        for entry in entries.values():
            if isinstance(entry, tk.Text):
                entry.delete('1.0', 'end')
            else:
                entry.delete(0, 'end')
                if hasattr(entry, 'reset'):
                    entry.reset()

    def _clear_form(self):
        """Limpa formulário de cadastro de pessoa."""
        self.current_pessoa_id = None
        self._clear_entries(self.entries)

    def _clear_evento_form(self):
        """Limpa formulário de evento."""
        self._clear_entries(self.evento_entries)
        self.evento_entries['tipo'].current(0)
    
    def _save_pessoa(self):
        """Salva nova pessoa (Chama AppController)"""
        if not self._validate_form():
            return
        
        pessoa = self._get_form_data()
        
        try:
            pessoa_id = self.controller.salvar_pessoa(pessoa) # Usa o AppController
            self.status_bar.set_message(f'Pessoa cadastrada com sucesso! ID: {pessoa_id}')
            self._clear_form()
            self._load_initial_data() # Recarrega tudo
        except ValueError as ve: # Erro de negócio (Ex: CPF duplicado)
            messagebox.showerror('Erro', str(ve))
        except Exception as e:
            logger.error(f'Erro ao salvar pessoa: {str(e)}')
            messagebox.showerror('Erro', f'Não foi possível salvar: {str(e)}')
    
    def _update_pessoa(self):
        """Atualiza pessoa existente (Chama AppController)"""
        if not self.current_pessoa_id:
            messagebox.showwarning('Aviso', 'Selecione uma pessoa para atualizar!')
            return
        
        if not self._validate_form():
            return
        
        pessoa = self._get_form_data()
        
        try:
            self.controller.salvar_pessoa(pessoa, self.current_pessoa_id) # Usa o AppController para atualizar
            self.status_bar.set_message('Pessoa atualizada com sucesso!')
            self._clear_form()
            self._load_initial_data() # Recarrega tudo
        except ValueError as ve: # Erro de negócio (Ex: CPF duplicado)
            messagebox.showerror('Erro', str(ve))
        except Exception as e:
            logger.error(f'Erro ao atualizar pessoa: {str(e)}')
            messagebox.showerror('Erro', f'Não foi possível atualizar: {str(e)}')
    
    def _delete_pessoa(self):
        """Exclui pessoa (Chama AppController)"""
        if not self.current_pessoa_id:
            messagebox.showwarning('Aviso', 'Selecione uma pessoa para excluir!')
            return
        
        nome = self.entries['nome'].get().strip()
        if not nome:
            messagebox.showwarning('Aviso', 'Não foi possível identificar a pessoa selecionada!')
            return
        
        if messagebox.askyesno('Confirmar', f'Tem certeza que deseja excluir "{nome}"?'):
            try:
                if self.controller.excluir_pessoa(self.current_pessoa_id, nome): # Usa o AppController
                    self.status_bar.set_message(f'Pessoa "{nome}" excluída com sucesso!')
                    self._clear_form()
                    self._load_initial_data() # Recarrega tudo
                else:
                    messagebox.showerror('Erro', 'Não foi possível excluir a pessoa!')
            except Exception as e:
                logger.error(f'Erro ao excluir pessoa: {str(e)}')
                messagebox.showerror('Erro', f'Não foi possível excluir: {str(e)}')

    def _save_evento(self):
        """Salva novo evento (Chama AppController)"""
        titulo = self.evento_entries['titulo'].get().strip()
        data = self.evento_entries['data_evento'].get().strip()
        
        if not titulo:
            messagebox.showerror('Erro', 'O título do evento é obrigatório!')
            return
        if not data:
            messagebox.showerror('Erro', 'A data do evento é obrigatória!')
            return
        if not Utils.validate_date(data):
            messagebox.showerror('Erro', 'Data inválida! Use o formato DD/MM/AAAA')
            return
        
        evento = {
            'titulo': titulo,
            'descricao': self.evento_entries['descricao'].get('1.0', 'end').strip(),
            'data_evento': data,
            'tipo': self.evento_entries['tipo'].get(),
            'local': self.evento_entries['local'].get().strip(),
            'responsavel': self.evento_entries['responsavel'].get().strip()
        }
        
        try:
            evento_id = self.controller.salvar_evento(evento) # Usa o AppController
            self.status_bar.set_message(f'Evento cadastrado com sucesso! ID: {evento_id}')
            self._clear_evento_form()
            self._load_eventos()
            self._update_statistics()
        except Exception as e:
            logger.error(f'Erro ao salvar evento: {str(e)}')
            messagebox.showerror('Erro', f'Não foi possível salvar: {str(e)}')

    # --- CONSULTA & UI INTERACTIONS (mantido) ---
    def _search_pessoas(self, search_term: str = None):
        """Busca pessoas"""
        search_term = search_term or self.search_bar.get()
        
        filters = {}
        if search_term:
            filters['nome'] = search_term
        
        cidade = self.filter_cidade.get()
        if cidade:
            filters['cidade'] = cidade
        
        pessoas = self.db.search_pessoas(filters)
        
        # Limpar treeview
        for item in self.tree_pessoas.get_children():
            self.tree_pessoas.delete(item)
        
        # Preencher com resultados
        for p in pessoas:
            self.tree_pessoas.insert('', 'end', values=(
                p['id'],
                p['nome'],
                Utils.format_cpf(p['cpf']),
                Utils.format_phone(p['telefone']),
                p['cidade'],
                p['bairro'],
                p['data_nascimento'],
                p['email']
            ))
        
        self.status_bar.set_stats(f'Encontrados: {len(pessoas)} pessoas')
    
    def _clear_filters(self):
        """Limpa filtros de busca"""
        self.filter_cidade.set('')
        self.search_bar._clear()
    
    def _on_pessoa_select(self, event):
        """Ao selecionar pessoa na treeview"""
        selection = self.tree_pessoas.selection()
        if not selection:
            return
        
        item = self.tree_pessoas.item(selection[0])
        pessoa_id = item['values'][0]
        
        # Buscar dados completos
        pessoa = self.db.get_pessoa_by_id(pessoa_id)
        if pessoa:
            self._fill_form(pessoa)
    
    def _edit_selected_pessoa(self):
        """Edita pessoa selecionada (duplo clique)"""
        selection = self.tree_pessoas.selection()
        if selection:
            self.notebook.select(0)  # Vai para aba de cadastro
    
    def _fill_form(self, pessoa):
        """Preenche formulário com dados da pessoa"""
        self.current_pessoa_id = pessoa['id']
        
        self.entries['nome'].delete(0, 'end')
        self.entries['nome'].insert(0, pessoa['nome'])
        
        self.entries['cpf'].delete(0, 'end')
        self.entries['cpf'].insert(0, Utils.format_cpf(pessoa['cpf']))
        
        self.entries['telefone'].delete(0, 'end')
        self.entries['telefone'].insert(0, Utils.format_phone(pessoa['telefone']))
        
        self.entries['cidade'].delete(0, 'end')
        self.entries['cidade'].insert(0, pessoa['cidade'])
        
        self.entries['bairro'].delete(0, 'end')
        self.entries['bairro'].insert(0, pessoa['bairro'])
        
        self.entries['data_nascimento'].delete(0, 'end')
        self.entries['data_nascimento'].insert(0, pessoa['data_nascimento'])
        
        self.entries['email'].delete(0, 'end')
        self.entries['email'].insert(0, pessoa['email'])
        
        self.entries['rede_social'].delete(0, 'end')
        self.entries['rede_social'].insert(0, pessoa['rede_social'])
        
        self.entries['observacoes'].delete('1.0', 'end')
        self.entries['observacoes'].insert('1.0', pessoa['observacoes'])
    
    # --- EXPORTS & SYSTEM (mantido) ---
    def _export_html(self, tipo: str):
        """Exporta relatório HTML"""
        if tipo == 'completo':
            pessoas = self.db.search_pessoas()
            eventos = self.db.search_eventos()
            title = "Relatório Completo IBVRD"
        else:
            pessoas = self.db.get_aniversariantes()
            eventos = []
            title = "Relatório de Aniversariantes IBVRD"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension='.html',
            filetypes=[('HTML', '*.html'), ('Todos os arquivos', '*.*')],
            title='Salvar Relatório HTML'
        )
        
        if filepath:
            try:
                ReportGenerator.export_html(pessoas, eventos, filepath, title)
                messagebox.showinfo('Sucesso', f'Relatório exportado com sucesso!\n{filepath}')
            except Exception as e:
                logger.error(f'Erro ao exportar HTML: {str(e)}')
                messagebox.showerror('Erro', f'Não foi possível exportar: {str(e)}')
    
    def _export_aniversariantes(self):
        """Exporta relatório de aniversariantes"""
        mes = self.mes_var.get()
        pessoas = self.db.get_aniversariantes(mes)
        
        filepath = filedialog.asksaveasfilename(
            defaultextension='.html',
            filetypes=[('HTML', '*.html'), ('Todos os arquivos', '*.*')],
            title='Salvar Relatório de Aniversariantes'
        )
        
        if filepath:
            try:
                ReportGenerator.export_aniversariantes_html(pessoas, filepath, mes)
                messagebox.showinfo('Sucesso', f'Relatório exportado com sucesso!\n{filepath}')
            except Exception as e:
                logger.error(f'Erro ao exportar aniversariantes: {str(e)}')
                messagebox.showerror('Erro', f'Não foi possível exportar: {str(e)}')
    
    def _export_csv(self):
        """Exporta dados para CSV"""
        pessoas = self.db.search_pessoas()
        
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv'), ('Todos os arquivos', '*.*')],
            title='Salvar Arquivo CSV'
        )
        
        if filepath:
            try:
                ReportGenerator.export_csv(pessoas, filepath)
                messagebox.showinfo('Sucesso', f'Dados exportados com sucesso!\n{filepath}')
            except Exception as e:
                logger.error(f'Erro ao exportar CSV: {str(e)}')
                messagebox.showerror('Erro', f'Não foi possível exportar: {str(e)}')
    
    def _create_backup(self):
        """Cria backup do banco"""
        try:
            backup_path = self.db.create_backup()
            messagebox.showinfo('Sucesso', f'Backup criado com sucesso!\n{backup_path}')
        except Exception as e:
            logger.error(f'Erro ao criar backup: {str(e)}')
            messagebox.showerror('Erro', f'Não foi possível criar backup: {str(e)}')
    
    def _restore_backup(self):
        """Restaura backup"""
        filepath = filedialog.askopenfilename(
            title='Selecionar Backup',
            filetypes=[('Banco de Dados', '*.db'), ('Todos os arquivos', '*.*')]
        )
        
        if filepath:
            if messagebox.askyesno('Confirmar', 'Tem certeza que deseja restaurar este backup? Todos os dados atuais serão substituídos.'):
                try:
                    # Fechar conexão atual
                    self.db = None
                    
                    # Fazer backup do atual antes de restaurar
                    shutil.copy2(Config.DB_NAME, f'{Config.DB_NAME}.bak')
                    
                    # Restaurar
                    shutil.copy2(filepath, Config.DB_NAME)
                    
                    # Recriar gerenciador
                    self.db = DatabaseManager()
                    self.controller = AppController(self.db) # Recriar controller
                    
                    # Recarregar dados
                    self._load_initial_data()
                    
                    messagebox.showinfo('Sucesso', 'Backup restaurado com sucesso!')
                except Exception as e:
                    logger.error(f'Erro ao restaurar backup: {str(e)}')
                    messagebox.showerror('Erro', f'Não foi possível restaurar: {str(e)}')
    
    def _clear_cache(self):
        """Limpa cache"""
        self.db.clear_cache()
        self.status_bar.set_message('Cache limpo com sucesso!')
        # Força recarregar dados que usam cache (como cidades)
        self._load_cidades() 
    
    def _check_integrity(self):
        """Verifica integridade dos dados (Chama AppController)"""
        try:
            results = self.controller.verificar_integridade()
            
            # Resultados
            msg = f"""
            Verificação de Integridade:
            
            Total de Pessoas (Ativas/Inativas): {results['pessoas_total']}
            Total de Eventos: {results['eventos_total']}
            CPFs Duplicados (Ativos): {len(results['cpfs_duplicados'])}
            """
            
            if results['cpfs_duplicados']:
                msg += "\n\nCPFs duplicados encontrados:\n"
                for cpf in results['cpfs_duplicados']:
                    msg += f"- {Utils.format_cpf(cpf)}\n"
            
            messagebox.showinfo('Verificação de Integridade', msg)
        except Exception as e:
            logger.error(f'Erro ao verificar integridade: {str(e)}')
            messagebox.showerror('Erro', f'Não foi possível verificar: {str(e)}')
    
    # --- UTILS DE UI (mantido) ---
    def _change_theme(self, theme_name: str):
        """Muda tema da interface"""
        if theme_name in Config.THEMES:
            self.current_theme = theme_name
            self.theme = Config.THEMES[theme_name]
            self._apply_theme()
            self.status_bar.set_message(f'Tema alterado para {theme_name}')
    
    def _format_cpf(self):
        """Formata CPF durante digitação"""
        value = self.entries['cpf'].get()
        formatted = Utils.format_cpf(value)
        
        # Só atualiza se houve mudança
        if formatted != value:
            self.entries['cpf'].delete(0, 'end')
            self.entries['cpf'].insert(0, formatted)
    
    def _format_phone(self):
        """Formata telefone durante digitação"""
        value = self.entries['telefone'].get()
        formatted = Utils.format_phone(value)
        
        # Só atualiza se houve mudança
        if formatted != value:
            self.entries['telefone'].delete(0, 'end')
            self.entries['telefone'].insert(0, formatted)
    
    def _format_date(self):
        """Formata data durante digitação"""
        value = self.entries['data_nascimento'].get()
        
        # Adicionar barras automaticamente
        if len(value) == 2 or len(value) == 5:
            if not value.endswith('/'):
                self.entries['data_nascimento'].insert('end', '/')
    
    def _sort_tree(self, col):
        """Ordena treeview por coluna"""
        data = [(self.tree_pessoas.set(child, col), child) for child in self.tree_pessoas.get_children('')]
        
        # Tentar converter para número se possível
        try:
            data.sort(key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
        except:
            data.sort()
        
        for index, (val, child) in enumerate(data):
            self.tree_pessoas.move(child, '', index)
    
    def _check_auto_backup(self):
        """Verifica se deve fazer backup automático"""
        if self.db.should_backup():
            threading.Thread(target=self._create_backup, daemon=True).start()
        
        # Agendar próxima verificação
        self.root.after(3600000, self._check_auto_backup)  # 1 hora
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Trata exceções não capturadas"""
        logger.critical(
            f"Exceção não tratada: {exc_type.__name__}: {exc_value}",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        messagebox.showerror(
            'Erro Crítico',
            f'Ocorreu um erro inesperado:\n{exc_value}\n\n'
            f'Por favor, reinicie o aplicativo e contate o suporte se o problema persistir.'
        )

# ====================== MAIN ======================
if __name__ == '__main__':
    root = tk.Tk()
    app = IBVRDApp(root)
    root.mainloop()