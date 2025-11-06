import sqlite3
from typing import Dict, List, Any
from datetime import datetime

from models.database import DatabaseManager
from config.settings import logger, Config
from utils.validators import Validators as V

class EventoService:
    """Lógica de negócio para a entidade Evento"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def add_evento(self, evento: Dict) -> int:
        """Adiciona evento (validação antes de salvar)"""
        if not evento.get('titulo'):
            raise ValueError("O título do evento é obrigatório.")
            
        data = evento.get('data_evento', '')
        if not data or not V.validate_date(data):
            raise ValueError("Data do evento inválida. Use o formato DD/MM/AAAA.")
            
        return self.db.add_evento(evento)
    
    def search_eventos(self, filters: Dict = None, only_active: bool = True) -> List[sqlite3.Row]:
        """Busca eventos com filtros avançados"""
        
        query = 'SELECT * FROM eventos WHERE 1=1'
        params: List[Any] = []
        
        if only_active:
            query += ' AND ativo=1'
        
        if filters:
            if filters.get('tipo'):
                query += ' AND tipo=?'
                params.append(filters['tipo'])
            
            if filters.get('data_inicio') and filters.get('data_fim'):
                # Assumindo que data_inicio e data_fim estão no formato YYYY-MM-DD
                query += ''' AND date(
                    substr(data_evento,7,4)||'-'||
                    substr(data_evento,4,2)||'-'||
                    substr(data_evento,1,2)
                ) BETWEEN date(?) AND date(?)'''
                params.extend([filters['data_inicio'], filters['data_fim']])
        
        # Ordenação pela data (mais próxima/recente primeiro)
        query += ''' ORDER BY
            substr(data_evento,7,4) DESC,
            substr(data_evento,4,2) DESC,
            substr(data_evento,1,2) DESC
        '''
        
        return self.db.execute_query(query, tuple(params))