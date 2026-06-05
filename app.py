#========================================
# IMPORTS
#========================================

import os
import sys
import yaml
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path

from src.assinatura import rodar_automacao

#========================================
# PATHS
#========================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / 'config.yaml'
CONFIG_EXEMPLO_PATH = BASE_DIR / 'config.yaml.example'


#========================================
# Captura de stdout para exibir no log da GUI
#========================================

class LogCapture:
    """Redireciona stdout/stderr para uma callback (ex: log da GUI)."""
    def __init__(self, callback):
        self.callback = callback

    def write(self, text):
        if text.strip():
            self.callback(text.rstrip('\n\r'))

    def flush(self):
        pass


#========================================
# Utilitários YAML
#========================================

def carregar_config():
    path = CONFIG_PATH
    if not path.exists():
        if CONFIG_EXEMPLO_PATH.exists():
            path.write_text(CONFIG_EXEMPLO_PATH.read_text(encoding='utf-8'), encoding='utf-8')
        else:
            path.write_text("""usuario:
  nome: 'Fulano'
  cpf: '12345678900'

certificado:
  nome: 'Fulano'
  cpf: '12345678900'

navegador:
  url:
    login: 'https://sign.app.dimensa.com.br/adminsign/login'
    dashboard: 'https://sign.app.dimensa.com.br/adminsign/dashboard'
    api: 'https://api.assina.rbm.digital'
  profile:
    path: './user_profile'
    name: 'Selenium'
  pausas:
    login: 5

api_servidor:
    documentos_por_requisicao: 3000

assinatura:
  filtros:
    data_inicial: '01/05/2026'
    data_final: '30/05/2026'
    tag: 
    titulo:
  fluxo:
    ordem_signatarios:
  lote:
    tamanho: 10

controle_bot:
  pausas:
    espera_elemento: 60
    minima: 2
    maxima: 4

test_mode: false

mock_web: false
mock_scenario: normal
mock_delay: 0
""", encoding='utf-8')

    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def salvar_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        f.flush()
        os.fsync(f.fileno())


#========================================
# Janela Principal
#========================================

class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Automação de Assinatura de Lotes')
        self.minsize(600, 540)
        largura = 600
        altura = 680
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()
        posicao_x = int((largura_tela / 2) - (largura / 2))
        posicao_y = int((altura_tela / 2) - (altura / 2))
        self.geometry(f"{largura}x{altura}+{posicao_x}+{posicao_y}")

        self.config = carregar_config()
        self._running = False
        self._thread = None

        self._menu()
        self._widgets()
        self._carregar_campos()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    #========================================
    # Menu
    #========================================

    def _menu(self):
        menubar = tk.Menu(self)

        menu_arquivo = tk.Menu(menubar, tearoff=False)
        menu_arquivo.add_command(label='Carregar Configuração', command=self._carregar_de_arquivo)
        menu_arquivo.add_command(label='Salvar Configuração como...', command=self._salvar_como)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label='Recarregar Padrão', command=self._recarregar_padrao)
        menubar.add_cascade(label='Arquivo', menu=menu_arquivo)

        menu_avancado = tk.Menu(menubar, tearoff=False)
        menu_avancado.add_command(label='Abrir Configurações Avançadas...', command=self._abrir_avancadas)
        menubar.add_cascade(label='Configurações', menu=menu_avancado)

        menu_ajuda = tk.Menu(menubar, tearoff=False)
        menu_ajuda.add_command(label='Sobre', command=self._sobre)
        menubar.add_cascade(label='Ajuda', menu=menu_ajuda)

        self.configure(menu=menubar)

    #========================================
    # Widgets
    #========================================

    def _widgets(self):
        pad = {'padx': 10, 'pady': 6}

        # Filtros (Grid de 2 Colunas)
        filtros = ttk.LabelFrame(self, text='Filtros')
        filtros.pack(fill='x', **pad, ipady=5) # type: ignore

        filtros.columnconfigure(0, weight=1)
        filtros.columnconfigure(1, weight=1)

        # Coluna 1: Datas
        frame_di = ttk.Frame(filtros)
        frame_di.grid(row=0, column=0, sticky='ew', padx=(10, 20), pady=4)
        frame_di.columnconfigure(1, weight=1)

        lbl_di = ttk.Label(frame_di, text='Data Inicial:', width=12, anchor='w')
        lbl_di.grid(row=0, column=0, sticky='w')
        self.ent_data_inicial = ttk.Entry(frame_di)
        self.ent_data_inicial.grid(row=0, column=1, sticky='ew')

        frame_df = ttk.Frame(filtros)
        frame_df.grid(row=1, column=0, sticky='ew', padx=(10, 20), pady=4)
        frame_df.columnconfigure(1, weight=1)

        lbl_df = ttk.Label(frame_df, text='Data Final:', width=12, anchor='w')
        lbl_df.grid(row=0, column=0, sticky='w')
        self.ent_data_final = ttk.Entry(frame_df)
        self.ent_data_final.grid(row=0, column=1, sticky='ew')

        # Coluna 2: Metadados
        frame_tag = ttk.Frame(filtros)
        frame_tag.grid(row=0, column=1, sticky='ew', padx=(0, 10), pady=4)
        frame_tag.columnconfigure(1, weight=1)

        lbl_tag = ttk.Label(frame_tag, text='Tag:', width=8, anchor='w')
        lbl_tag.grid(row=0, column=0, sticky='w')
        self.ent_tag = ttk.Entry(frame_tag)
        self.ent_tag.grid(row=0, column=1, sticky='ew')

        frame_tit = ttk.Frame(filtros)
        frame_tit.grid(row=1, column=1, sticky='ew', padx=(0, 10), pady=4)
        frame_tit.columnconfigure(1, weight=1)

        lbl_tit = ttk.Label(frame_tit, text='Título:', width=8, anchor='w')
        lbl_tit.grid(row=0, column=0, sticky='w')
        self.ent_titulo = ttk.Entry(frame_tit)
        self.ent_titulo.grid(row=0, column=1, sticky='ew')

        # Botões
        botoes = ttk.Frame(self)
        botoes.pack(fill='x', **pad) # type: ignore

        self.btn_executar = ttk.Button(botoes, text='▶ Executar Automação', command=self._executar)
        self.btn_executar.pack(side='left', padx=(0, 6))

        self.btn_parar = ttk.Button(botoes, text='⏹ Parar', command=self._parar, state='disabled')
        self.btn_parar.pack(side='left', padx=6)

        self.btn_limpar = ttk.Button(botoes, text='Limpar Log', command=self._limpar_log)
        self.btn_limpar.pack(side='right')

        # Log
        log_frame = ttk.LabelFrame(self, text='Log da Automação', padding=4)
        log_frame.pack(fill='both', expand=True, **pad) # type: ignore

        self.log_text = tk.Text(log_frame, height=14, wrap='word', state='disabled',
                                font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4',
                                insertbackground='white')
        scroll = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)

        self.log_text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

    #========================================
    # Carregar Campos do Config
    #========================================

    def _carregar_campos(self):
        filtros = self.config.get('assinatura', {}).get('filtros', {})

        self._set_text(self.ent_data_inicial, filtros.get('data_inicial', ''))
        self._set_text(self.ent_data_final, filtros.get('data_final', ''))
        self._set_text(self.ent_tag, filtros.get('tag', '') or '')
        self._set_text(self.ent_titulo, filtros.get('titulo', '') or '')

    def _ler_campos_filtros(self):
        assinatura = self.config.setdefault('assinatura', {})
        filtros = assinatura.setdefault('filtros', {})

        data_inicial = self.ent_data_inicial.get().strip()
        if data_inicial:
            data_limpa = ''.join(char for char in data_inicial if char.isdigit())
            if len(data_limpa) == 8:
                data_corrigida = f"{data_limpa[:2]}/{data_limpa[2:4]}/{data_limpa[4:]}"
                self.ent_data_inicial.delete(0, tk.END)
                self.ent_data_inicial.insert(0, data_corrigida)
                data_inicial = data_corrigida
            try:
                datetime.strptime(data_inicial, '%d/%m/%Y')
            except ValueError:
                messagebox.showerror('Erro', 'Data Inicial deve estar no formato dd/mm/aaaa')
                return None

        data_final = self.ent_data_final.get().strip()
        if data_final:
            data_limpa = ''.join(char for char in data_final if char.isdigit())
            if len(data_limpa) == 8:
                data_corrigida = f"{data_limpa[:2]}/{data_limpa[2:4]}/{data_limpa[4:]}"
                self.ent_data_final.delete(0, tk.END)
                self.ent_data_final.insert(0, data_corrigida)
                data_final = data_corrigida
            try:
                datetime.strptime(data_final, '%d/%m/%Y')
            except ValueError:
                messagebox.showerror('Erro', 'Data Final deve estar no formato dd/mm/aaaa')
                return None

        filtros['data_inicial'] = data_inicial
        filtros['data_final'] = data_final
        filtros['tag'] = self.ent_tag.get().strip() or None
        filtros['titulo'] = self.ent_titulo.get().strip() or None

        return self.config

    #========================================
    # Ações
    #========================================

    def _executar(self):
        if self._running:
            return

        configuracoes = self._ler_campos_filtros()
        if configuracoes is None:
            return

        salvar_config(configuracoes)
        self.config = configuracoes

        self._running = True
        self._thread = None
        self._stop_event = threading.Event()
        self.btn_executar.configure(state='disabled', text='▶ Executando...')
        self.btn_parar.configure(state='normal')
        self._log('[INFO] Iniciando automação...')

        # Roda em thread separada para não travar a GUI
        self._thread = threading.Thread(target=self._rodar_automacao, daemon=True)
        self._thread.start()

    def _rodar_automacao(self):
        """
        Executa a automação dentro da mesma thread, redirecionando
        stdout/stderr para o log da GUI.
        """
        old_cwd = os.getcwd()
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        try:
            # Redireciona saídas para o log
            sys.stdout = LogCapture(self._log)
            sys.stderr = LogCapture(self._log)

            # Muda para o diretório base (logs, relatorios, config.yaml)
            os.chdir(str(BASE_DIR))

            # Executa o módulo de automação
            rodar_automacao(self.config, stop_event=self._stop_event)

            # Se chegou aqui sem sys.exit, foi sucesso
            self._log('[✓] Automação concluída com sucesso!')

        except SystemExit as e:
            # sys.exit(codigo) — 0 = sucesso, !=0 = erro
            codigo = e.code if e.code else 0
            if codigo == 0:
                self._log('[✓] Automação concluída com sucesso!')
            else:
                self._log(f'[✗] Automação encerrada com código {codigo}')

        except Exception as e:
            self._log(f'[ERRO] {e}')
            import traceback
            for line in traceback.format_exc().splitlines():
                self._log(f'[DEBUG] {line}')

        finally:
            os.chdir(old_cwd)
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, self._finalizar_execucao)

    def _finalizar_execucao(self):
        self._running = False
        self._thread = None
        self.btn_executar.configure(state='normal', text='▶ Executar Automação')
        self.btn_parar.configure(state='disabled')

    def _parar(self):
        """Sinaliza parada via threading.Event (lido pelo módulo a cada lote)."""
        if self._running and self._stop_event:
            self._log('[WARNING] Solicitando parada... (a automação será interrompida ao final do lote atual)')
            self._stop_event.set()

    def _limpar_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    #========================================
    # Configurações Avançadas
    #========================================

    def _abrir_avancadas(self):
        DialogAvancadas(self, dict(self.config))

    #========================================
    # Arquivo
    #========================================

    def _carregar_de_arquivo(self):
        path = filedialog.askopenfilename(
            title='Selecionar arquivo de configuração',
            filetypes=[('YAML', '*.yaml *.yml'), ('Todos', '*.*')],
            initialdir=str(BASE_DIR),
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            self._carregar_campos()
            self._log(f'[INFO] Configuração carregada de: {path}')
        except Exception as e:
            messagebox.showerror('Erro', f'Falha ao carregar configuração:\n{e}')

    def _salvar_como(self):
        cfg = self._ler_campos_filtros()
        if cfg is None:
            return
        path = filedialog.asksaveasfilename(
            title='Salvar configuração como',
            defaultextension='.yaml',
            filetypes=[('YAML', '*.yaml'), ('Todos', '*.*')],
            initialdir=str(BASE_DIR),
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            self._log(f'[INFO] Configuração salva em: {path}')
        except Exception as e:
            messagebox.showerror('Erro', f'Falha ao salvar:\n{e}')

    def _recarregar_padrao(self):
        if messagebox.askyesno('Confirmar', 'Recarregar configuração padrão?\nAs alterações atuais serão perdidas.'):
            self.config = carregar_config()
            self._carregar_campos()
            self._log('[INFO] Configuração recarregada')

    #========================================
    # Helpers
    #========================================

    @staticmethod
    def _set_text(entry, value):
        entry.delete(0, 'end')
        entry.insert(0, value)

    def _log(self, texto):
        def append():
            self.log_text.configure(state='normal')
            self.log_text.insert('end', texto + '\n')
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
        self.after(0, append)

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno('Atenção', 'Automação em execução. Deseja encerrar mesmo assim?'):
                return
            self._parar()
        self.destroy()

    def _sobre(self):
        messagebox.showinfo(
            'Sobre',
            'Automação de Assinatura em Lote\n\n'
            'Versão: 2.0\n'
            'Plataforma: DimensaSign\n\n'
            'Configurações avançadas disponíveis no menu Configurações.'
        )


#========================================
# Diálogo de Configurações Avançadas
#========================================

class DialogAvancadas(tk.Toplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.result = None

        self.title('Configurações Avançadas')
        self.geometry('620x480')
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._widgets()
        self._carregar()
        self._centralizar()

        self.wait_window()

    # ── helpers internos ──────────────────────────────────────────

    @staticmethod
    def _criar_secao(parent, texto, row, columnspan=2):
        """Label em negrito + separator horizontal."""
        sep = ttk.Separator(parent, orient='horizontal')
        sep.grid(row=row, column=0, columnspan=columnspan, sticky='ew', pady=(8, 2))
        lbl = ttk.Label(parent, text=texto, font=('', 9, 'bold'))
        lbl.grid(row=row + 1, column=0, columnspan=columnspan, sticky='w', pady=(0, 4))
        return row + 2  # próxima linha livre

    @staticmethod
    def _add_row(parent, row, label, widget=None, btn_text=None, btn_cmd=None, nota=''):
        """Adiciona uma linha label + widget opcional + botão opcional."""
        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=0, sticky='w', pady=3, padx=(12, 0))

        col = 1

        if btn_text and btn_cmd:
            # Sub-frame com Entry + botão (não grida widget no parent antes)
            f = ttk.Frame(parent)
            f.grid(row=row, column=col, sticky='ew', padx=(6, 0), pady=3)
            f.columnconfigure(0, weight=1)
            if widget is not None:
                widget.grid(in_=f, row=0, column=0, sticky='ew')
            ttk.Button(f, text=btn_text, width=3, command=btn_cmd).grid(
                row=0, column=1, padx=(3, 0))
        elif widget is not None:
            widget.grid(row=row, column=col, sticky='ew', padx=(6, 0), pady=3)

        if nota:
            n = ttk.Label(parent, text=nota, font=('', 8), foreground='#888')
            n.grid(row=row + 1, column=1, sticky='w', padx=(6, 0))

        return row + 1

    # ── construção ────────────────────────────────────────────────

    def _widgets(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill='both', expand=True)

        notebook = ttk.Notebook(main)
        notebook.pack(fill='both', expand=True)

        # =============================================================
        # ABA 1 — CREDENCIAIS
        # =============================================================
        frame_id = ttk.Frame(notebook, padding=12)
        notebook.add(frame_id, text='Credenciais')
        frame_id.columnconfigure(1, weight=1)

        ttk.Label(frame_id, text='Usuário', font=('', 9, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))

        self.id_usuario_nome = ttk.Entry(frame_id)
        self._add_row(frame_id, 1, 'Nome:', widget=self.id_usuario_nome)
        self.id_usuario_cpf = ttk.Entry(frame_id)
        self._add_row(frame_id, 2, 'CPF:', widget=self.id_usuario_cpf)

        row = self._criar_secao(frame_id, 'Certificado', row=4)

        self.id_certificado_nome = ttk.Entry(frame_id)
        self._add_row(frame_id, row, 'Nome:', widget=self.id_certificado_nome)
        self.id_certificado_cpf = ttk.Entry(frame_id)
        self._add_row(frame_id, row + 1, 'CPF:', widget=self.id_certificado_cpf)

        # =============================================================
        # ABA 2 — NAVEGADOR
        # =============================================================
        frame_nav = ttk.Frame(notebook, padding=12)
        notebook.add(frame_nav, text='Navegador')
        frame_nav.columnconfigure(1, weight=1)

        ttk.Label(frame_nav, text='URLs', font=('', 9, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))

        self.nav_url_login = ttk.Entry(frame_nav)
        self._add_row(frame_nav, 1, 'Login:', widget=self.nav_url_login)
        self.nav_url_dashboard = ttk.Entry(frame_nav)
        self._add_row(frame_nav, 2, 'Dashboard:', widget=self.nav_url_dashboard)
        self.nav_url_api = ttk.Entry(frame_nav)
        self._add_row(frame_nav, 3, 'API:', widget=self.nav_url_api)

        row = self._criar_secao(frame_nav, 'Perfil do Navegador', row=5)

        # Sub-frame manual: Entry + botão ... (Entry criado dentro da sub-frame)
        row_path = ttk.Frame(frame_nav)
        row_path.grid(row=row, column=1, sticky='ew', padx=(6, 0), pady=3)
        row_path.columnconfigure(0, weight=1)
        self.nav_profile_path = ttk.Entry(row_path)
        self.nav_profile_path.grid(row=0, column=0, sticky='ew')
        ttk.Button(row_path, text='...', width=3,
                   command=self._escolher_pasta_navegador).grid(row=0, column=1, padx=(3, 0))
        ttk.Label(frame_nav, text='Caminho:').grid(
            row=row, column=0, sticky='w', pady=3, padx=(12, 0))
        self.nav_profile_name = ttk.Entry(frame_nav)
        self._add_row(frame_nav, row + 1, 'Nome:', widget=self.nav_profile_name)

        row = self._criar_secao(frame_nav, 'Conexão', row=row + 3)

        self.nav_pausa_login = ttk.Entry(frame_nav)
        self._add_row(frame_nav, row, 'Pausa pós-login (s):', widget=self.nav_pausa_login)

        row = self._criar_secao(frame_nav, 'Modo de Teste', row=row + 2)

        self.nav_test_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame_nav,
            text='🧪 Modo de Teste (simula o portal sem acessar DimensaSign)',
            variable=self.nav_test_mode_var
        ).grid(row=row, column=0, columnspan=2, sticky='w', pady=3)

        self.nav_mock_web_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame_nav,
            text='🌐 Mock Web (abre navegador de verdade em páginas locais)',
            variable=self.nav_mock_web_var
        ).grid(row=row + 1, column=0, columnspan=2, sticky='w', pady=(0, 3))
        ttk.Label(frame_nav, text='requer Modo de Teste ativado',
                  font=('', 8), foreground='#888').grid(
            row=row + 2, column=0, columnspan=2, sticky='w', padx=(24, 0))

        # =============================================================
        # ABA 3 — COMPORTAMENTO
        # =============================================================
        frame_comp = ttk.Frame(notebook, padding=12)
        notebook.add(frame_comp, text='Comportamento')
        frame_comp.columnconfigure(1, weight=1)

        ttk.Label(frame_comp, text='Pausas', font=('', 9, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))

        self.comp_espera_elemento = ttk.Entry(frame_comp)
        self._add_row(frame_comp, 1, 'Espera por elemento (s):', widget=self.comp_espera_elemento,
                      nota='tempo máximo que o Selenium espera um elemento aparecer')
        self.comp_pausa_minima = ttk.Entry(frame_comp)
        self._add_row(frame_comp, 2, 'Pausa mínima (s):', widget=self.comp_pausa_minima,
                      nota='entre ações do bot')
        self.comp_pausa_maxima = ttk.Entry(frame_comp)
        self._add_row(frame_comp, 3, 'Pausa máxima (s):', widget=self.comp_pausa_maxima,
                      nota='entre ações do bot')

        row = self._criar_secao(frame_comp, 'Requisição', row=5)

        self.comp_docs_por_req = ttk.Entry(frame_comp)
        self._add_row(frame_comp, row, 'Docs por requisição:', widget=self.comp_docs_por_req,
                      nota='quantos documentos buscar por página da API')

        row = self._criar_secao(frame_comp, 'Simulação (Mock)', row=row + 2)

        self.comp_mock_scenario = ttk.Combobox(
            frame_comp, values=['normal', 'empty', 'minimal', 'expired_certs'],
            state='readonly', width=18)
        self._add_row(frame_comp, row, 'Cenário:', widget=self.comp_mock_scenario,
                      nota='normal=15 docs · empty=0 · minimal=1 · expired_certs=5')

        self.comp_mock_delay = ttk.Entry(frame_comp)
        self._add_row(frame_comp, row + 1, 'Delay simulado (s):', widget=self.comp_mock_delay,
                      nota='latência artificial do mock (útil p/ testar timeouts)')

        # =============================================================
        # ABA 4 — ASSINATURA
        # =============================================================
        frame_ass = ttk.Frame(notebook, padding=12)
        notebook.add(frame_ass, text='Assinatura')
        frame_ass.columnconfigure(1, weight=1)

        ttk.Label(frame_ass, text='Lote', font=('', 9, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))

        self.ass_lote_tamanho = ttk.Entry(frame_ass)
        self._add_row(frame_ass, 1, 'Tamanho do lote:', widget=self.ass_lote_tamanho,
                      nota='documentos por lote de assinatura')

        row = self._criar_secao(frame_ass, 'Fluxo', row=3)

        self.ass_ordem_signatarios = ttk.Entry(frame_ass)
        self._add_row(frame_ass, row, 'Ordem dos signatários:', widget=self.ass_ordem_signatarios,
                      nota='separado por vírgulas, ex: "emissor,cliente"')

        # =============================================================
        # Botões
        # =============================================================
        botoes = ttk.Frame(main)
        botoes.pack(fill='x', pady=(12, 0))

        ttk.Button(botoes, text='Salvar', command=self._salvar).pack(side='right', padx=(6, 0))
        ttk.Button(botoes, text='Cancelar', command=self.destroy).pack(side='right')

    # ── carregar valores do config → widgets ──────────────────────

    def _carregar(self):
        cfg = self.config

        usuario = cfg.get('usuario', {})
        self.id_usuario_nome.insert(0, usuario.get('nome', ''))
        self.id_usuario_cpf.insert(0, usuario.get('cpf', ''))

        certificado = cfg.get('certificado', {})
        self.id_certificado_nome.insert(0, certificado.get('nome', ''))
        self.id_certificado_cpf.insert(0, certificado.get('cpf', ''))

        nav = cfg.get('navegador', {})
        url = nav.get('url', {})
        self.nav_url_login.insert(0, url.get('login', ''))
        self.nav_url_dashboard.insert(0, url.get('dashboard', ''))
        self.nav_url_api.insert(0, url.get('api', ''))

        profile = nav.get('profile', {})
        self.nav_profile_path.insert(0, profile.get('path', './user_profile'))
        self.nav_profile_name.insert(0, profile.get('name', 'Selenium'))

        pausas_nav = nav.get('pausas', {})
        self.nav_pausa_login.insert(0, pausas_nav.get('login', '5'))
        self.comp_espera_elemento.insert(0, pausas_nav.get('espera_elemento', '60'))

        api_srv = cfg.get('api_servidor', {})
        self.comp_docs_por_req.insert(0, str(api_srv.get('documentos_por_requisicao', '3000')))

        ass = cfg.get('assinatura', {})
        fluxo = ass.get('fluxo', {})
        sequencia = fluxo.get('ordem_signatarios', '')
        if isinstance(sequencia, list):
            sequencia = ', '.join(sequencia)
        self.ass_ordem_signatarios.insert(0, sequencia or '')

        lote = ass.get('lote', {})
        self.ass_lote_tamanho.insert(0, str(lote.get('tamanho', '10')))

        ctl = cfg.get('controle_bot', {})
        pausas_ctl = ctl.get('pausas', {})
        self.comp_pausa_minima.insert(0, pausas_ctl.get('minima', '2'))
        self.comp_pausa_maxima.insert(0, pausas_ctl.get('maxima', '4'))

        # Modo de Teste
        self.nav_test_mode_var.set(cfg.get('test_mode', False))
        self.nav_mock_web_var.set(cfg.get('mock_web', False))

        # Mock
        scenario = cfg.get('mock_scenario', 'normal')
        self.comp_mock_scenario.set(scenario)
        self.comp_mock_delay.insert(0, str(cfg.get('mock_delay', '0')))

    # ── salvar widgets → config ──────────────────────────────────

    def _salvar(self):
        cfg = self.config

        # Identidade
        cfg.setdefault('usuario', {})
        cfg['usuario']['nome'] = self.id_usuario_nome.get().strip()
        cfg['usuario']['cpf'] = self.id_usuario_cpf.get().strip()

        cfg.setdefault('certificado', {})
        cfg['certificado']['nome'] = self.id_certificado_nome.get().strip()
        cfg['certificado']['cpf'] = self.id_certificado_cpf.get().strip()

        # Navegador
        cfg.setdefault('navegador', {})
        cfg['navegador'].setdefault('url', {})
        cfg['navegador']['url']['login'] = self.nav_url_login.get().strip()
        cfg['navegador']['url']['dashboard'] = self.nav_url_dashboard.get().strip()
        cfg['navegador']['url']['api'] = self.nav_url_api.get().strip()

        cfg['navegador'].setdefault('profile', {})
        cfg['navegador']['profile']['path'] = self.nav_profile_path.get().strip()
        cfg['navegador']['profile']['name'] = self.nav_profile_name.get().strip()

        cfg['navegador'].setdefault('pausas', {})
        try:
            cfg['navegador']['pausas']['login'] = int(self.nav_pausa_login.get().strip() or 5)
            cfg['navegador']['pausas']['espera_elemento'] = int(self.comp_espera_elemento.get().strip() or 60)
        except ValueError:
            messagebox.showerror('Erro', 'Pausas devem ser números inteiros', parent=self)
            return

        # API Servidor (mesma chave de sempre)
        cfg.setdefault('api_servidor', {})
        try:
            cfg['api_servidor']['documentos_por_requisicao'] = int(self.comp_docs_por_req.get().strip() or 3000)
        except ValueError:
            messagebox.showerror('Erro', 'Documentos por requisição deve ser um número inteiro', parent=self)
            return

        # Assinatura
        cfg.setdefault('assinatura', {})
        cfg['assinatura'].setdefault('fluxo', {})
        cfg['assinatura'].setdefault('lote', {})
        ordem_raw = self.ass_ordem_signatarios.get().strip()
        if ordem_raw:
            cfg['assinatura']['fluxo']['ordem_signatarios'] = [x.strip() for x in ordem_raw.split(',') if x.strip()]
        else:
            cfg['assinatura']['fluxo']['ordem_signatarios'] = []

        try:
            cfg['assinatura']['lote']['tamanho'] = int(self.ass_lote_tamanho.get().strip() or 10)
        except ValueError:
            messagebox.showerror('Erro', 'O tamanho do lote deve ser um número inteiro', parent=self)
            return

        # Controle do Bot (mesmas chaves)
        cfg.setdefault('controle_bot', {})
        cfg['controle_bot'].setdefault('pausas', {})
        try:
            cfg['controle_bot']['pausas']['minima'] = int(self.comp_pausa_minima.get().strip() or 2)
            cfg['controle_bot']['pausas']['maxima'] = int(self.comp_pausa_maxima.get().strip() or 4)
        except ValueError:
            messagebox.showerror('Erro', 'Pausas do bot devem ser números inteiros', parent=self)
            return

        # Modo de Teste
        cfg['test_mode'] = self.nav_test_mode_var.get()
        cfg['mock_web'] = self.nav_mock_web_var.get()

        # Mock scenario / delay
        cfg['mock_scenario'] = self.comp_mock_scenario.get()
        cfg['mock_delay'] = int(self.comp_mock_delay.get().strip() or 0)

        self.parent.config = cfg
        salvar_config(cfg)
        self.parent._carregar_campos()
        self.parent._log('[INFO] Configurações avançadas salvas')

        self.destroy()

    def _escolher_pasta_navegador(self):
        pasta = filedialog.askdirectory(
            title='Selecionar diretório do profile do navegador',
            parent=self,
        )
        if pasta:
            self.nav_profile_path.delete(0, 'end')
            self.nav_profile_path.insert(0, pasta)

    def _centralizar(self):
        self.update_idletasks()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        px = self.master.winfo_x()
        py = self.master.winfo_y()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f'{w}x{h}+{x}+{y}')


#========================================
# FIM
#========================================
if __name__ == '__main__':
    app = LauncherApp()
    app.mainloop()