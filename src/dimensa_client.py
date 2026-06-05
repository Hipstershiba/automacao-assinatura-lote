#========================================
# IMPORTS
#========================================
import os
import time
import json
import logging
import requests

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service

#========================================
# Configurações de logging
#========================================

logger = logging.getLogger(__name__)

#========================================
# Classe
#========================================
class DimensaClient:
    def __init__(self, config_navegador=None):
        
        self._validar_config(config_navegador)
        self.url_login = config_navegador['url']['login']
        self.url_dashboard = config_navegador['url']['dashboard']
        self.url_api = config_navegador['url']['api']
        self.pausa_login = config_navegador['pausas']['login']
        self.profile_name = config_navegador['profile']['name']
        
        profile_path = config_navegador['profile']['path']
        self.profile_path = profile_path if os.path.isabs(profile_path) else os.path.abspath(profile_path)

        self.token = None
        self.navegador = None
        self.sessao = None

    def opcoes_navegador(self):
        opcoes = Options()
        opcoes.add_argument('--enable-extensions')
        opcoes.add_argument('--start-maximized')
        opcoes.add_argument('--user-data-dir=' + self.profile_path)
        opcoes.add_argument('--profile-directory=' + self.profile_name)
        opcoes.add_argument('--log-level=3')
        opcoes.add_experimental_option('excludeSwitches', ['enable-logging'])
        opcoes.set_capability('ms:loggingPrefs', {'performance': 'ALL'})
        return opcoes

    def _validar_config(self, config):
        """Garante que todas as chaves obrigatórias existem no dicionário."""
        if not isinstance(config, dict):
            raise TypeError("O parâmetro 'config_navegador' precisa ser um dicionário.")

    def iniciar_navegador(self):

        if not os.path.exists(self.profile_path):
            os.makedirs(self.profile_path)

        options = self.opcoes_navegador()
        service = Service()

        self.navegador = webdriver.Edge(options=options, service=service)

        return self.navegador

    def fazer_login(self):
        self.validar_navegador()
        self.navegador.get(self.url_login)

        url = self.navegador.current_url
        while url != self.url_dashboard:
            print('[INFO] Aguardando login...')
            time.sleep(self.pausa_login)
            url = self.navegador.current_url

        self.navegador.refresh()
        time.sleep(self.pausa_login)

    def capturar_token(self):
        self.validar_navegador()
        logger.info('Iniciando varredura dos logs de rede para captura do token...')

        logs = self.navegador.get_log('performance')
        for log in logs:
            try:
                log_data = json.loads(log['message'])['message']
                
                if log_data['method'] == 'Network.requestWillBeSent':
                    request_data = log_data.get('params', {}).get('request', {})
                    headers = request_data.get('headers', {})
                    
                    auth = {key.lower(): value for key, value in headers.items()}.get('authorization')
                    
                    if auth and 'Bearer' in auth:
                        self.token = auth
                        logger.info('Bearer Token encontrado na requisição de rede!')
                        break
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        if self.validar_token():
            return self.token
            
    def validar_navegador(self):
        if self.navegador is None:
            raise Exception("navegador não iniciado. Chame iniciar_navegador() primeiro.")

    def validar_token(self, tentativas=5, intervalo=10):
        if self.token is None:
            raise Exception("Token não capturado. Chame capturar_token() primeiro.")

        self.sessao = requests.Session()
        self.sessao.headers.update({'Authorization': self.token})

        url = f'{self.url_api}/api/v2/documentos/list/meus-documentos'

        for tentativa in range(1, tentativas + 1):
            try:
                response = self.sessao.get(url, params={'limit': 1})
                if response.ok:
                    logger.info(f'Token validado com sucesso na tentativa {tentativa}')
                    print(f'[INFO] Token validado com sucesso na tentativa {tentativa}')
                    return True
                status = response.status_code
                logger.warning(f'Health check retornou {status} na tentativa {tentativa}')
                print(f'[WARNING] Health check retornou {status} na tentativa {tentativa}')
            except requests.exceptions.RequestException as exc:
                logger.warning(f'Health check falhou na tentativa {tentativa}: {exc}')
                print(f'[WARNING] Health check falhou na tentativa {tentativa}: {exc}')
            time.sleep(intervalo)

        raise RuntimeError("Token inválido ou não autorizado")

    def fechar_navegador(self):
        if self.navegador:
            self.navegador.quit()
            self.navegador = None

if __name__ == "__main__":
    import yaml

    # 1. Configura o logging para exibir as mensagens no terminal durante o teste local
    logging.basicConfig(
        level=logging.INFO, 
        format='%(levelname)s - %(message)s'
    )

    # 2. Carrega o arquivo de configuração YAML
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        config_navegador = config.get('navegador', {})
    except FileNotFoundError:
        logger.error("Arquivo 'config.yaml' não foi encontrado no diretório atual.")
        exit(1)

    # 3. Instancia e executa a classe com segurança
    dimensa = DimensaClient(config_navegador)
    
    try:
        dimensa.iniciar_navegador()
        dimensa.fazer_login()
        
        token_capturado = dimensa.capturar_token()
        print(f'\n[SUCESSO] Token capturado e validado: {token_capturado}\n')
        
    except Exception as exc:
        logger.error(f"Ocorreu uma falha durante a execução da automação: {exc}")
        
    finally:
        # O bloco finally garante que o Edge não fique travado na memória se o código falhar
        logger.info("Finalizando o processo e fechando o navegador...")
        dimensa.fechar_navegador()