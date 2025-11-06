import shutil
import os
import threading
from tkinter import messagebox, filedialog
from datetime import datetime

from models.database import DatabaseManager
from config.settings import Config, logger

class BackupService:
    """Lógica de serviço para Backup e Restauração"""
    
    def __init__(self, db_manager: DatabaseManager, app_root: Any): # app_root é o tk.Tk()
        self.db = db_manager
        self.app_root = app_root
    
    def create_backup(self, show_message: bool = True):
        """Cria backup do banco e mostra mensagem opcionalmente"""
        try:
            backup_path = self.db.create_backup()
            if show_message:
                messagebox.showinfo('Sucesso', f'Backup criado com sucesso!\n{backup_path}')
        except Exception as e:
            logger.error(f'Erro ao criar backup: {str(e)}')
            if show_message:
                messagebox.showerror('Erro', f'Não foi possível criar backup: {str(e)}')
    
    def restore_backup(self, on_success_reload: callable):
        """Restaura backup a partir de um arquivo selecionado"""
        filepath = filedialog.askopenfilename(
            title='Selecionar Backup',
            filetypes=[('Banco de Dados', '*.db'), ('Todos os arquivos', '*.*')]
        )
        
        if filepath:
            if messagebox.askyesno('Confirmar', 'Tem certeza que deseja restaurar este backup? Todos os dados atuais serão substituídos.'):
                try:
                    # Fazer backup do atual antes de restaurar (safety net)
                    shutil.copy2(Config.DB_NAME, f'{Config.DB_NAME}.bak')
                    
                    # Restaurar
                    shutil.copy2(filepath, Config.DB_NAME)
                    
                    # Forçar recarregamento do DB Manager e da UI
                    on_success_reload()
                    
                    messagebox.showinfo('Sucesso', 'Backup restaurado com sucesso!')
                except Exception as e:
                    logger.error(f'Erro ao restaurar backup: {str(e)}')
                    messagebox.showerror('Erro', f'Não foi possível restaurar: {str(e)}')
    
    def check_auto_backup(self, interval_ms: int = 3600000):
        """Verifica se deve fazer backup automático e agenda a próxima verificação"""
        if self.db.should_backup():
            # Executa em thread para não travar a UI
            threading.Thread(target=self.create_backup, kwargs={'show_message': False}, daemon=True).start()
        
        # Agendar próxima verificação (recursiva)
        self.app_root.after(interval_ms, lambda: self.check_auto_backup(interval_ms))