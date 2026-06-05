#========================================
# Servidor Mock do DimensaSign
# Simula as páginas web para demonstração visual com Selenium real.
#========================================

import os
import sys
import json
import threading
import random
import datetime
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer com suporte a múltiplas threads (uma por request)."""
    allow_reuse_address = True
    daemon_threads = True
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


# ── Dados mock ────────────────────────────────────────────────────────────

def _gerar_contratos(quantidade=15):
    hoje = datetime.date.today()
    contratos = []
    tags = ['', 'contrato', 'prestacao', 'venda', 'locacao']

    for i in range(quantidade):
        dc = hoje - datetime.timedelta(days=random.randint(0, 15))
        dl = hoje + datetime.timedelta(days=random.randint(1, 15))
        contratos.append({
            'id': f'mock-doc-{i+1:04d}',
            'titulo': f'Contrato de Teste #{i+1}',
            'numero_externo': f'EXT-{2026000 + i}',
            'tag': random.choice(tags),
            'status': 'aberto',
            'created_at': dc.strftime('%d/%m/%Y'),
            'dataLimite': dl.strftime('%d/%m/%Y %H:%M:%S'),
            'signatarios': [
                {'nome': 'Empresa Mock Ltda', 'cpfCnpj': '11222333000181',
                 'pivot': {'status': 'pendente', 'tipo': 'emissor'}},
                {'nome': 'Cliente Teste Silva', 'cpfCnpj': '12345678900',
                 'pivot': {'status': 'pendente', 'tipo': 'cliente'}},
            ]
        })
    return contratos


# ── Páginas HTML ──────────────────────────────────────────────────────────

PAGINA_LOGIN = '''<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>Mock DimensaSign — Login</title>
<style>
body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;
height:100vh;margin:0;background:#f0f2f5}
.card{background:#fff;border-radius:12px;padding:40px;box-shadow:0 2px 12px rgba(0,0,0,.1);
text-align:center;width:360px}
h2{color:#1a1a2e;margin-bottom:8px}
p{color:#666;font-size:14px;margin-bottom:24px}
.btn-login{background:#1a73e8;color:#fff;border:none;padding:12px 32px;border-radius:6px;
font-size:16px;cursor:pointer;transition:background .2s}
.btn-login:hover{background:#1557b0}
.spinner{display:none;margin-top:16px;color:#999;font-size:13px}
.loading .spinner{display:block}
.loading .btn-login{display:none}
</style></head><body>
<div class="card">
  <h2>🔐 Mock DimensaSign</h2>
  <p>Portal de teste — clique para simular o login</p>
  <form method="POST" action="/login" id="loginForm">
    <button type="submit" class="btn-login" id="btnEntrar">Entrar no Sistema</button>
    <div class="spinner">⏳ Simulando login...</div>
  </form>
</div>
<script>
document.getElementById('loginForm').onsubmit = function(e){
  e.preventDefault();
  this.classList.add('loading');
  setTimeout(() => { this.submit(); }, 1200);
};
</script>
</body></html>'''

PAGINA_DASHBOARD = '''<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>Mock DimensaSign — Dashboard</title>
<style>
body{font-family:sans-serif;margin:0;background:#f0f2f5;color:#333}
nav{background:#1a1a2e;color:#fff;padding:16px 24px;display:flex;justify-content:space-between}
nav h1{margin:0;font-size:18px}
nav span{font-size:13px;opacity:.8}
main{padding:24px;max-width:800px;margin:0 auto}
.card{background:#fff;border-radius:8px;padding:20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.card h3{margin:0 0 12px;color:#1a1a2e}
.stat{display:inline-block;margin-right:24px}
.stat .num{font-size:28px;font-weight:bold;color:#1a73e8}
.stat .label{font-size:13px;color:#666}
.btn{background:#1a73e8;color:#fff;border:none;padding:10px 24px;border-radius:6px;font-size:14px;cursor:pointer}
.btn:hover{background:#1557b0}
</style></head><body>
<nav><h1>🏢 Mock DimensaSign</h1><span>Bem-vindo, Usuário Teste</span></nav>
<main>
  <div class="card">
    <h3>📊 Resumo</h3>
    <div class="stat"><div class="num" id="totalDocs">15</div>
    <div class="label">Contratos</div></div>
    <div class="stat"><div class="num">12</div>
    <div class="label">Pendentes</div></div>
    <div class="stat"><div class="num">0</div>
    <div class="label">Assinados Hoje</div></div>
  </div>
  <div class="card" style="text-align:center;padding:40px">
    <p style="margin-bottom:20px;color:#666">Use o menu lateral para acessar as funcionalidades.</p>
    <button class="btn" onclick="window.location.href='/batch-subscription'">
      📝 Ir para Assinatura em Lote
    </button>
  </div>
</main>
<script>
fetch('/api/v2/documentos/list/meus-documentos?limit=1', {
  headers: {'Authorization': 'Bearer mock-token-visual-12345'}
}).catch(function(){});
</script>
</body></html>'''

PAGINA_BATCH = '''<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>Mock DimensaSign — Assinar em Lote</title>
<style>
body{font-family:sans-serif;margin:0;background:#f0f2f5;color:#333}
nav{background:#1a1a2e;color:#fff;padding:16px 24px}
nav h1{margin:0;font-size:18px}
main{padding:24px;max-width:700px;margin:0 auto;text-align:center}
.card{background:#fff;border-radius:8px;padding:32px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.btn{background:#1a73e8;color:#fff;border:none;padding:12px 32px;border-radius:6px;
font-size:15px;cursor:pointer;margin:8px;transition:all .2s}
.btn:hover{background:#1557b0;transform:translateY(-1px)}
.btn-success{background:#0d7c3f}
.btn-success:hover{background:#0a6232}
.btn-warning{background:#e67e22}
.btn-warning:hover{background:#d35400}
.btn:disabled{opacity:.6;cursor:not-allowed;transform:none}
.feedback{margin-top:20px;padding:16px;border-radius:6px;display:none}
.feedback.success{display:block;background:#d4edda;color:#155724;border:1px solid #c3e6cb}
.feedback.info{display:block;background:#d1ecf1;color:#0c5460;border:1px solid #bee5eb}
.py-2{padding:12px 16px;margin:6px 0;border:1px solid #dee2e6;border-radius:6px;
cursor:pointer;transition:all .2s;text-align:left;background:#fff}
.py-2:hover{border-color:#1a73e8;background:#e8f0fe}
.py-2.selected{border-color:#0d7c3f;background:#d4edda}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;
background:rgba(0,0,0,.4);justify-content:center;align-items:center}
.modal.show{display:flex}
.modal-content{background:#fff;border-radius:12px;padding:32px;max-width:480px;
text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.15)}
</style></head><body>
<nav><h1>📝 Assinar em Lote — Mock</h1></nav>
<main>
  <div class="card">
    <div id="step1">
      <h3 style="margin-top:0">Lote Criado com Sucesso!</h3>
      <p style="color:#666">5 contratos prontos para assinatura.</p>
      <button class="btn" id="btnAssinarLote"
        onclick="document.getElementById('step1').style.display='none';
                 document.getElementById('step2').style.display='block'">
        Assinar em Lote
      </button>
    </div>
    <div id="step2" style="display:none;margin-top:24px">
      <button class="btn btn-success" id="btnVisualizarLote"
        onclick="document.getElementById('step2').style.display='none';
                 document.getElementById('step3').style.display='block'">
        VISUALIZAR LOTE
      </button>
    </div>
    <div id="step3" style="display:none;margin-top:24px">
      <p style="color:#666;margin-bottom:16px">Visualize os documentos do lote e confirme.</p>
      <button class="btn btn-warning" id="btnAssinarEmLote"
        onclick="document.getElementById('step3').style.display='none';
                 document.getElementById('step4').style.display='block'">
        ASSINAR EM LOTE
      </button>
    </div>
    <div id="step4" style="display:none;margin-top:24px;text-align:left">
      <p style="color:#666;margin-bottom:12px">Selecione o certificado digital:</p>
      <section class="py-2" onclick="selecionarCert(this)">
        <strong>Empresa Mock Ltda</strong><br>
        CNPJ: 11.222.333/0001-81<br>
        <small style="color:#666">Válido até: 31/12/2027</small>
      </section>
      <section class="py-2" onclick="selecionarCert(this)">
        <strong>Fulano de Tal</strong><br>
        CPF: 123.456.789-00<br>
        <small style="color:#666">Válido até: 30/06/2027</small>
      </section>
      <div style="text-align:center;margin-top:16px">
        <button class="btn btn-success" id="btnConfirmar"
          onclick="confirmarAssinatura()" disabled>
          Confirmar Assinatura
        </button>
      </div>
    </div>
    <div id="step5" style="display:none;margin-top:24px">
      <div class="modal show" id="modalCert">
        <div class="modal-content">
          <h3>📄 Confirmação de Assinatura</h3>
          <p style="color:#666">Deseja realmente assinar o lote com o certificado selecionado?</p>
          <button class="btn btn-success" id="tutorial-cert-assina"
            onclick="document.getElementById('modalCert').style.display='none';
                     document.getElementById('step5').style.display='none';
                     document.getElementById('step6').style.display='block'">
            ✅ Sim, Assinar
          </button>
          <button class="btn" style="background:#6c757d" onclick="fecharModal()">
            Cancelar
          </button>
        </div>
      </div>
    </div>
    <div id="step6" style="display:none;margin-top:24px">
      <div class="feedback success" id="scroll-dialog-description" style="display:block">
        <h3>✅ Lote Assinado com Sucesso!</h3>
        <p style="color:#666">5 contratos foram assinados.</p>
        <div style="margin-top:16px">
          <button class="btn btn-success"
            onclick="window.location.href='/batch-subscription'">
            Continuar
          </button>
        </div>
      </div>
    </div>
  </div>
</main>
<script>
let certSelecionado = false;
function selecionarCert(el) {
  document.querySelectorAll('.py-2').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  certSelecionado = true;
  document.getElementById('btnConfirmar').disabled = false;
}
function confirmarAssinatura() {
  document.getElementById('step4').style.display = 'none';
  document.getElementById('step5').style.display = 'block';
}
function fecharModal() {
  document.getElementById('modalCert').style.display = 'none';
  document.getElementById('step5').style.display = 'none';
  document.getElementById('step4').style.display = 'block';
}
</script>
</body></html>'''


# ── Handler HTTP ──────────────────────────────────────────────────────────

class MockHandler(BaseHTTPRequestHandler):
    """Serve as páginas mock e endpoints de API."""

    contratos = _gerar_contratos(15)
    lotes_criados = 0

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _html(self, html, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _redirect(self, path):
        self.send_response(302)
        self.send_header('Location', path)
        self.end_headers()

    def log_message(self, format, *args):
        logger.info(f'[MockServer] {args[0]} {args[1]} {args[2]}')

    # ── Rotas ──

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/login':
            self._html(PAGINA_LOGIN)

        elif path == '/dashboard':
            self._html(PAGINA_DASHBOARD)

        elif path == '/batch-subscription':
            self._html(PAGINA_BATCH)

        elif path.startswith('/api/v2/documentos/list/meus-documentos'):
            params = parse_qs(parsed.query)
            page = int(params.get('page', [1])[0])
            limit = int(params.get('limit', [10])[0])
            inicio = (page - 1) * limit
            fim = inicio + limit
            docs = self.__class__.contratos[inicio:fim]
            total = len(self.__class__.contratos)
            self._json({
                'payload': {
                    'total': total,
                    'lastPage': max(1, (total + limit - 1) // limit),
                    'documentos': docs,
                    'page': page,
                }
            })

        elif path == '/api/v2/documentos/list/meus-documentos/':
            self._redirect('/api/v2/documentos/list/meus-documentos')

        else:
            self._html('<h1>404 - Página não encontrada</h1>', 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/login':
            self._redirect('/dashboard')

        elif path == '/api/lote':
            self.__class__.lotes_criados += 1
            lote_id = f'mock-lote-{self.__class__.lotes_criados:04d}'
            logger.info(f'[MockServer] Lote criado: {lote_id}')
            self._json({
                'payload': {
                    'lote': {'id': lote_id}
                }
            })

        else:
            self._json({'error': 'Not found'}, 404)

    do_PUT = do_POST
    do_DELETE = do_POST


# ── Server Manager ────────────────────────────────────────────────────────

class ServidorMock:
    """Inicia/gerencia o servidor HTTP mock em uma thread separada."""

    def __init__(self, host='127.0.0.1', port=0):
        self.host = host
        self.port = port
        self._server = None
        self._thread = None
        self._started = threading.Event()

    def iniciar(self):
        """Inicia o servidor em uma thread daemon."""
        self._server = ThreadedHTTPServer((self.host, self.port), MockHandler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._started.set()
        logger.info(f'[MockServer] 🚀 Servidor mock rodando em http://{self.host}:{self.port}')

    def parar(self):
        """Para o servidor."""
        if self._server:
            self._server.shutdown()
            self._server = None
            logger.info('[MockServer] ⏹ Servidor mock parado')

    @property
    def url_base(self):
        return f'http://{self.host}:{self.port}'

    @property
    def url_login(self):
        return f'{self.url_base}/login'

    @property
    def url_dashboard(self):
        return f'{self.url_base}/dashboard'

    @property
    def url_api(self):
        return f'{self.url_base}'

    def aguardar(self, timeout=5):
        """Aguarda o servidor iniciar."""
        return self._started.wait(timeout)


# ── Entry point para teste ────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(message)s')
    sv = ServidorMock()
    sv.iniciar()
    print(f'Servidor rodando em {sv.url_base}')
    print('Pressione Ctrl+C para parar.')
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        sv.parar()