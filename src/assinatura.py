#========================================
# IMPORTS
#========================================

import os
import sys
import time
import random
import requests
import datetime
import logging

import yaml

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.dimensa_client import DimensaClient
from src.contrato import Contrato
from src.gerador_relatorio import GeradorRelatorio

# Modo de teste — importa mocks se disponível
try:
    from src.dimensa_mock import MockDimensaClient, MockWebDriverWait
    _MOCK_DISPONIVEL = True
except ImportError:
    _MOCK_DISPONIVEL = False

#========================================
# Configura log (executado uma vez na importação)
#========================================

if not os.path.exists('logs'):
    os.makedirs('logs')

HOJE = datetime.date.today()
logging.basicConfig(filename=os.path.join('logs', f'{HOJE}.log'), encoding='utf-8', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%y %H:%M:%S')


#========================================
# Funções auxiliares (não dependem de config)
#========================================

def formatar_data(data_string):
    try:
        data_obj = datetime.datetime.strptime(data_string, '%d/%m/%Y')
    except Exception as e:
        raise ValueError(e)
    try:
        result = data_obj.strftime('%Y-%m-%d')
    except Exception as e:
        raise ValueError(e)
    return result


def baixar_contratos(sessao, parametros, url_api):
    url = f'{url_api}/api/v2/documentos/list/meus-documentos'

    # Primeira chamada para metadados
    response = sessao.get(url, params=parametros)
    response.raise_for_status()
    dados_init = response.json()

    total_contratos = dados_init.get('payload', {}).get('total', 0)
    total_paginas = dados_init.get('payload', {}).get('lastPage', 1)

    todos_documentos = []
    ids_baixados = set()  # Para evitar duplicatas

    inicio_total = time.time()

    print(f"\n--- Iniciando Download de {total_contratos} documentos ---")

    for pagina in range(1, total_paginas + 1):
        parametros['page'] = pagina
        inicio_pagina = time.time()

        try:
            response = sessao.get(url, params=parametros)
            response.raise_for_status()

            novos_docs = response.json().get('payload', {}).get('documentos', [])

            for doc in novos_docs:
                doc_id = doc.get('id')
                if doc_id not in ids_baixados:
                    todos_documentos.append(doc)
                    ids_baixados.add(doc_id)

            # Estimativa de tempo restante
            fim_pagina = time.time()
            tempo_desta_pagina = fim_pagina - inicio_pagina
            paginas_restantes = total_paginas - pagina
            tempo_restante_segundos = paginas_restantes * tempo_desta_pagina
            minutos, segundos = divmod(int(tempo_restante_segundos), 60)
            eta_str = f"{minutos:02d}:{segundos:02d}"

            progresso = len(todos_documentos)
            percentual = (progresso / total_contratos) * 100 if total_contratos > 0 else 100

            msg = (f"Pág {pagina}/{total_paginas} | Docs: {progresso}/{total_contratos} "
                   f"({percentual:.1f}%) | ETA: {eta_str}")

            logging.info(msg)
            sys.stdout.write(f"\r[PROCESSO] {msg}")
            sys.stdout.flush()

        except Exception as e:
            logging.error(f"\nErro na página {pagina}: {e}")

    tempo_final = time.time() - inicio_total
    print(f"\n\nConcluído em {int(tempo_final // 60)}min {int(tempo_final % 60)}s!")
    return todos_documentos


def titulo_valido(titulo, nome_documento):
    if not nome_documento:
        return True
    return nome_documento.lower() in titulo.lower()


def esta_expirado(data_limite_str):
    data_limite = datetime.datetime.strptime(data_limite_str, "%d/%m/%Y %H:%M:%S")
    return datetime.datetime.now() > data_limite


def validar_contrato(contrato, nome_documento, usuario_cpf):
    if esta_expirado(contrato.data_limite):
        logging.info(f"Contrato {contrato.titulo} expirado")
        return False

    if not titulo_valido(contrato.titulo, nome_documento):
        logging.info(f"Contrato {contrato.titulo} não corresponde ao filtro de nome")
        return False

    if not contrato.liberar_assinatura(usuario_cpf):
        logging.info(f"Contrato {contrato.titulo} não está liberado para assinatura neste momento")
        return False

    return True


def delay(pausa_minima, pausa_maxima):
    time.sleep(random.randint(pausa_minima, pausa_maxima))


def clique_seguro(wait, xpath, nome_elemento, retries=3):
    for i in range(retries):
        try:
            elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            elemento.click()
            logging.info(f'Clique com sucesso: {nome_elemento}')
            return True
        except Exception as e:
            logging.warning(f'Tentativa {i+1} falhou para {nome_elemento}: {e}')
            time.sleep(2)
    raise RuntimeError(f'Falha persistente após {retries} tentativas: {nome_elemento}')


def encerrar_automacao(navegador, gerador_relatorio=None, codigo=1, perguntar=False):
    if gerador_relatorio is not None:
        try:
            gerador_relatorio.salvar_relatorio()
        except Exception as e:
            logging.error(f"Falha ao salvar relatório: {e}")

    logging.info('========================================')
    logging.info('ENCERRANDO AUTOMAÇÃO')
    logging.info('========================================\n\n')
    print('[INFO] ENCERRANDO AUTOMAÇÃO')
    time.sleep(1)

    if navegador:
        try:
            navegador.quit()
        except Exception:
            pass

    if not perguntar:
        sys.exit(codigo)

    # Modo interativo (perguntar=True) — usado apenas quando executado standalone
    while True:
        resposta = input("[WARNING] Deseja encerrar a automação? [Y/n]: ").strip().lower()
        if resposta == "" or resposta in ["y", "s"]:
            sys.exit(codigo)
        elif resposta == "n":
            print("\nFechamento cancelado.")
            break
        else:
            print("Opção inválida! Aperte ENTER ou digite 'Y' ou 'N'.")


def verificar_solicitacao_parada(navegador, gerador_relatorio=None, stop_event=None):
    """Verifica se a interface gráfica solicitou a interrupção da automação."""
    if stop_event and stop_event.is_set():
        print("\n[INFO] Sinal de interrupção detectado vindo da interface!")
        encerrar_automacao(navegador, gerador_relatorio, codigo=0, perguntar=False)


#========================================
# Funções que dependem de parâmetros do config
#========================================

def criar_lote(sessao, contratos_ids, usuario_cpf, url_api):
    url = f'{url_api}/api/lote'
    payload = {
        'ids': contratos_ids,
        "cpfAssinante": usuario_cpf
    }
    response = sessao.post(url, json=payload)
    response.raise_for_status()
    lote_id = response.json().get('payload', {}).get('lote').get('id')
    logging.info(f'Lote criado com ID: {lote_id}')
    return lote_id


def selecionar_certificado(navegador, wait, certificado_cnpj, certificado_nome):
    try:
        wait.until(EC.presence_of_all_elements_located((By.XPATH, "//section[contains(@class,'py-2')]")))
        certificados = navegador.find_elements(By.XPATH, "//section[contains(@class,'py-2')]")

        for certificado in certificados:
            texto = certificado.text

            if f"CNPJ: {certificado_cnpj}" not in texto:
                continue
            if certificado_nome not in texto:
                continue
            if "VENCIDO" in texto.upper():
                continue

            certificado.click()
            logging.info(f"Certificado selecionado: CNPJ={certificado_cnpj}, Nome={certificado_nome}")
            return

        raise RuntimeError(
            f"Certificado não encontrado ou vencido: CNPJ={certificado_cnpj}, Nome={certificado_nome}"
        )
    except Exception as e:
        logging.error("Falha ao selecionar certificado configurado")
        logging.error(e)
        raise


def assinar_lote(navegador, gerador_relatorio, wait,
                 pausa_minima, pausa_maxima,
                 certificado_cpf, certificado_nome,
                 modo_teste=False,
                 url_batch=None):

    if modo_teste:
        msg = '[MOCK] 📝 Simulando assinatura em lote...'
        print(msg)
        logging.info(msg)
        msg = '[MOCK] ✅ Lote assinado com sucesso (simulado)!'
        print(msg)
        logging.info(msg)
        return

    # Abre página de assinar em lote
    url_batch = url_batch or 'https://sign.app.dimensa.com.br/adminsign/user/batch-subscription'
    try:
        navegador.get(url_batch)
    except Exception as e:
        logging.error('Falha ao tentar acessar página Assinar em Lote')
        logging.error(e)
        print('[INFO] Falha ao tentar acessar página Assinar em Lote')
        encerrar_automacao(navegador, gerador_relatorio, 1)
    delay(pausa_minima, pausa_maxima)

    # Certifica que a página carregou corretamente
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Assinar em Lote')]")))
        navegador.find_element(By.XPATH, "//button[contains(text(), 'Assinar em Lote')]").click()
        logging.info('Página de assinatura em lote acessada com sucesso')
    except Exception as e:
        logging.error('Falha ao acessar página de assinatura em lote')
        logging.error(e)
        print('[INFO] Falha ao acessar página de assinatura em lote')
        encerrar_automacao(navegador, gerador_relatorio, 1)
    delay(pausa_minima, pausa_maxima)

    # Visualizar lote
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'VISUALIZAR LOTE')]")))
        navegador.find_element(By.XPATH, "//button[contains(text(), 'VISUALIZAR LOTE')]").click()
        logging.info('Visualizando lote')
    except Exception as e:
        logging.error('Falha ao visualizar lote')
        logging.error(e)
        encerrar_automacao(navegador, gerador_relatorio, 1)
    delay(pausa_minima, pausa_maxima)

    # Assinar lote
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'ASSINAR EM LOTE')]")))
        navegador.find_element(By.XPATH, "//button[contains(text(), 'ASSINAR EM LOTE')]").click()
        logging.info('Assinar em lote')
    except Exception as e:
        logging.error('Falha ao assinar em lote')
        logging.error(e)
        encerrar_automacao(navegador, gerador_relatorio, 1)
    delay(pausa_minima, pausa_maxima)

    # Seleciona certificado
    try:
        selecionar_certificado(navegador, wait, certificado_cpf, certificado_nome)
        logging.info('Certificado selecionado')
    except Exception as e:
        logging.error('Falha ao selecionar certificado')
        logging.error(e)
        encerrar_automacao(navegador, gerador_relatorio, 1)
    delay(pausa_minima, pausa_maxima)

    # Confirma assinatura
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tutorial-cert-assina"]')))
        navegador.find_element(By.XPATH, '//*[@id="tutorial-cert-assina"]').click()
        logging.info('Assinatura confirmada')
    except Exception as e:
        logging.error('Falha ao confirmar assinatura')
        logging.error(e)
        encerrar_automacao(navegador, gerador_relatorio, 1)
    delay(pausa_minima, pausa_maxima)

    # Finaliza lote
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="scroll-dialog-description"]/div/button')))
        navegador.find_element(By.XPATH, '//*[@id="scroll-dialog-description"]/div/button').click()
        logging.info('Finalizando lote')
    except Exception as e:
        logging.error('Falha ao finalizar lote')
        logging.error(e)
        encerrar_automacao(navegador, gerador_relatorio, 1)


#========================================
# Função principal (ponto de entrada único)
#========================================

def rodar_automacao(config=None, stop_event=None):
    """
    Executa a automação de assinatura em lote.

    Parâmetros:
        config: dicionário com toda a configuração (mesma estrutura do config.yaml).
                Se None, lê do arquivo 'config.yaml' no diretório atual.
        stop_event: threading.Event para interromper a execução.

    Retorna: 0 em caso de sucesso, 1 em caso de erro.

    Pode levantar SystemExit em caso de erro grave (capturável pela GUI).
    """
    if config is None:
        with open('config.yaml', 'r') as file:
            config = yaml.safe_load(file)

    # Extrai configurações
    URL_LOGIN = config['navegador']['url']['login']
    URL_DASHBOARD = config['navegador']['url']['dashboard']
    URL_API = config['navegador']['url']['api']
    PROFILE_PATH = config['navegador']['profile']['path']
    PROFILE_NAME = config['navegador']['profile']['name']
    PAUSA_LOGIN = config['navegador']['pausas']['login']

    USUARIO_NOME = config['usuario'].get('nome', config['usuario']['cpf'])
    USUARIO_CPF = config['usuario']['cpf'].replace('.', '').replace('-', '').replace('/', '')

    CERTIFICADO_NOME = config['certificado']['nome']
    CERTIFICADO_CPF = config['certificado']['cpf'].replace('.', '').replace('-', '').replace('/', '')

    CONTRATOS_POR_PAGINA = config['api_servidor']['documentos_por_requisicao']

    DATA_INICIAL = config['assinatura']['filtros']['data_inicial']
    DATA_FINAL = config['assinatura']['filtros']['data_final']
    TAG = config['assinatura']['filtros']['tag']
    NOME_DOCUMENTO = config['assinatura']['filtros']['titulo']
    ORDEM_ASSINATURA = config['assinatura']['fluxo']['ordem_signatarios']
    TAMANHO_LOTE = config['assinatura']['lote']['tamanho']

    ESPERA_ELEMENTO = config['controle_bot']['pausas']['espera_elemento']
    PAUSA_MINIMA = config['controle_bot']['pausas']['minima']
    PAUSA_MAXIMA = config['controle_bot']['pausas']['maxima']

    logging.info('========================================')
    logging.info('INICIANDO AUTOMAÇÃO')
    logging.info('========================================')
    print('[INFO] INICIANDO AUTOMAÇÃO')

    # Verifica modo de teste
    modo_teste = config.get('test_mode', False)
    mock_web = config.get('mock_web', False)

    if modo_teste:
        if not _MOCK_DISPONIVEL:
            print('[AVISO] Módulo de mock não encontrado. Instalando dependências de teste...')
        msg = '[MOCK] 🧪 MODO DE TESTE ATIVO — simulando portal DimensaSign'
        print(msg)
        logging.info(msg)
        msg = '[MOCK] Nenhum dado real será acessado ou modificado.'
        print(msg)
        logging.info(msg)

    # Mock visual com servidor web + navegador real
    servidor_mock = None
    if modo_teste and mock_web:
        try:
            from src.servidor_mock import ServidorMock
            servidor_mock = ServidorMock()
            servidor_mock.iniciar()
            servidor_mock.aguardar()
            # Redireciona URLs do navegador para o servidor mock
            config['navegador']['url']['login'] = servidor_mock.url_login
            config['navegador']['url']['dashboard'] = servidor_mock.url_dashboard
            config['navegador']['url']['api'] = servidor_mock.url_api
            print(f'[MOCK] 🌐 Servidor web mock em {servidor_mock.url_base}')
            logging.info(f'[MOCK] 🌐 Servidor web mock em {servidor_mock.url_base}')
            print(f'[MOCK] 🔗 Navegador real apontando para páginas locais')
            logging.info(f'[MOCK] 🔗 Navegador real apontando para páginas locais')
            # Re-extrai URLs após mock server estar pronto (porta dinâmica)
            URL_LOGIN = config['navegador']['url']['login']
            URL_DASHBOARD = config['navegador']['url']['dashboard']
            URL_API = config['navegador']['url']['api']
        except Exception as e:
            print(f'[AVISO] Falha ao iniciar servidor mock web: {e}')
            print('[AVISO] Usando modo mock headless (sem navegador)')
            mock_web = False

    # Inicializa gerador de relatório
    gerador_relatorio = GeradorRelatorio(
        usuario_cpf=USUARIO_CPF,
        usuario_nome=USUARIO_NOME,
        filtros={
            'data_inicial': DATA_INICIAL,
            'data_final': DATA_FINAL,
            'tag': TAG,
            'nome_documento': NOME_DOCUMENTO
        },
        ordem_assinatura=ORDEM_ASSINATURA
    )

    # Abre navegador (real ou mock headless)
    if modo_teste and not mock_web:
        dimensa = MockDimensaClient(config['navegador'], stop_event=stop_event)
    else:
        dimensa = DimensaClient(config['navegador'], stop_event=stop_event)
    dimensa.iniciar_navegador()
    navegador = dimensa.navegador

    # Realiza login
    try:
        dimensa.fazer_login()
        logging.info('Login realizado com sucesso')
        print('[INFO] Login realizado com sucesso')
    except Exception as e:
        logging.error('Falha no processo de login')
        logging.error(e)
        print('[INFO] Falha no processo de login')
        encerrar_automacao(navegador, gerador_relatorio, 1)

    # Captura token de autenticação
    try:
        token = dimensa.capturar_token()
        logging.info('Token capturado com sucesso')
        print('[INFO] Token capturado com sucesso')
    except Exception as e:
        logging.error('Falha ao capturar token')
        logging.error(e)
        print('[INFO] Falha ao capturar token')
        encerrar_automacao(navegador, gerador_relatorio, 1)

    # Configura sessão de requisições com token
    sessao = dimensa.sessao
    sessao.headers.update({'Authorization': token})

    if modo_teste and not mock_web:
        wait = MockWebDriverWait(navegador, ESPERA_ELEMENTO)
    else:
        wait = WebDriverWait(navegador, ESPERA_ELEMENTO)

    # Baixar contratos via API
    parametros = {
        'assinaturaPendente': 'S',
        'status': 'aberto',
        'limit': CONTRATOS_POR_PAGINA
    }
    if DATA_INICIAL:
        parametros['dataInicial'] = formatar_data(DATA_INICIAL)
    if DATA_FINAL:
        parametros['dataFinal'] = formatar_data(DATA_FINAL)
    if TAG:
        parametros['tag'] = TAG

    try:
        contratos_json = baixar_contratos(sessao, parametros, URL_API)
        total_contratos_baixados = len(contratos_json)
        logging.info(f'{total_contratos_baixados} contratos baixados')
        print(f'[INFO] {total_contratos_baixados} contratos baixados')
    except Exception as e:
        logging.error('Falha ao baixar contratos via API')
        logging.error(e)
        print('[INFO] Falha ao baixar contratos via API')
        encerrar_automacao(navegador, gerador_relatorio, 1)

    if total_contratos_baixados == 0:
        logging.info('Nenhum contrato disponível')
        print('[INFO] Nenhum contrato disponível')
        encerrar_automacao(navegador, gerador_relatorio, 0)

    # Cria objetos Contrato
    contratos_validados = []
    for contrato in contratos_json:
        novo_contrato = Contrato(
            titulo=contrato['titulo'],
            codigo=contrato['numero_externo'],
            doc_id=contrato['id'],
            tag=contrato['tag'],
            status=contrato['status'],
            ordem_assinatura=ORDEM_ASSINATURA,
            data_criacao=contrato['created_at'],
            data_limite=contrato['dataLimite']
        )
        novo_contrato.set_signatarios(contrato['signatarios'])
        if validar_contrato(novo_contrato, NOME_DOCUMENTO, USUARIO_CPF):
            contratos_validados.append(novo_contrato)
        else:
            if esta_expirado(novo_contrato.data_limite):
                gerador_relatorio.registrar_pulado(novo_contrato, "Contrato expirado")
            elif not titulo_valido(novo_contrato.titulo, NOME_DOCUMENTO):
                gerador_relatorio.registrar_pulado(novo_contrato, "Não corresponde ao filtro de nome")
            elif not novo_contrato.liberar_assinatura(USUARIO_CPF):
                gerador_relatorio.registrar_pulado(novo_contrato, "Não liberado para assinatura neste momento")

    contratos_total = len(contratos_validados)
    contratos_restantes = contratos_total

    logging.info('Iniciando assinatura dos contratos')
    logging.info(f'Contratos restantes: {contratos_restantes}/{contratos_total}')
    print('[INFO] Iniciando assinatura dos contratos')
    print(f'[INFO] Contratos restantes: {contratos_restantes}/{contratos_total}')

    for i in range(0, contratos_total, TAMANHO_LOTE):
        verificar_solicitacao_parada(navegador, gerador_relatorio, stop_event=stop_event)
        lote_contratos = contratos_validados[i: i + TAMANHO_LOTE]
        ids_lote = [contrato.id for contrato in lote_contratos]
        try:
            criar_lote(sessao, ids_lote, USUARIO_CPF, URL_API)
        except Exception as e:
            logging.error('Falha ao criar lote')
            logging.error(e)
            print('[INFO] Falha ao criar lote')
            encerrar_automacao(navegador, gerador_relatorio, 1)
        try:
            assinar_lote(navegador, gerador_relatorio, wait,
                         PAUSA_MINIMA, PAUSA_MAXIMA,
                         CERTIFICADO_CPF, CERTIFICADO_NOME,
                         modo_teste=(modo_teste and not mock_web),
                         url_batch=(URL_API + '/batch-subscription') if mock_web else None)
            logging.info('Lote assinado com sucesso')

            for contrato in lote_contratos:
                gerador_relatorio.registrar_assinatura(
                    contrato,
                    datetime.datetime.now().strftime("%H:%M:%S")
                )

            contratos_restantes -= len(lote_contratos)
            logging.info(f'Contratos restantes: {contratos_restantes}/{contratos_total}')
            print('[INFO] Lote assinado com sucesso')
            print(f'[INFO] Contratos restantes: {contratos_restantes}/{contratos_total}')
        except Exception as e:
            logging.error('Falha ao assinar lote')
            logging.error(e)
            print('[INFO] Falha ao assinar lote')
            encerrar_automacao(navegador, gerador_relatorio, 1)

    encerrar_automacao(navegador, gerador_relatorio, 0)


#========================================
# Execução standalone (via CLI)
#========================================

if __name__ == "__main__":
    rodar_automacao()