from typing import Dict, List, Any
from services.evento_service import EventoService
from config.settings import logger

class EventoController:
    """Controlador para a lógica de Evento (Criação, Consulta)"""
    
    def __init__(self, evento_service: EventoService):
        self.service = evento_service
    
    def add_evento(self, evento_data: Dict) -> int:
        """Adiciona novo evento"""
        logger.info(f"Cadastrando novo evento: {evento_data.get('titulo')}")
        new_id = self.service.add_evento(evento_data)
        return new_id
    
    def search_eventos(self, filters: Dict = None) -> List[Any]:
        """Busca e retorna eventos para a Treeview"""
        eventos = self.service.search_eventos(filters=filters)
        
        # Formatar dados para exibição na Treeview (sem muita formatação aqui)
        formatted_eventos = []
        for e in eventos:
            formatted_eventos.append((
                e['id'],
                e['titulo'],
                e['data_evento'],
                e['tipo'],
                e['local'],
                e['responsavel']
            ))
        return formatted_eventos