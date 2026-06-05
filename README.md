# Automação de Assinatura em Lote — DimensaSign

Launcher GUI para automatizar assinatura em lote de contratos no portal **DimensaSign**, com Selenium WebDriver (Microsoft Edge).

## Funcionalidades

- **Filtros** por data, tag e título de contrato
- **Download inteligente** de contratos via API com progresso e ETA
- **Assinatura em lote** com processamento por lotes configuráveis
- **Relatório Excel** detalhado com contratos assinados e pulados
- **Modo de teste** integrado — simula o portal sem acessar o DimensaSign real
- **Executável** — pode gerar um .exe com PyInstaller (modo `--onedir`, sem delay de abertura)

## Pré-requisitos

- **Python 3.10+**
- **Microsoft Edge** instalado
- **Edge WebDriver** (gerenciado automaticamente pelo Selenium Manager)

## Instalação

```bash
# Clone o repositório
git clone git@github.com:Hipstershiba/automacao-assinatura-lote.git
cd automacao-assinatura-lote

# Crie e ative o virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Linux / macOS:
source .venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

## Como usar

### GUI (recomendado)

```bash
python app.py
```

A interface permite:
- Configurar filtros de data, tag e título
- Acessar configurações avançadas (usuário, certificado, navegador, API, etc.)
- Executar/parar a automação
- Acompanhar o log em tempo real

### Modo de teste (sem acessar o portal real)

Na GUI: **Configurações > Navegador > marcar "🧪 Modo de Teste"**

Ou edite o `config.yaml`:
```yaml
test_mode: true
```

### Mock Web (navegador real em páginas locais)

Quer **ver o robô funcionando de verdade** sem o portal? Ative o Mock Web:

```yaml
test_mode: true
mock_web: true
```

Isso inicia um servidor web local que serve páginas simulando o DimensaSign,
e o Selenium abre o **Edge de verdade** navegando nessas páginas mock.
Você vê login, navegação, cliques e assinatura como se fosse no portal real.

### Script direto (CLI)

```bash
python src/assinatura.py
```

### Gerar executável

```bash
python build.py
```

O executável será gerado em `./dist/assinatura-lote/` (modo `--onedir`, que abre instantaneamente).

## Estrutura do projeto

```
automacao-assinatura-lote/
├── app.py                    # Launcher GUI (ponto de entrada principal)
├── build.py                  # Script de build (PyInstaller)
├── config.yaml.example       # Template de configuração
├── requirements.txt          # Dependências do projeto
├── src/
│   ├── assinatura.py         # Módulo principal de automação
│   ├── dimensa_client.py     # Cliente Selenium para DimensaSign
│   ├── dimensa_mock.py       # Mock para testes sem o portal real
│   ├── contrato.py           # Modelo de contrato
│   └── gerador_relatorio.py  # Gerador de relatórios Excel
└── .gitignore
```

## Configuração

Copie o arquivo de exemplo e ajuste:

```bash
cp config.yaml.example config.yaml
```

### Principais campos

| Campo | Descrição |
|---|---|
| `usuario.nome` | Nome do usuário |
| `usuario.cpf` | CPF do usuário |
| `certificado.nome` | Nome do certificado digital |
| `certificado.cpf` | CPF/CNPJ do certificado |
| `navegador.url.*` | URLs do portal DimensaSign |
| `assinatura.lote.tamanho` | Quantos contratos por lote |
| `assinatura.filtros.*` | Filtros para buscar contratos |
| `controle_bot.pausas.*` | Pausas entre ações (comportamento humano) |
| `test_mode` | `true` = modo de teste (mock), `false` = modo real |

## Licença

Uso interno. Código proprietário.