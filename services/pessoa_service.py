import sqlite3
from typing import Dict, List, Optional, Any
from functools import lru_cache

from models.database import DatabaseManager
from config.settings import logger
from utils.validators import Validators as V
from utils.helpers import Helpers as H

class PessoaService:
    """Lógica de negócio para a entidade Pessoa"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def add_pessoa(self, pessoa: Dict) -> int:
        """Adiciona pessoa (validação antes de salvar)"""
        if not pessoa.get('nome'):
            raise ValueError("O nome é obrigatório.")
        
        cpf = V.normalize_cpf(pessoa.get('cpf', ''))
        if cpf and not V.validate_cpf(cpf):
            raise ValueError("CPF inválido.")
        if cpf and self.cpf_exists(cpf):
            raise ValueError("CPF já cadastrado.")
            
        return self.db.add_pessoa(pessoa)
    
    def update_pessoa(self, pessoa_id: int, pessoa: Dict) -> bool:
        """Atualiza pessoa (validação antes de salvar)"""
        if not pessoa.get('nome'):
            raise ValueError("O nome é obrigatório.")
            
        cpf = V.normalize_cpf(pessoa.get('cpf', ''))
        if cpf and not V.validate_cpf(cpf):
            raise ValueError("CPF inválido.")
        if cpf and self.cpf_exists(cpf, exclude_id=pessoa_id):
            raise ValueError("CPF já cadastrado para outra pessoa.")
            
        return self.db.update_pessoa(pessoa_id, pessoa)
    
    def delete_pessoa(self, pessoa_id: int, soft: bool = True) -> bool:
        """Exclui pessoa"""
        return self.db.delete_pessoa(pessoa_id, soft)
    
    @lru_cache(maxsize=128)
    def search_pessoas(self, filters: Dict = None, only_active: bool = True) -> List[sqlite3.Row]:
        """Busca pessoas com filtros avançados (com cache)"""
        
        query = 'SELECT * FROM pessoas WHERE 1=1'
        params: List[Any] = []
        
        if only_active:
            query += ' AND ativo=1'
        
        if filters:
            if filters.get('nome'):
                query += ' AND nome LIKE ?'
                params.append(f"%{filters['nome']}%")
            
            if filters.get('cpf'):
                query += ' AND cpf LIKE ?'
                params.append(f"%{V.normalize_cpf(filters['cpf'])}%")
            
            if filters.get('cidade'):
                query += ' AND cidade LIKE ?'
                params.append(f"%{filters['cidade']}%")
            
            if filters.get('mes_aniversario'):
                query += ' AND substr(data_nascimento, 4, 2)=?'
                params.append(filters['mes_aniversario'].zfill(2))
        
        query += ' ORDER BY nome'
        
        results = self.db.execute_query(query, tuple(params))
        return results
    
    def get_pessoa_by_id(self, pessoa_id: int) -> Optional[sqlite3.Row]:
        """Retorna pessoa pelo ID"""
        return self.db.get_pessoa_by_id(pessoa_id)
        
    def cpf_exists(self, cpf: str, exclude_id: int = None) -> bool:
        """Verifica se CPF já existe"""
        cpf = V.normalize_cpf(cpf)
        if not cpf:
            return False
        
        query = 'SELECT id FROM pessoas WHERE cpf=?'
        params = [cpf]
        
        if exclude_id:
            query += ' AND id!=?'
            params.append(exclude_id)
            
        return self.db.execute_query(query, tuple(params), fetch_one=True) is not None
        
    def get_aniversariantes(self, mes: str = None) -> List[sqlite3.Row]:
        """Retorna aniversariantes do mês"""
        # ... (Query de aniversariantes)
        import datetime
        if not mes:
            mes = datetime.datetime.now().strftime('%m')
        
        mes = mes.zfill(2)
        
        query = '''
            SELECT * FROM pessoas
            WHERE ativo=1
            AND data_nascimento IS NOT NULL
            AND data_nascimento != ''
            AND substr(data_nascimento, 4, 2) = ?
            ORDER BY substr(data_nascimento, 1, 2), nome
        '''
        return self.db.execute_query(query, (mes,))

    def get_cidades(self) -> List[str]:
        """Retorna lista de cidades cadastradas"""
        query = '''
            SELECT DISTINCT cidade FROM pessoas
            WHERE ativo=1 AND cidade IS NOT NULL AND cidade != ''
            ORDER BY cidade
        '''
        return [row[0] for row in self.db.execute_query(query)]
        
    def get_duplicate_cpfs(self) -> List[str]:
        """Retorna CPFs duplicados"""
        query = '''
            SELECT cpf FROM pessoas
            WHERE cpf IS NOT NULL AND cpf != '' AND ativo=1
            GROUP BY cpf HAVING COUNT(*) > 1
        '''
        return [row[0] for row in self.db.execute_query(query)]