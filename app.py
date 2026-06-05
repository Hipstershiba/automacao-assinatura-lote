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
            rodar_automacao(self.config)

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
        """Sinaliza parada via arquivo temporário (lido pelo módulo a cada lote)."""
        if self._running:
            self._log('[WARNING] Solicitando parada... (a automação será interrompida ao final do lote atual)')
            try:
                Path(BASE_DIR / 'sinal_parar.tmp').touch()
            except Exception as e:
                self._log(f'[WARNING] Erro ao criar sinal de parada: {e}')

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
        self.geometry('580x440')
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._widgets()
        self._carregar()
        self._centralizar()

        self.wait_window()

    def _widgets(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill='both', expand=True)

        notebook = ttk.Notebook(main)
        notebook.pack(fill='both', expand=True)

        # Aba Usuário
        frame_usuario = ttk.Frame(notebook, padding=12)
        notebook.add(frame_usuario, text='Usuário')
        frame_usuario.columnconfigure(1, weight=1)

        ttk.Label(frame_usuario, text='Nome:').grid(row=0, column=0, sticky='w', pady=3)
        self.usuario_nome = ttk.Entry(frame_usuario)
        self.usuario_nome.grid(row=0, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_usuario, text='CPF:').grid(row=1, column=0, sticky='w', pady=3)
        self.usuario_cpf = ttk.Entry(frame_usuario)
        self.usuario_cpf.grid(row=1, column=1, sticky='ew', padx=(6, 0), pady=3)

        # Aba Certificado
        frame_certificado = ttk.Frame(notebook, padding=12)
        notebook.add(frame_certificado, text='certificado')
        frame_certificado.columnconfigure(1, weight=1)

        ttk.Label(frame_certificado, text='Nome:').grid(row=0, column=0, sticky='w', pady=3)
        self.certificado_nome = ttk.Entry(frame_certificado)
        self.certificado_nome.grid(row=0, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_certificado, text='CPF:').grid(row=1, column=0, sticky='w', pady=3)
        self.certificado_cpf = ttk.Entry(frame_certificado)
        self.certificado_cpf.grid(row=1, column=1, sticky='ew', padx=(6, 0), pady=3)

        # Aba Navegador
        frame_navegador = ttk.Frame(notebook, padding=12)
        notebook.add(frame_navegador, text='Navegador')
        frame_navegador.columnconfigure(1, weight=1)

        ttk.Label(frame_navegador, text='URLs:').grid(row=0, column=0, sticky='w', pady=3)

        ttk.Label(frame_navegador, text='Login:').grid(row=1, column=0, sticky='w', pady=3, padx=(12, 0))
        self.url_login = ttk.Entry(frame_navegador)
        self.url_login.grid(row=1, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_navegador, text='Dashboard:').grid(row=2, column=0, sticky='w', pady=3, padx=(12, 0))
        self.url_dashboard = ttk.Entry(frame_navegador)
        self.url_dashboard.grid(row=2, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_navegador, text='API:').grid(row=3, column=0, sticky='w', pady=3, padx=(12, 0))
        self.url_api = ttk.Entry(frame_navegador)
        self.url_api.grid(row=3, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_navegador, text='Perfil:').grid(row=4, column=0, sticky='w', pady=3)

        ttk.Label(frame_navegador, text='Caminho:').grid(row=5, column=0, sticky='w', pady=3, padx=(12, 0))
        row_navegador_path = ttk.Frame(frame_navegador)
        row_navegador_path.grid(row=5, column=1, sticky='ew', padx=(6, 0), pady=3)
        row_navegador_path.columnconfigure(0, weight=1)
        self.profile_path = ttk.Entry(row_navegador_path)
        self.profile_path.grid(row=0, column=0, sticky='ew')
        ttk.Button(row_navegador_path, text='...', width=3,
                   command=self._escolher_pasta_navegador).grid(row=0, column=1, padx=(3, 0))

        ttk.Label(frame_navegador, text='Nome:').grid(row=6, column=0, sticky='w', pady=3, padx=(12, 0))
        self.profile_name = ttk.Entry(frame_navegador)
        self.profile_name.grid(row=6, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_navegador, text='Pausas:').grid(row=7, column=0, sticky='w', pady=3)

        ttk.Label(frame_navegador, text='Login:').grid(row=8, column=0, sticky='w', pady=3, padx=(12, 0))
        self.pausa_login = ttk.Entry(frame_navegador)
        self.pausa_login.grid(row=8, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_navegador, text='Espera Elemento:').grid(row=9, column=0, sticky='w', pady=3, padx=(12, 0))
        self.pausa_espera_elemento = ttk.Entry(frame_navegador)
        self.pausa_espera_elemento.grid(row=9, column=1, sticky='ew', padx=(6, 0), pady=3)

        # Espaçador
        ttk.Separator(frame_navegador, orient='horizontal').grid(
            row=10, column=0, columnspan=2, sticky='ew', pady=8)

        # Modo de Teste
        self.test_mode_var = tk.BooleanVar(value=False)
        self.chk_test_mode = ttk.Checkbutton(
            frame_navegador, text='🧪 Modo de Teste (simula o portal sem acessar DimensaSign)',
            variable=self.test_mode_var
        )
        self.chk_test_mode.grid(row=11, column=0, columnspan=2, sticky='w', pady=3)

        # Aba API Servidor
        frame_api = ttk.Frame(notebook, padding=12)
        notebook.add(frame_api, text='API Servidor')
        frame_api.columnconfigure(1, weight=1)

        ttk.Label(frame_api, text='Documentos por requisição:').grid(row=0, column=0, sticky='w', pady=3)
        self.tamanho_requisicao = ttk.Entry(frame_api)
        self.tamanho_requisicao.grid(row=0, column=1, sticky='ew', padx=(6, 0), pady=3)

        # Aba Assinatura
        frame_assinatura = ttk.Frame(notebook, padding=12)
        notebook.add(frame_assinatura, text='Assinatura')
        frame_assinatura.columnconfigure(1, weight=1)

        ttk.Label(frame_assinatura, text='Tamanho do lote').grid(row=0, column=0, sticky='w', pady=3)
        self.lote_tamanho = ttk.Entry(frame_assinatura)
        self.lote_tamanho.grid(row=0, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_assinatura, text='Ordem de assinatura:').grid(row=1, column=0, sticky='w', pady=3)
        self.ordem_signatarios = ttk.Entry(frame_assinatura)
        self.ordem_signatarios.grid(row=1, column=1, sticky='ew', padx=(6, 0), pady=3)
        ttk.Label(frame_assinatura, text='separado por vírgulas, ex: "emissor,cliente"').grid(
            row=2, column=1, sticky='w', padx=(6, 0))

        # Aba Controle do Bot
        frame_controle = ttk.Frame(notebook, padding=12)
        notebook.add(frame_controle, text='Controle do Bot')
        frame_controle.columnconfigure(1, weight=1)

        ttk.Label(frame_controle, text='Pausas entre ações:').grid(row=0, column=0, sticky='w', pady=3)

        ttk.Label(frame_controle, text='Mínima:').grid(row=1, column=0, sticky='w', pady=3, padx=(12, 0))
        self.pausa_minima = ttk.Entry(frame_controle)
        self.pausa_minima.grid(row=1, column=1, sticky='ew', padx=(6, 0), pady=3)

        ttk.Label(frame_controle, text='Máxima:').grid(row=2, column=0, sticky='w', pady=3, padx=(12, 0))
        self.pausa_maxima = ttk.Entry(frame_controle)
        self.pausa_maxima.grid(row=2, column=1, sticky='ew', padx=(6, 0), pady=3)

        # Botões
        botoes = ttk.Frame(main)
        botoes.pack(fill='x', pady=(12, 0))

        ttk.Button(botoes, text='Salvar', command=self._salvar).pack(side='right', padx=(6, 0))
        ttk.Button(botoes, text='Cancelar', command=self.destroy).pack(side='right')

    def _carregar(self):
        config = self.config

        usuario = config.get('usuario', {})
        self.usuario_nome.insert(0, usuario.get('nome', ''))
        self.usuario_cpf.insert(0, usuario.get('cpf', ''))

        certificado = config.get('certificado', {})
        self.certificado_nome.insert(0, certificado.get('nome', ''))
        self.certificado_cpf.insert(0, certificado.get('cpf', ''))

        navegador = config.get('navegador', {})
        url = navegador.get('url', {})
        self.url_login.insert(0, url.get('login', ''))
        self.url_dashboard.insert(0, url.get('dashboard', ''))
        self.url_api.insert(0, url.get('api', ''))

        profile = navegador.get('profile', {})
        self.profile_path.insert(0, profile.get('path', './user_profile'))
        self.profile_name.insert(0, profile.get('name', 'Selenium'))

        pausas = navegador.get('pausas', {})
        self.pausa_login.insert(0, pausas.get('login', '5'))
        self.pausa_espera_elemento.insert(0, pausas.get('espera_elemento', '60'))

        api_servidor = config.get('api_servidor', {})
        self.tamanho_requisicao.insert(0, str(api_servidor.get('documentos_por_requisicao', '3000')))

        assinatura = config.get('assinatura', {})
        fluxo = assinatura.get('fluxo', {})
        sequencia = fluxo.get('ordem_signatarios', '')
        if isinstance(sequencia, list):
            sequencia = ', '.join(sequencia)
        self.ordem_signatarios.insert(0, sequencia or '')

        lote = assinatura.get('lote', {})
        self.lote_tamanho.insert(0, lote.get('tamanho', '10'))

        controle_bot = config.get('controle_bot', {})
        pausas = controle_bot.get('pausas', {})
        self.pausa_minima.insert(0, pausas.get('minima', '2'))
        self.pausa_maxima.insert(0, pausas.get('maxima', '3'))

        # Modo de Teste
        self.test_mode_var.set(config.get('test_mode', False))

    def _salvar(self):
        config = self.config

        config.setdefault('usuario', {})
        config['usuario']['nome'] = self.usuario_nome.get().strip()
        config['usuario']['cpf'] = self.usuario_cpf.get().strip()

        config.setdefault('certificado', {})
        config['certificado']['nome'] = self.certificado_nome.get().strip()
        config['certificado']['cpf'] = self.certificado_cpf.get().strip()

        config.setdefault('navegador', {})
        config['navegador'].setdefault('url', {})
        config['navegador']['url']['login'] = self.url_login.get().strip()
        config['navegador']['url']['dashboard'] = self.url_dashboard.get().strip()
        config['navegador']['url']['api'] = self.url_api.get().strip()

        config['navegador'].setdefault('profile', {})
        config['navegador']['profile']['path'] = self.profile_path.get().strip()
        config['navegador']['profile']['name'] = self.profile_name.get().strip()

        config['navegador'].setdefault('pausas', {})
        try:
            config['navegador']['pausas']['login'] = int(self.pausa_login.get().strip() or 5)
            config['navegador']['pausas']['espera_elemento'] = int(self.pausa_espera_elemento.get().strip() or 60)
        except ValueError:
            messagebox.showerror('Erro', 'Pausas do navegador devem ser números inteiros', parent=self)
            return

        config.setdefault('api_servidor', {})
        try:
            config['api_servidor']['documentos_por_requisicao'] = int(self.tamanho_requisicao.get().strip() or 3000)
        except ValueError:
            messagebox.showerror('Erro', 'O tamanho da requisição deve ser um número inteiro', parent=self)
            return

        config.setdefault('assinatura', {})
        config['assinatura'].setdefault('fluxo', {})
        config['assinatura'].setdefault('lote', {})
        ordem_raw = self.ordem_signatarios.get().strip()
        if ordem_raw:
            config['assinatura']['fluxo']['ordem_signatarios'] = [x.strip() for x in ordem_raw.split(',') if x.strip()]
        else:
            config['assinatura']['fluxo']['ordem_signatarios'] = []

        try:
            config['assinatura']['lote']['tamanho'] = int(self.lote_tamanho.get().strip() or 10)
        except ValueError:
            messagebox.showerror('Erro', 'O tamanho do lote deve ser um número inteiro', parent=self)
            return

        config.setdefault('controle_bot', {})
        config['controle_bot'].setdefault('pausas', {})
        try:
            config['controle_bot']['pausas']['minima'] = int(self.pausa_minima.get().strip() or 2)
            config['controle_bot']['pausas']['maxima'] = int(self.pausa_maxima.get().strip() or 4)
        except ValueError:
            messagebox.showerror('Erro', 'Pausas do bot devem ser números inteiros', parent=self)
            return

        # Modo de Teste
        config['test_mode'] = self.test_mode_var.get()

        self.parent.config = config
        salvar_config(config)
        self.parent._carregar_campos()
        self.parent._log('[INFO] Configurações avançadas salvas')

        self.destroy()

    def _escolher_pasta_navegador(self):
        pasta = filedialog.askdirectory(
            title='Selecionar diretório do profile do navegador',
            parent=self,
        )
        if pasta:
            self.profile_path.delete(0, 'end')
            self.profile_path.insert(0, pasta)

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