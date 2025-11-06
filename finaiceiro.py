import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import sqlite3
import csv
from typing import Optional, Tuple
import re

# Importar DateEntry do tkcalendar
try:
    from tkcalendar import DateEntry
    HAS_DATEPICKER = True
except ImportError:
    HAS_DATEPICKER = False
    print("Aviso: tkcalendar não instalado. Para melhor experiência, instale com: pip install tkcalendar")


class DatabaseManager:
    """Gerenciador de banco de dados com context manager"""
    
    def __init__(self, db_name: str = 'ibvrd_finance.db'):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
    
    def execute(self, query: str, params: tuple = ()):
        """Executa uma query e retorna o cursor"""
        return self.cursor.execute(query, params)
    
    def fetchone(self):
        """Retorna um resultado"""
        return self.cursor.fetchone()
    
    def fetchall(self):
        """Retorna todos os resultados"""
        return self.cursor.fetchall()
    
    def commit(self):
        """Commit manual"""
        if self.conn:
            self.conn.commit()


class DateValidator:
    """Validador de datas"""
    
    @staticmethod
    def validate_date(date_str: str) -> bool:
        """Valida formato DD/MM/YYYY"""
        try:
            datetime.strptime(date_str, "%d/%m/%Y")
            return True
        except ValueError:
            return False
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """Converte string para datetime"""
        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            return None
    
    @staticmethod
    def format_date(date_obj: datetime) -> str:
        """Formata datetime para DD/MM/YYYY"""
        return date_obj.strftime("%d/%m/%Y")
    
    @staticmethod
    def get_month_year(date_str: str) -> str:
        """Extrai MM/YYYY de DD/MM/YYYY"""
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        return date_obj.strftime("%m/%Y")


class CurrencyFormatter:
    """Formatador de valores monetários"""
    
    @staticmethod
    def format_value(value: float) -> str:
        """Formata valor para R$ X.XXX,XX"""
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    @staticmethod
    def parse_value(value_str: str) -> float:
        """Converte string para float, aceitando vírgula ou ponto"""
        cleaned = value_str.replace("R$", "").replace(" ", "").strip()
        # Remover separadores de milhar
        cleaned = cleaned.replace(".", "")
        # Converter vírgula decimal para ponto
        cleaned = cleaned.replace(",", ".")
        return float(cleaned)


class IBVRDFinanceApp:
    """Sistema Financeiro IBVRD - Aplicação Principal"""
    
    # Constantes
    EXPENSE_CATEGORIES = ["Água", "Luz", "Internet", "Telefone", "Aluguel", "Manutenção", 
                         "Material de Limpeza", "Alimentação", "Transporte", "Outros"]
    CONTRIBUTION_TYPES = ["Dízimo", "Oferta", "Doação", "Eventos", "Outros"]
    
    def __init__(self, root):
        self.root = root
        self.root.title("IBVRD - Sistema Financeiro")
        self.root.geometry("950x750")
        self.root.configure(bg="#f0f0f0")
        
        # Configurar ícone (se existir)
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass
        
        # Variáveis de controle
        self.current_month = datetime.now().strftime("%m/%Y")
        self.month_var = tk.StringVar(value=self.current_month)
        
        # Inicializar banco de dados
        self.init_database()
        
        # Configurar estilos
        self.setup_styles()
        
        # Criar interface
        self.create_widgets()
        
        # Carregar dados iniciais
        self.update_dashboard()
        
        # Configurar protocolo de fechamento
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def init_database(self):
        """Inicializa o banco de dados"""
        with DatabaseManager() as db:
            # Tabela de despesas
            db.execute('''
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    month_year TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabela de entradas
            db.execute('''
                CREATE TABLE IF NOT EXISTS contributions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL,
                    contributor TEXT,
                    amount REAL NOT NULL,
                    month_year TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices para melhor performance
            db.execute('CREATE INDEX IF NOT EXISTS idx_expenses_month ON expenses(month_year)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_contributions_month ON contributions(month_year)')
            db.commit()
    
    def setup_styles(self):
        """Configura estilos ttk"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Frames
        self.style.configure('White.TFrame', background='white')
        self.style.configure('Card.TFrame', background='white', relief='raised')
        
        # Labels
        self.style.configure('White.TLabel', background='white')
        self.style.configure('Title.TLabel', background='white', font=('Arial', 12, 'bold'))
        
        # Radiobuttons
        self.style.configure('White.TRadiobutton', background='white')
        
        # Treeview
        self.style.configure('Treeview', rowheight=25)
        self.style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))
    
    def create_widgets(self):
        """Cria todos os widgets da interface"""
        # Cabeçalho
        self.create_header()
        
        # Notebook (abas)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Criar abas
        self.create_dashboard_tab()
        self.create_expenses_tab()
        self.create_contributions_tab()
        self.create_reports_tab()
        self.create_export_tab()
        
        # Atalhos de teclado
        self.setup_keyboard_shortcuts()
    
    def create_header(self):
        """Cria o cabeçalho da aplicação"""
        header = tk.Frame(self.root, bg="#1e40af", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        title_label = tk.Label(
            header, 
            text="IBVRD - Sistema Financeiro", 
            font=("Arial", 20, "bold"), 
            bg="#1e40af", 
            fg="white"
        )
        title_label.pack(pady=10)
        
        subtitle_label = tk.Label(
            header, 
            text="Igreja Batista Vida no Reino de Deus", 
            font=("Arial", 10), 
            bg="#1e40af", 
            fg="#93c5fd"
        )
        subtitle_label.pack()
    
    def create_dashboard_tab(self):
        """Cria a aba Dashboard"""
        self.dashboard_frame = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.dashboard_frame, text="📊 Dashboard")
        
        # Seletor de mês
        month_frame = tk.Frame(self.dashboard_frame, bg="white")
        month_frame.pack(fill="x", padx=20, pady=15)
        
        tk.Label(
            month_frame, 
            text="Selecione o mês:", 
            bg="white", 
            font=("Arial", 11, "bold")
        ).pack(side="left", padx=5)
        
        # Obter meses disponíveis
        months = self.get_available_months()
        
        month_combo = ttk.Combobox(
            month_frame, 
            textvariable=self.month_var, 
            values=months, 
            state="readonly", 
            width=15,
            font=("Arial", 10)
        )
        month_combo.pack(side="left", padx=5)
        month_combo.bind("<<ComboboxSelected>>", lambda e: self.update_dashboard())
        
        # Botão atualizar
        tk.Button(
            month_frame,
            text="🔄 Atualizar",
            command=self.update_dashboard,
            bg="#6366f1",
            fg="white",
            font=("Arial", 9, "bold"),
            cursor="hand2",
            padx=15,
            pady=5,
            relief="flat"
        ).pack(side="left", padx=10)
        
        # Cards de resumo
        self.create_summary_cards()
        
        # Resumo por categoria
        self.create_category_summary()
    
    def create_summary_cards(self):
        """Cria os cards de resumo financeiro"""
        cards_frame = tk.Frame(self.dashboard_frame, bg="white")
        cards_frame.pack(fill="x", padx=20, pady=20)
        
        # Card Entradas
        self.entries_card = tk.Frame(cards_frame, bg="#10b981", relief="raised", bd=0)
        self.entries_card.pack(side="left", fill="both", expand=True, padx=8)
        
        tk.Label(
            self.entries_card, 
            text="💰 Entradas do Mês", 
            font=("Arial", 11), 
            bg="#10b981", 
            fg="white"
        ).pack(pady=(15, 5))
        
        self.entries_value = tk.Label(
            self.entries_card, 
            text="R$ 0,00", 
            font=("Arial", 22, "bold"), 
            bg="#10b981", 
            fg="white"
        )
        self.entries_value.pack(pady=(0, 15))
        
        # Card Despesas
        self.expenses_card = tk.Frame(cards_frame, bg="#ef4444", relief="raised", bd=0)
        self.expenses_card.pack(side="left", fill="both", expand=True, padx=8)
        
        tk.Label(
            self.expenses_card, 
            text="💸 Despesas do Mês", 
            font=("Arial", 11), 
            bg="#ef4444", 
            fg="white"
        ).pack(pady=(15, 5))
        
        self.expenses_value = tk.Label(
            self.expenses_card, 
            text="R$ 0,00", 
            font=("Arial", 22, "bold"), 
            bg="#ef4444", 
            fg="white"
        )
        self.expenses_value.pack(pady=(0, 15))
        
        # Card Saldo
        self.balance_card = tk.Frame(cards_frame, bg="#3b82f6", relief="raised", bd=0)
        self.balance_card.pack(side="left", fill="both", expand=True, padx=8)
        
        tk.Label(
            self.balance_card, 
            text="📈 Saldo do Mês", 
            font=("Arial", 11), 
            bg="#3b82f6", 
            fg="white"
        ).pack(pady=(15, 5))
        
        self.balance_value = tk.Label(
            self.balance_card, 
            text="R$ 0,00", 
            font=("Arial", 22, "bold"), 
            bg="#3b82f6", 
            fg="white"
        )
        self.balance_value.pack(pady=(0, 15))
    
    def create_category_summary(self):
        """Cria o resumo por categoria"""
        summary_frame = tk.Frame(self.dashboard_frame, bg="white")
        summary_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        tk.Label(
            summary_frame, 
            text="📑 Despesas por Categoria", 
            font=("Arial", 14, "bold"), 
            bg="white"
        ).pack(anchor="w", pady=10)
        
        # Frame com scrollbar
        tree_frame = tk.Frame(summary_frame, bg="white")
        tree_frame.pack(fill="both", expand=True)
        
        self.category_tree = ttk.Treeview(
            tree_frame, 
            columns=("Valor", "Percentual"), 
            height=8
        )
        self.category_tree.heading("#0", text="Categoria")
        self.category_tree.heading("Valor", text="Valor")
        self.category_tree.heading("Percentual", text="% do Total")
        
        self.category_tree.column("#0", width=250)
        self.category_tree.column("Valor", width=150, anchor="e")
        self.category_tree.column("Percentual", width=120, anchor="center")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.category_tree.yview)
        self.category_tree.configure(yscrollcommand=scrollbar.set)
        
        self.category_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_expenses_tab(self):
        """Cria a aba de Despesas"""
        self.expenses_frame = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.expenses_frame, text="💸 Despesas")
        
        # Formulário
        form_frame = tk.LabelFrame(
            self.expenses_frame, 
            text="Adicionar Nova Despesa", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        form_frame.pack(fill="x", padx=20, pady=20)
        
        # Linha 1
        row1 = tk.Frame(form_frame, bg="white")
        row1.pack(fill="x", pady=8)
        
        tk.Label(row1, text="Categoria:*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left")
        self.expense_category = ttk.Combobox(
            row1, 
            values=self.EXPENSE_CATEGORIES, 
            state="readonly", 
            width=22,
            font=("Arial", 10)
        )
        self.expense_category.set(self.EXPENSE_CATEGORIES[0])
        self.expense_category.pack(side="left", padx=5)
        
        tk.Label(row1, text="Valor (R$):*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        self.expense_amount = tk.Entry(row1, width=22, font=("Arial", 10))
        self.expense_amount.pack(side="left", padx=5)
        
        # Linha 2
        row2 = tk.Frame(form_frame, bg="white")
        row2.pack(fill="x", pady=8)
        
        tk.Label(row2, text="Data:*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left")
        self.expense_date = tk.Entry(row2, width=22, font=("Arial", 10))
        self.expense_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.expense_date.pack(side="left", padx=5)
        
        tk.Label(row2, text="Descrição:", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        self.expense_desc = tk.Entry(row2, width=22, font=("Arial", 10))
        self.expense_desc.pack(side="left", padx=5)
        
        # Botão adicionar
        btn_frame = tk.Frame(form_frame, bg="white")
        btn_frame.pack(fill="x", pady=15)
        
        tk.Button(
            btn_frame, 
            text="➕ Adicionar Despesa",
            command=self.add_expense,
            bg="#2563eb", 
            fg="white", 
            font=("Arial", 10, "bold"), 
            cursor="hand2", 
            padx=25, 
            pady=8,
            relief="flat"
        ).pack()
        
        tk.Label(btn_frame, text="* Campos obrigatórios", bg="white", fg="#6b7280", font=("Arial", 8)).pack(pady=(5, 0))
        
        # Lista de despesas
        self.create_expenses_list()
    
    def create_expenses_list(self):
        """Cria a lista de despesas"""
        list_frame = tk.LabelFrame(
            self.expenses_frame, 
            text="Lista de Despesas do Mês", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Frame para treeview
        tree_frame = tk.Frame(list_frame, bg="white")
        tree_frame.pack(fill="both", expand=True)
        
        # Treeview
        self.expenses_tree = ttk.Treeview(
            tree_frame, 
            columns=("Data", "Categoria", "Descrição", "Valor"),
            height=10
        )
        self.expenses_tree.heading("#0", text="ID")
        self.expenses_tree.heading("Data", text="Data")
        self.expenses_tree.heading("Categoria", text="Categoria")
        self.expenses_tree.heading("Descrição", text="Descrição")
        self.expenses_tree.heading("Valor", text="Valor")
        
        self.expenses_tree.column("#0", width=50)
        self.expenses_tree.column("Data", width=100)
        self.expenses_tree.column("Categoria", width=130)
        self.expenses_tree.column("Descrição", width=250)
        self.expenses_tree.column("Valor", width=120, anchor="e")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.expenses_tree.yview)
        self.expenses_tree.configure(yscrollcommand=scrollbar.set)
        
        self.expenses_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Botões
        btn_frame = tk.Frame(list_frame, bg="white")
        btn_frame.pack(fill="x", pady=10)
        
        tk.Button(
            btn_frame, 
            text="🗑️ Deletar Selecionado",
            command=self.delete_expense,
            bg="#dc2626", 
            fg="white", 
            font=("Arial", 9, "bold"), 
            cursor="hand2", 
            padx=15, 
            pady=6,
            relief="flat"
        ).pack(side="left", padx=5)
        
        tk.Button(
            btn_frame, 
            text="📥 Exportar para CSV",
            command=lambda: self.export_to_csv("expenses"),
            bg="#059669", 
            fg="white", 
            font=("Arial", 9, "bold"), 
            cursor="hand2", 
            padx=15, 
            pady=6,
            relief="flat"
        ).pack(side="left", padx=5)
    
    def create_contributions_tab(self):
        """Cria a aba de Entradas"""
        self.contributions_frame = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.contributions_frame, text="💰 Entradas")
        
        # Formulário
        form_frame = tk.LabelFrame(
            self.contributions_frame, 
            text="Adicionar Nova Entrada", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        form_frame.pack(fill="x", padx=20, pady=20)
        
        # Linha 1
        row1 = tk.Frame(form_frame, bg="white")
        row1.pack(fill="x", pady=8)
        
        tk.Label(row1, text="Tipo:*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left")
        self.contribution_type = ttk.Combobox(
            row1, 
            values=self.CONTRIBUTION_TYPES, 
            state="readonly", 
            width=22,
            font=("Arial", 10)
        )
        self.contribution_type.set(self.CONTRIBUTION_TYPES[0])
        self.contribution_type.pack(side="left", padx=5)
        
        tk.Label(row1, text="Valor (R$):*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        self.contribution_amount = tk.Entry(row1, width=22, font=("Arial", 10))
        self.contribution_amount.pack(side="left", padx=5)
        
        # Linha 2
        row2 = tk.Frame(form_frame, bg="white")
        row2.pack(fill="x", pady=8)
        
        tk.Label(row2, text="Data:*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left")
        self.contribution_date = tk.Entry(row2, width=22, font=("Arial", 10))
        self.contribution_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.contribution_date.pack(side="left", padx=5)
        
        tk.Label(row2, text="Contribuinte:", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        self.contribution_name = tk.Entry(row2, width=22, font=("Arial", 10))
        self.contribution_name.pack(side="left", padx=5)
        
        # Botão adicionar
        btn_frame = tk.Frame(form_frame, bg="white")
        btn_frame.pack(fill="x", pady=15)
        
        tk.Button(
            btn_frame, 
            text="➕ Adicionar Entrada",
            command=self.add_contribution,
            bg="#059669", 
            fg="white", 
            font=("Arial", 10, "bold"), 
            cursor="hand2", 
            padx=25, 
            pady=8,
            relief="flat"
        ).pack()
        
        tk.Label(btn_frame, text="* Campos obrigatórios", bg="white", fg="#6b7280", font=("Arial", 8)).pack(pady=(5, 0))
        
        # Lista de entradas
        self.create_contributions_list()
    
    def create_contributions_list(self):
        """Cria a lista de entradas"""
        list_frame = tk.LabelFrame(
            self.contributions_frame, 
            text="Lista de Entradas do Mês", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Frame para treeview
        tree_frame = tk.Frame(list_frame, bg="white")
        tree_frame.pack(fill="both", expand=True)
        
        # Treeview
        self.contributions_tree = ttk.Treeview(
            tree_frame, 
            columns=("Data", "Tipo", "Contribuinte", "Valor"),
            height=10
        )
        self.contributions_tree.heading("#0", text="ID")
        self.contributions_tree.heading("Data", text="Data")
        self.contributions_tree.heading("Tipo", text="Tipo")
        self.contributions_tree.heading("Contribuinte", text="Contribuinte")
        self.contributions_tree.heading("Valor", text="Valor")
        
        self.contributions_tree.column("#0", width=50)
        self.contributions_tree.column("Data", width=100)
        self.contributions_tree.column("Tipo", width=130)
        self.contributions_tree.column("Contribuinte", width=250)
        self.contributions_tree.column("Valor", width=120, anchor="e")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.contributions_tree.yview)
        self.contributions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.contributions_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Botões
        btn_frame = tk.Frame(list_frame, bg="white")
        btn_frame.pack(fill="x", pady=10)
        
        tk.Button(
            btn_frame, 
            text="🗑️ Deletar Selecionado",
            command=self.delete_contribution,
            bg="#dc2626", 
            fg="white", 
            font=("Arial", 9, "bold"), 
            cursor="hand2", 
            padx=15, 
            pady=6,
            relief="flat"
        ).pack(side="left", padx=5)
        
        tk.Button(
            btn_frame, 
            text="📥 Exportar para CSV",
            command=lambda: self.export_to_csv("contributions"),
            bg="#059669", 
            fg="white", 
            font=("Arial", 9, "bold"), 
            cursor="hand2", 
            padx=15, 
            pady=6,
            relief="flat"
        ).pack(side="left", padx=5)
    
    def create_reports_tab(self):
        """Cria a aba de Relatórios"""
        self.reports_frame = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.reports_frame, text="📋 Relatórios")
        
        # Frame para seleção de período
        period_frame = tk.LabelFrame(
            self.reports_frame, 
            text="Configurações do Relatório", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        period_frame.pack(fill="x", padx=20, pady=20)
        
        # Datas
        row1 = tk.Frame(period_frame, bg="white")
        row1.pack(fill="x", pady=8)
        
        tk.Label(row1, text="Data Início:*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left")
        self.report_start_date = tk.Entry(row1, width=18, font=("Arial", 10))
        self.report_start_date.insert(0, f"01/{datetime.now().strftime('%m/%Y')}")
        self.report_start_date.pack(side="left", padx=5)
        
        tk.Label(row1, text="Data Fim:*", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        self.report_end_date = tk.Entry(row1, width=18, font=("Arial", 10))
        self.report_end_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.report_end_date.pack(side="left", padx=5)
        
        # Botões
        btn_frame = tk.Frame(period_frame, bg="white")
        btn_frame.pack(fill="x", pady=15)
        
        tk.Button(
            btn_frame, 
            text="📊 Gerar Relatório",
            command=self.generate_report,
            bg="#8b5cf6", 
            fg="white", 
            font=("Arial", 10, "bold"), 
            cursor="hand2", 
            padx=20, 
            pady=8,
            relief="flat"
        ).pack(side="left", padx=5)
        
        # Continuação do código anterior...

        tk.Button(
                btn_frame, 
                text="📥 Exportar Relatório",
                command=self.export_report_to_csv,
                bg="#059669", 
                fg="white", 
                font=("Arial", 10, "bold"), 
                cursor="hand2", 
                padx=20, 
                pady=8,
                relief="flat"
            ).pack(side="left", padx=5)
        
        # Área de exibição do relatório
        report_display_frame = tk.LabelFrame(
            self.reports_frame, 
            text="Relatório Financeiro", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        report_display_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Frame para treeview
        tree_frame = tk.Frame(report_display_frame, bg="white")
        tree_frame.pack(fill="both", expand=True)
        
        # Treeview
        self.report_tree = ttk.Treeview(
            tree_frame, 
            columns=("Data", "Tipo", "Descrição", "Valor", "Saldo"),
            height=15
        )
        self.report_tree.heading("#0", text="ID")
        self.report_tree.heading("Data", text="Data")
        self.report_tree.heading("Tipo", text="Tipo")
        self.report_tree.heading("Descrição", text="Descrição")
        self.report_tree.heading("Valor", text="Valor")
        self.report_tree.heading("Saldo", text="Saldo Acumulado")
        
        self.report_tree.column("#0", width=50)
        self.report_tree.column("Data", width=100)
        self.report_tree.column("Tipo", width=100)
        self.report_tree.column("Descrição", width=250)
        self.report_tree.column("Valor", width=120, anchor="e")
        self.report_tree.column("Saldo", width=120, anchor="e")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=scrollbar.set)
        
        self.report_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Resumo do relatório
        self.report_summary_frame = tk.Frame(report_display_frame, bg="white")
        self.report_summary_frame.pack(fill="x", pady=10)
        
        self.report_summary_label = tk.Label(
            self.report_summary_frame, 
            text="", 
            bg="white", 
            font=("Arial", 11, "bold"),
            justify="left"
        )
        self.report_summary_label.pack(anchor="w")
    
    def create_export_tab(self):
        """Cria a aba de Exportação"""
        self.export_frame = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.export_frame, text="📤 Exportar Dados")
        
        # Frame para opções de exportação
        options_frame = tk.LabelFrame(
            self.export_frame, 
            text="Opções de Exportação", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        options_frame.pack(fill="x", padx=20, pady=20)
        
        # Opções de exportação
        tk.Label(
            options_frame, 
            text="Selecione o tipo de dados para exportar:", 
            bg="white", 
            font=("Arial", 11)
        ).pack(anchor="w", pady=10)
        
        self.export_type = tk.StringVar(value="all")
        
        tk.Radiobutton(
            options_frame, 
            text="Todos os dados (despesas e entradas)", 
            variable=self.export_type, 
            value="all",
            bg="white",
            font=("Arial", 10)
        ).pack(anchor="w", padx=20, pady=5)
        
        tk.Radiobutton(
            options_frame, 
            text="Apenas despesas", 
            variable=self.export_type, 
            value="expenses",
            bg="white",
            font=("Arial", 10)
        ).pack(anchor="w", padx=20, pady=5)
        
        tk.Radiobutton(
            options_frame, 
            text="Apenas entradas", 
            variable=self.export_type, 
            value="contributions",
            bg="white",
            font=("Arial", 10)
        ).pack(anchor="w", padx=20, pady=5)
        
        # Período
        period_frame = tk.Frame(options_frame, bg="white")
        period_frame.pack(fill="x", pady=15)
        
        tk.Label(period_frame, text="Data Início:", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left")
        self.export_start_date = tk.Entry(period_frame, width=18, font=("Arial", 10))
        self.export_start_date.insert(0, f"01/{datetime.now().strftime('%m/%Y')}")
        self.export_start_date.pack(side="left", padx=5)
        
        tk.Label(period_frame, text="Data Fim:", bg="white", width=12, anchor="w", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        self.export_end_date = tk.Entry(period_frame, width=18, font=("Arial", 10))
        self.export_end_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.export_end_date.pack(side="left", padx=5)
        
        # Botão exportar
        btn_frame = tk.Frame(options_frame, bg="white")
        btn_frame.pack(fill="x", pady=15)
        
        tk.Button(
            btn_frame, 
            text="📥 Exportar para CSV",
            command=self.export_data,
            bg="#059669", 
            fg="white", 
            font=("Arial", 10, "bold"), 
            cursor="hand2", 
            padx=20, 
            pady=8,
            relief="flat"
        ).pack()
        
        # Informações
        info_frame = tk.LabelFrame(
            self.export_frame, 
            text="Informações", 
            font=("Arial", 12, "bold"), 
            bg="white", 
            padx=20, 
            pady=15
        )
        info_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        info_text = tk.Text(info_frame, height=10, width=80, wrap="word", font=("Arial", 10))
        info_text.pack(fill="both", expand=True)
        info_text.insert("1.0", 
            "Sobre a exportação de dados:\n\n"
            "• Os dados serão exportados no formato CSV (valores separados por vírgula)\n"
            "• Você pode abrir esses arquivos em programas como Excel, Google Sheets ou LibreOffice Calc\n"
            "• O formato de data utilizado é DD/MM/YYYY\n"
            "• Os valores monetários são exportados com ponto como separador decimal\n"
            "• Para exportar todos os dados, deixe os campos de data em branco\n\n"
            "Dica: Use a função de relatórios para visualizar os dados antes de exportá-los."
        )
        info_text.config(state="disabled")
    
    def setup_keyboard_shortcuts(self):
        """Configura atalhos de teclado"""
        self.root.bind("<Control-n>", lambda e: self.notebook.select(1))  # Ir para aba de despesas
        self.root.bind("<Control-i>", lambda e: self.notebook.select(2))  # Ir para aba de entradas
        self.root.bind("<Control-r>", lambda e: self.notebook.select(3))  # Ir para aba de relatórios
        self.root.bind("<Control-e>", lambda e: self.notebook.select(4))  # Ir para aba de exportação
        self.root.bind("<F5>", lambda e: self.update_dashboard())  # Atualizar dashboard
    
    def get_available_months(self) -> list:
        """Obtém lista de meses disponíveis no banco de dados"""
        with DatabaseManager() as db:
            # Obter meses das despesas
            db.execute("SELECT DISTINCT month_year FROM expenses ORDER BY month_year DESC")
            expense_months = [row[0] for row in db.fetchall()]
            
            # Obter meses das entradas
            db.execute("SELECT DISTINCT month_year FROM contributions ORDER BY month_year DESC")
            contribution_months = [row[0] for row in db.fetchall()]
            
            # Combinar e remover duplicatas
            all_months = list(set(expense_months + contribution_months))
            all_months.sort(reverse=True)
            
            return all_months
    
    def update_dashboard(self):
        """Atualiza o dashboard com dados do mês selecionado"""
        selected_month = self.month_var.get()
        
        # Obter totais do mês
        total_expenses = self.get_monthly_expenses(selected_month)
        total_contributions = self.get_monthly_contributions(selected_month)
        balance = total_contributions - total_expenses
        
        # Atualizar cards
        self.entries_value.config(text=CurrencyFormatter.format_value(total_contributions))
        self.expenses_value.config(text=CurrencyFormatter.format_value(total_expenses))
        
        # Atualizar cor do saldo
        if balance >= 0:
            self.balance_value.config(text=CurrencyFormatter.format_value(balance))
            self.balance_card.config(bg="#3b82f6")
            self.balance_value.config(bg="#3b82f6")
        else:
            self.balance_value.config(text=CurrencyFormatter.format_value(balance))
            self.balance_card.config(bg="#ef4444")
            self.balance_value.config(bg="#ef4444")
        
        # Atualizar resumo por categoria
        self.update_category_summary(selected_month)
        
        # Atualizar listas
        self.update_expenses_list(selected_month)
        self.update_contributions_list(selected_month)
    
    def get_monthly_expenses(self, month_year: str) -> float:
        """Obtém o total de despesas do mês"""
        with DatabaseManager() as db:
            db.execute(
                "SELECT SUM(amount) FROM expenses WHERE month_year = ?", 
                (month_year,)
            )
            result = db.fetchone()
            return result[0] if result[0] else 0.0
    
    def get_monthly_contributions(self, month_year: str) -> float:
        """Obtém o total de entradas do mês"""
        with DatabaseManager() as db:
            db.execute(
                "SELECT SUM(amount) FROM contributions WHERE month_year = ?", 
                (month_year,)
            )
            result = db.fetchone()
            return result[0] if result[0] else 0.0
    
    def update_category_summary(self, month_year: str):
        """Atualiza o resumo por categoria"""
        # Limpar treeview
        for item in self.category_tree.get_children():
            self.category_tree.delete(item)
        
        # Obter dados
        with DatabaseManager() as db:
            db.execute(
                "SELECT category, SUM(amount) FROM expenses WHERE month_year = ? GROUP BY category ORDER BY SUM(amount) DESC", 
                (month_year,)
            )
            categories = db.fetchall()
        
        # Calcular total
        total = sum(amount for _, amount in categories)
        
        # Adicionar itens ao treeview
        for category, amount in categories:
            percentage = (amount / total * 100) if total > 0 else 0
            self.category_tree.insert(
                "", 
                "end", 
                text=category, 
                values=(CurrencyFormatter.format_value(amount), f"{percentage:.1f}%")
            )
    
    def update_expenses_list(self, month_year: str):
        """Atualiza a lista de despesas"""
        # Limpar treeview
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)
        
        # Obter dados
        with DatabaseManager() as db:
            db.execute(
                "SELECT id, date, category, description, amount FROM expenses WHERE month_year = ? ORDER BY date DESC", 
                (month_year,)
            )
            expenses = db.fetchall()
        
        # Adicionar itens ao treeview
        for expense in expenses:
            self.expenses_tree.insert(
                "", 
                "end", 
                text=expense[0], 
                values=(expense[1], expense[2], expense[3], CurrencyFormatter.format_value(expense[4]))
            )
    
    def update_contributions_list(self, month_year: str):
        """Atualiza a lista de entradas"""
        # Limpar treeview
        for item in self.contributions_tree.get_children():
            self.contributions_tree.delete(item)
        
        # Obter dados
        with DatabaseManager() as db:
            db.execute(
                "SELECT id, date, type, contributor, amount FROM contributions WHERE month_year = ? ORDER BY date DESC", 
                (month_year,)
            )
            contributions = db.fetchall()
        
        # Adicionar itens ao treeview
        for contribution in contributions:
            self.contributions_tree.insert(
                "", 
                "end", 
                text=contribution[0], 
                values=(contribution[1], contribution[2], contribution[3] or "", CurrencyFormatter.format_value(contribution[4]))
            )
    
    def add_expense(self):
        """Adiciona uma nova despesa"""
        # Validar campos
        category = self.expense_category.get()
        amount_str = self.expense_amount.get().strip()
        date_str = self.expense_date.get().strip()
        description = self.expense_desc.get().strip()
        
        if not category:
            messagebox.showerror("Erro", "Selecione uma categoria!")
            return
        
        if not amount_str:
            messagebox.showerror("Erro", "Informe o valor da despesa!")
            return
        
        if not date_str:
            messagebox.showerror("Erro", "Informe a data da despesa!")
            return
        
        if not DateValidator.validate_date(date_str):
            messagebox.showerror("Erro", "Data inválida! Use o formato DD/MM/YYYY.")
            return
        
        try:
            amount = CurrencyFormatter.parse_value(amount_str)
            if amount <= 0:
                raise ValueError("O valor deve ser positivo!")
        except ValueError as e:
            messagebox.showerror("Erro", f"Valor inválido: {str(e)}")
            return
        
        # Obter mês/ano
        month_year = DateValidator.get_month_year(date_str)
        
        # Inserir no banco de dados
        with DatabaseManager() as db:
            db.execute(
                "INSERT INTO expenses (date, category, description, amount, month_year) VALUES (?, ?, ?, ?, ?)",
                (date_str, category, description, amount, month_year)
            )
        
        # Limpar campos
        self.expense_amount.delete(0, tk.END)
        self.expense_desc.delete(0, tk.END)
        
        # Atualizar interface
        self.update_dashboard()
        
        # Mensagem de sucesso
        messagebox.showinfo("Sucesso", "Despesa adicionada com sucesso!")
    
    def delete_expense(self):
        """Deleta a despesa selecionada"""
        selected_item = self.expenses_tree.selection()
        if not selected_item:
            messagebox.showerror("Erro", "Selecione uma despesa para deletar!")
            return
        
        # Confirmar exclusão
        if not messagebox.askyesno("Confirmar", "Tem certeza que deseja deletar esta despesa?"):
            return
        
        # Obter ID
        expense_id = self.expenses_tree.item(selected_item, "text")
        
        # Deletar do banco de dados
        with DatabaseManager() as db:
            db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        
        # Atualizar interface
        self.update_dashboard()
        
        # Mensagem de sucesso
        messagebox.showinfo("Sucesso", "Despesa deletada com sucesso!")
    
    def add_contribution(self):
        """Adiciona uma nova entrada"""
        # Validar campos
        contribution_type = self.contribution_type.get()
        amount_str = self.contribution_amount.get().strip()
        date_str = self.contribution_date.get().strip()
        contributor = self.contribution_name.get().strip()
        
        if not contribution_type:
            messagebox.showerror("Erro", "Selecione um tipo de contribuição!")
            return
        
        if not amount_str:
            messagebox.showerror("Erro", "Informe o valor da contribuição!")
            return
        
        if not date_str:
            messagebox.showerror("Erro", "Informe a data da contribuição!")
            return
        
        if not DateValidator.validate_date(date_str):
            messagebox.showerror("Erro", "Data inválida! Use o formato DD/MM/YYYY.")
            return
        
        try:
            amount = CurrencyFormatter.parse_value(amount_str)
            if amount <= 0:
                raise ValueError("O valor deve ser positivo!")
        except ValueError as e:
            messagebox.showerror("Erro", f"Valor inválido: {str(e)}")
            return
        
        # Obter mês/ano
        month_year = DateValidator.get_month_year(date_str)
        
        # Inserir no banco de dados
        with DatabaseManager() as db:
            db.execute(
                "INSERT INTO contributions (date, type, contributor, amount, month_year) VALUES (?, ?, ?, ?, ?)",
                (date_str, contribution_type, contributor, amount, month_year)
            )
        
        # Limpar campos
        self.contribution_amount.delete(0, tk.END)
        self.contribution_name.delete(0, tk.END)
        
        # Atualizar interface
        self.update_dashboard()
        
        # Mensagem de sucesso
        messagebox.showinfo("Sucesso", "Entrada adicionada com sucesso!")
    
    def delete_contribution(self):
        """Deleta a entrada selecionada"""
        selected_item = self.contributions_tree.selection()
        if not selected_item:
            messagebox.showerror("Erro", "Selecione uma entrada para deletar!")
            return
        
        # Confirmar exclusão
        if not messagebox.askyesno("Confirmar", "Tem certeza que deseja deletar esta entrada?"):
            return
        
        # Obter ID
        contribution_id = self.contributions_tree.item(selected_item, "text")
        
        # Deletar do banco de dados
        with DatabaseManager() as db:
            db.execute("DELETE FROM contributions WHERE id = ?", (contribution_id,))
        
        # Atualizar interface
        self.update_dashboard()
        
        # Mensagem de sucesso
        messagebox.showinfo("Sucesso", "Entrada deletada com sucesso!")
    
    def generate_report(self):
        """Gera um relatório financeiro para o período selecionado"""
        # Validar datas
        start_date_str = self.report_start_date.get().strip()
        end_date_str = self.report_end_date.get().strip()
        
        if not start_date_str or not end_date_str:
            messagebox.showerror("Erro", "Informe as datas de início e fim!")
            return
        
        if not DateValidator.validate_date(start_date_str) or not DateValidator.validate_date(end_date_str):
            messagebox.showerror("Erro", "Datas inválidas! Use o formato DD/MM/YYYY.")
            return
        
        # Converter datas para comparação
        start_date = DateValidator.parse_date(start_date_str)
        end_date = DateValidator.parse_date(end_date_str)
        
        if start_date > end_date:
            messagebox.showerror("Erro", "A data de início deve ser anterior à data de fim!")
            return
        
        # Limpar treeview
        for item in self.report_tree.get_children():
            self.report_tree.delete(item)
        
        # Obter dados
        with DatabaseManager() as db:
            # Obter despesas
            db.execute(
                "SELECT id, date, 'Despesa', category, amount FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date",
                (start_date_str, end_date_str)
            )
            expenses = db.fetchall()
            
            # Obter entradas
            db.execute(
                "SELECT id, date, 'Entrada', type, amount FROM contributions WHERE date BETWEEN ? AND ? ORDER BY date",
                (start_date_str, end_date_str)
            )
            contributions = db.fetchall()
        
        # Combinar e ordenar todos os registros por data
        all_records = []
        
        # Adicionar despesas (valores negativos)
        for expense in expenses:
            all_records.append((expense[0], expense[1], expense[2], expense[3], -expense[4]))
        
        # Adicionar entradas (valores positivos)
        for contribution in contributions:
            all_records.append((contribution[0], contribution[1], contribution[2], contribution[3], contribution[4]))
        
        # Ordenar por data
        all_records.sort(key=lambda x: (x[1], x[0]))
        
        # Adicionar itens ao treeview e calcular saldo
        running_balance = 0.0
        for record in all_records:
            record_id, date, record_type, description, amount = record
            running_balance += amount
            
            self.report_tree.insert(
                "", 
                "end", 
                text=record_id, 
                values=(
                    date, 
                    record_type, 
                    description, 
                    CurrencyFormatter.format_value(abs(amount)),
                    CurrencyFormatter.format_value(running_balance)
                )
            )
        
        # Calcular totais
        total_expenses = sum(-amount for _, _, _, _, amount in all_records if amount < 0)
        total_contributions = sum(amount for _, _, _, _, amount in all_records if amount > 0)
        final_balance = total_contributions - total_expenses
        
        # Atualizar resumo
        summary_text = (
            f"Período: {start_date_str} a {end_date_str}\n"
            f"Total de Entradas: {CurrencyFormatter.format_value(total_contributions)}\n"
            f"Total de Despesas: {CurrencyFormatter.format_value(total_expenses)}\n"
            f"Saldo Final: {CurrencyFormatter.format_value(final_balance)}"
        )
        
        self.report_summary_label.config(text=summary_text)
    
    def export_report_to_csv(self):
        """Exporta o relatório atual para CSV"""
        # Verificar se há dados no relatório
        if not self.report_tree.get_children():
            messagebox.showerror("Erro", "Não há dados para exportar! Gere um relatório primeiro.")
            return
        
        # Solicitar arquivo
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*")],
            title="Exportar Relatório"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Cabeçalho
                writer.writerow(["ID", "Data", "Tipo", "Descrição", "Valor", "Saldo Acumulado"])
                
                # Dados
                for item in self.report_tree.get_children():
                    values = self.report_tree.item(item, "values")
                    row = [self.report_tree.item(item, "text")] + list(values)
                    
                    # Converter valores de volta para números
                    row[4] = CurrencyFormatter.parse_value(row[4])  # Valor
                    row[5] = CurrencyFormatter.parse_value(row[5])  # Saldo
                    
                    writer.writerow(row)
                
                # Adicionar resumo
                writer.writerow([])
                writer.writerow(["RESUMO"])
                summary_text = self.report_summary_label.cget("text").split('\n')
                for line in summary_text:
                    writer.writerow([line])
            
            messagebox.showinfo("Sucesso", f"Relatório exportado com sucesso para:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar relatório: {str(e)}")
    
    def export_to_csv(self, data_type: str):
        """Exporta dados para CSV"""
        # Obter mês atual
        month_year = self.month_var.get()
        
        # Solicitar arquivo
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*")],
            title=f"Exportar {'Despesas' if data_type == 'expenses' else 'Entradas'}"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                if data_type == "expenses":
                    # Cabeçalho
                    writer.writerow(["ID", "Data", "Categoria", "Descrição", "Valor"])
                    
                    # Dados
                    with DatabaseManager() as db:
                        db.execute(
                            "SELECT id, date, category, description, amount FROM expenses WHERE month_year = ? ORDER BY date",
                            (month_year,)
                        )
                        expenses = db.fetchall()
                        
                        for expense in expenses:
                            writer.writerow(list(expense))
                
                elif data_type == "contributions":
                    # Cabeçalho
                    writer.writerow(["ID", "Data", "Tipo", "Contribuinte", "Valor"])
                    
                    # Dados
                    with DatabaseManager() as db:
                        db.execute(
                            "SELECT id, date, type, contributor, amount FROM contributions WHERE month_year = ? ORDER BY date",
                            (month_year,)
                        )
                        contributions = db.fetchall()
                        
                        for contribution in contributions:
                            writer.writerow(list(contribution))
            
            messagebox.showinfo("Sucesso", f"Dados exportados com sucesso para:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar dados: {str(e)}")
    
    def export_data(self):
        """Exporta dados conforme seleção do usuário"""
        # Validar datas
        start_date_str = self.export_start_date.get().strip()
        end_date_str = self.export_end_date.get().strip()
        
        if not start_date_str or not end_date_str:
            messagebox.showerror("Erro", "Informe as datas de início e fim!")
            return
        
        if not DateValidator.validate_date(start_date_str) or not DateValidator.validate_date(end_date_str):
            messagebox.showerror("Erro", "Datas inválidas! Use o formato DD/MM/YYYY.")
            return
        
        # Converter datas para comparação
        start_date = DateValidator.parse_date(start_date_str)
        end_date = DateValidator.parse_date(end_date_str)
        
        if start_date > end_date:
            messagebox.showerror("Erro", "A data de início deve ser anterior à data de fim!")
            return
        
        # Solicitar arquivo
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*")],
            title="Exportar Dados"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                export_type = self.export_type.get()
                
                if export_type == "all" or export_type == "expenses":
                    # Cabeçalho de despesas
                    writer.writerow(["DESPESAS"])
                    writer.writerow(["ID", "Data", "Categoria", "Descrição", "Valor"])
                    
                    # Dados de despesas
                    with DatabaseManager() as db:
                        db.execute(
                            "SELECT id, date, category, description, amount FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date",
                            (start_date_str, end_date_str)
                        )
                        expenses = db.fetchall()
                        
                        for expense in expenses:
                            writer.writerow(list(expense))
                    
                    # Linha em branco
                    writer.writerow([])
                
                if export_type == "all" or export_type == "contributions":
                    # Cabeçalho de entradas
                    writer.writerow(["ENTRADAS"])
                    writer.writerow(["ID", "Data", "Tipo", "Contribuinte", "Valor"])
                    
                    # Dados de entradas
                    with DatabaseManager() as db:
                        db.execute(
                            "SELECT id, date, type, contributor, amount FROM contributions WHERE date BETWEEN ? AND ? ORDER BY date",
                            (start_date_str, end_date_str)
                        )
                        contributions = db.fetchall()
                        
                        for contribution in contributions:
                            writer.writerow(list(contribution))
            
            messagebox.showinfo("Sucesso", f"Dados exportados com sucesso para:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar dados: {str(e)}")
    
    def on_closing(self):
        """Ação ao fechar a aplicação"""
        if messagebox.askokcancel("Sair", "Deseja realmente sair do sistema?"):
            self.root.destroy()


# Inicialização da aplicação
if __name__ == "__main__":
    root = tk.Tk()
    app = IBVRDFinanceApp(root)
    root.mainloop()