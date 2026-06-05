#========================================
# MOCK DimensaSign — para testes sem o portal real
#========================================

import os
import time
import json
import logging
import datetime
import random

logger = logging.getLogger(__name__)


# ── Elementos mock ─────────────────────────────────────────────────────────

class MockElement:
    """Simula um WebElement do Selenium."""
    def __init__(self, text='', tag='div'):
        self._text = text
        self._tag = tag

    @property
    def text(self):
        return self._text

    def click(self):
        pass

    def send_keys(self, *args):
        pass

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def get_attribute(self, name):
        return None

    def find_element(self, by, value):
        return MockElement()

    def find_elements(self, by, value):
        return []


class MockWebDriverWait:
    """Simula WebDriverWait — não espera nada, retorna mock na hora."""
    def __init__(self, driver, timeout):
        self._driver = driver
        self._timeout = timeout

    def until(self, condition, message=''):
        return MockElement()

    def until_not(self, condition, message=''):
        return MockElement()


# ── Navegador mock ────────────────────────────────────────────────────────

class MockNavegador:
    """Simula um navegador Selenium sem abrir janela real."""
    def __init__(self):
        self._current_url = 'about:blank'

    @property
    def current_url(self):
        return self._current_url

    def get(self, url):
        print(f'[MOCK] 🌐 Navegador acessando: {url}')
        self._current_url = url
        time.sleep(0.5)

    def refresh(self):
        print('[MOCK] 🔄 Página recarregada')

    def quit(self):
        print('[MOCK] 🚪 Navegador fechado')

    def find_element(self, by, value):
        return MockElement()

    def find_elements(self, by, value):
        return [MockElement()]

    def get_log(self, log_type):
        return []

    def execute_script(self, script, *args):
        return None

    def save_screenshot(self, path):
        pass

    def close(self):
        pass

    def back(self):
        pass

    def forward(self):
        pass

    def maximize_window(self):
        pass

    @property
    def title(self):
        return 'Mock DimensaSign'


# ── Respostas HTTP mock ──────────────────────────────────────────────────

class MockResponse:
    """Simula uma resposta requests.Response."""
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.headers = {'Content-Type': 'application/json'}
        self.text = json.dumps(json_data, ensure_ascii=False)
        self.content = self.text.encode('utf-8')

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if not self.ok:
            raise Exception(f"Mock HTTP {self.status_code}")


# ── Contratos falsos ─────────────────────────────────────────────────────

def _gerar_contratos_falsos(quantidade=15):
    """Gera uma lista de contratos simulados para teste."""
    hoje = datetime.date.today()
    contratos = []

    status_opcoes = ['aberto', 'aberto', 'aberto', 'pendente']
    tag_opcoes = ['', 'contrato', 'prestacao', 'venda', 'locacao']

    for i in range(quantidade):
        dias_atras = random.randint(0, 5)
        data_criacao = hoje - datetime.timedelta(days=dias_atras + random.randint(0, 10))
        data_limite = hoje + datetime.timedelta(days=random.randint(1, 15))

        contratos.append({
            'id': f'mock-doc-{i+1:04d}',
            'titulo': f'Contrato de Teste #{i+1}',
            'numero_externo': f'EXT-{2026000 + i}',
            'tag': random.choice(tag_opcoes),
            'status': random.choice(status_opcoes),
            'created_at': data_criacao.strftime('%d/%m/%Y'),
            'dataLimite': data_limite.strftime('%d/%m/%Y %H:%M:%S'),
            'signatarios': [
                {
                    'nome': 'Empresa Mock Ltda',
                    'cpfCnpj': '11222333000181',
                    'pivot': {'status': 'pendente', 'tipo': 'emissor'}
                },
                {
                    'nome': 'Cliente Teste Silva',
                    'cpfCnpj': '12345678900',
                    'pivot': {'status': 'pendente', 'tipo': 'cliente'}
                }
            ]
        })

    return contratos


# ── Sessão mock ──────────────────────────────────────────────────────────

class MockSession:
    """Simula uma requests.Session com dados falsos."""
    def __init__(self):
        self.headers = {}
        self.contratos = _gerar_contratos_falsos(quantidade=15)

    def get(self, url, params=None, **kwargs):
        logger.debug(f'[MOCK] GET {url} params={params}')

        if 'meus-documentos' in url:
            page = int((params or {}).get('page', 1))
            limit = int((params or {}).get('limit', 10))

            # Paginação simulada
            inicio = (page - 1) * limit
            fim = inicio + limit
            pagina_docs = self.contratos[inicio:fim]

            return MockResponse({
                'payload': {
                    'total': len(self.contratos),
                    'lastPage': max(1, (len(self.contratos) + limit - 1) // limit),
                    'documentos': pagina_docs,
                    'page': page,
                }
            })

        return MockResponse({'payload': {}}, status_code=200)

    def post(self, url, json=None, **kwargs):
        logger.debug(f'[MOCK] POST {url} json={json}')
        return MockResponse({
            'payload': {
                'lote': {
                    'id': f'mock-lote-{random.randint(1000, 9999)}'
                }
            }
        })


# ── Client mock ──────────────────────────────────────────────────────────

class MockDimensaClient:
    """
    Versão mock do DimensaClient para testes sem o portal real.

    Mesma interface pública que DimensaClient:
      - iniciar_navegador()
      - fazer_login()
      - capturar_token()
      - validar_token()
      - fechar_navegador()
      - navegador (propriedade)
      - sessao (propriedade)
    """

    def __init__(self, config_navegador=None, stop_event=None):
        self.config_navegador = config_navegador or {}
        self.stop_event = stop_event
        self.token = 'Bearer mock-token-para-teste'
        self._navegador = None
        self._sessao = None

    def iniciar_navegador(self):
        print(f'[MOCK] 🚀 Inicializando navegador simulado (profile: {self.config_navegador.get("profile", {}).get("name", "Mock")})')
        self._navegador = MockNavegador()
        return self._navegador

    def fazer_login(self):
        print('[MOCK] 🔑 Simulando login...')
        time.sleep(1)
        navegador = self._navegador or self.iniciar_navegador()
        navegador._current_url = self.config_navegador.get('url', {}).get('dashboard', 'https://mock.app.dimensa.com.br/dashboard')
        print('[MOCK] ✅ Login simulado com sucesso!')

    def capturar_token(self):
        print(f'[MOCK] 🎫 Token capturado: {self.token[:30]}...')
        return self.token

    def validar_token(self, tentativas=5, intervalo=10):
        print('[MOCK] ✅ Token validado com sucesso!')
        self._sessao = MockSession()
        self._sessao.headers.update({'Authorization': self.token})
        return True

    def fechar_navegador(self):
        if self._navegador:
            self._navegador.quit()
            self._navegador = None

    @property
    def navegador(self):
        return self._navegador

    @property
    def sessao(self):
        if self._sessao is None:
            self._sessao = MockSession()
            self._sessao.headers.update({'Authorization': self.token})
        return self._sessao