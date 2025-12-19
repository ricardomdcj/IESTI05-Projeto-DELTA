# IESTI05 - Desenvolvimento de um Assistente Doméstico Baseado em IA Generativa na Borda - Projeto DELTA
Documentação de todo o projeto de IESTI05 para conclusão da segunda parte do curso.

O vídeo de apresentação do projeto se encontra no link: 
<a href="https://www.youtube.com/watch?v=dKtQXxFgpXw">
  <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/YouTube_full-color_icon_%282017%29.svg/1024px-YouTube_full-color_icon_%282017%29.svg.png" width="20" alt="IESTI05 - Dataset + FOMO + YOLO">
</a>
https://www.youtube.com/watch?v=dKtQXxFgpXw

<div align="center">
  <img src="https://raw.githubusercontent.com/ricardomdcj/IESTI05-Projeto-DELTA/de3122edee0d421e0808a5707cc6effb843f7a79/delta.png" width="30%" alt="Logo Delta Centralizada">
</div>

## Visão Geral

**DELTA** é um assistente de voz inteligente para automação residencial que combina reconhecimento de voz offline (Vosk) com processamento de linguagem natural em edge computing (Ollama). O sistema permite controlar dispositivos inteligentes como ar-condicionado, ventilador de teto, lâmpadas RGB e monitorar sensores ambientais em tempo real.

### Características Principais

-**Reconhecimento de voz offline** via Vosk (sem dependência de internet)

-**Processamento de IA em edge** com Ollama (modelos pequenos e rápidos)

-**Controle de dispositivos Tuya** (AR, ventilador, lâmpadas RGB)

-**Monitoramento ambiental** com múltiplos sensores (DHT22, AHT20, BMP280)

-**LED RGB indicador de estado** do sistema

-**Métricas de latência** para análise de desempenho

-**Feedback visual** em tempo real

---

## Requisitos de Hardware

### Computador Principal
- **Raspberry Pi 5** (ou similar com GPIO e I2C)
- **Memória RAM**: Mínimo 4GB (recomendado 8GB)
- **Armazenamento**: Mínimo 32GB
- **Sistema Operacional**: Raspberry Pi OS

### Sensores Ambientais
| Sensor | Protocolo | Função |
|--------|-----------|--------|
| **DHT22** | GPIO (single-wire) | Temperatura e Umidade |
| **AHT20** | I2C (0x38) | Temperatura e Umidade |
| **BMP280** | I2C (0x77 ou 0x76) | Pressão, Temperatura e Altitude |

### Dispositivos de Entrada/Saída
| Dispositivo | Protocolo | Função |
|-------------|-----------|--------|
| **LED RGB** | GPIO | Indicador de estado do sistema |
| **Microfone USB** | USB/3.5mm | Captura de áudio |

### Dispositivos Inteligentes Tuya
| Dispositivo | Versão | Função |
|-------------|--------|--------|
| **Ar-Condicionado Split** | 3.3 | Controle de temperatura e modos |
| **Interruptor Inteligente** | 3.4 | Ventilador de teto + Lâmpada teto |
| **Lâmpada RGB** | 3.5 | Iluminação colorida e intensidade |

### Conexões GPIO (Raspberry Pi 5)

```
GPIO 4  (pin 7)   -> DHT22 Data
GPIO 13 (pin 33)  -> LED RGB Red (PWM)
GPIO 19 (pin 35)  -> LED RGB Green (PWM)
GPIO 26 (pin 37)  -> LED RGB Blue (PWM)

I2C Bus (SDA/SCL):
GPIO 2 (pin 3)    -> SDA (AHT20, BMP280)
GPIO 3 (pin 5)    -> SCL (AHT20, BMP280)
```

---

## Dependências de Software

### Dependências do Sistema Operacional
```bash
sudo apt update
sudo apt install -y \
    python3-dev \
    python3-pip \
    python3-board \
    portaudio19-dev \
    swig \
    git \
    alsa-utils \
    libasound2-dev
```

### Bibliotecas Python (pip)

```bash
# Reconhecimento de voz
vosk==0.3.32

# LLM local
ollama-python==0.1.0

# Processamento de áudio
pyaudio==0.2.13

# Hardware GPIO e Sensores
RPi.GPIO==0.7.0
gpiozero==2.0.1
adafruit-circuitpython-dht==3.7.10
adafruit-circuitpython-ahtx0==1.0.15
adafruit-circuitpython-bmp280==3.9.4
adafruit-circuitpython-busio==5.2.6

# Controle Tuya
tinytuya==1.12.7

# Utilitários
numpy==1.24.3
```

### Modelos Necessários

1. **Modelo de Voz Vosk**
   - Modelo recomendado: `vosk-model-pt-br-v1` (Português Brasileiro)
   - Diretório: `./models` (na raiz do projeto)

2. **Modelo de Linguagem (LLM)**
   - Executar via Ollama (ambiente virtual recomendado)
   - Modelo padrão: `llama3.2:3b` (otimizado para edge)

---

## Instruções de Instalação

### 1. Preparação do Ambiente

```bash
# Crie um ambiente virtual Python
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### 2. Instalação de Dependências

```bash
# Instale as dependências do sistema
sudo apt update && sudo apt install -y portaudio19-dev swig libasound2-dev

# Instale as bibliotecas Python
pip install -r requirements.txt
```

### 3. Configuração de Modelos

```bash
# Crie o diretório para o modelo de voz
mkdir -p models

# Download do modelo Vosk (Português Brasileiro)
cd models
pip install vosk
wget https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip
unzip vosk-model-small-pt-0.3.zip
cd ..

# Instale e inicie Ollama (com Docker)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

### 4. Configuração de Dispositivos Tuya

Edite `controle_tuya.py` com suas credenciais:

```python
DEVICES = {
    "interruptor": {
        "id": "SEU_DEVICE_ID",
        "ip": "192.168.0.XXX",
        "key": "SUA_CHAVE_LOCAL",
        "version": VERSAO_DO_SEU_DEVICE,
    },
    # ... adicione seus outros dispositivos
}
```

**Para obter credenciais Tuya:**
1. Use a app oficial Tuya Smart
2. Ative "Modo de Desenvolvimento" em cada dispositivo
3. Obtenha Device ID e Local Key via:
   - tinytuya: `tinytuya.wizard()`
   - Ou aplicação web: https://iot.tuya.com

### 5. Habilitação de I2C e GPIO

```bash
# Ative I2C e GPIO via raspi-config
sudo raspi-config

# Selecione:
# 3. Interface Options
# I5. I2C -> Enable
# I1. GPIO -> Enable

# Verifique se os sensores I2C estão visíveis
i2cdetect -y 1
```

### 6. Teste de Hardware

```bash
# Teste os sensores
python3 hardware.py

# Teste o controle Tuya
python3 controle_tuya.py status

# Teste o LED
python3 -c "from hardware import GerenciadorLED; led = GerenciadorLED(); led.iniciar_rainbow()"
```

---

## Instruções de Uso

### Execução Principal do Sistema

```bash
# Ative o ambiente virtual
source venv/bin/activate

# Inicie o assistente DELTA
python3 delta.py
```

**Saída esperada:**
```
======================================================================
SISTEMA DELTA - ASSISTENTE VIRTUAL RESIDENCIAL
======================================================================
Modelo de linguagem: llama3.2:3b
Limite de captura: 15.0s
Sensores: DHT22, AHT20, BMP280
======================================================================
[STATUS] Aguardando palavra-chave: 'delta'
```

### Interações de Voz

Uma vez que o sistema esteja rodando, você pode:

#### 1. Consultar Clima
```
User: "Delta, como está o clima?"
DELTA: "Temperatura de 24.5°C, umidade em 60%, ambiente confortável."
```

#### 2. Controlar Ar-Condicionado
```
User: "Delta, ajusta o ar para 22 graus"
DELTA: "AC ligado em 22°C (ambiente: 24.5°C)."

User: "Delta, desliga o ar"
DELTA: "AC desligado."
```

#### 3. Controlar Ventilador
```
User: "Delta, liga o ventilador na velocidade 3"
DELTA: "Ventilador ligado velocidade 3."

User: "Delta, desliga o ventilador"
DELTA: "Ventilador desligado."
```

#### 4. Controlar Lâmpadas
```
User: "Delta, acende a luz do teto"
DELTA: "Lampada teto ligada."

User: "Delta, coloca a lâmpada em modo noite"
DELTA: "Lampada RGB modo noite 450 100%."

User: "Delta, aumenta o brilho da lâmpada para 80"
DELTA: "Lampada RGB 80%."
```

#### 5. Conversa Geral
```
User: "Delta, qual é a capital do Brasil?"
DELTA: "A capital do Brasil é Brasília."
```

### Controle Manual via Terminal

```bash
# Ar-Condicionado
python3 controle_tuya.py ar switch on
python3 controle_tuya.py ar temp 23
python3 controle_tuya.py ar mode cold
python3 controle_tuya.py ar wind high

# Ventilador
python3 controle_tuya.py interruptor ventilador on
python3 controle_tuya.py interruptor speed 3

# Lâmpada Teto
python3 controle_tuya.py interruptor lamp on

# Lâmpada RGB
python3 controle_tuya.py lampada modo dia
python3 controle_tuya.py lampada brilho 75
python3 controle_tuya.py lampada temp quente

# Status
python3 controle_tuya.py ar status
python3 controle_tuya.py lampada status
```

### Indicadores LED

| Cor | Significado |
|-----|-------------|
| 🔴 **Vermelho** | Aguardando palavra-chave "delta" |
| 🟢 **Verde** | Palavra-chave detectada, aguardando comando |
| 🌈 **Rainbow** | Processando IA/SLM |
| 🔵 **Azul** | Respondendo ao usuário |

---

## Estrutura de Arquivos

```
delta-system/
├── delta.py                 # Sistema principal (reconhecimento + IA)
├── hardware.py              # Gerenciador de sensores e LED
├── controle_tuya.py         # Interface Tuya Smart
├── device_tools.py          # Funções de controle de dispositivos
├── model/                   # Diretório com modelo Vosk
│   └── vosk-model-pt-br-v1/
├── requirements.txt         # Dependências Python
├── README.md                # Este arquivo
└── logs/                    # Logs do sistema (opcional)
```

---

## Configurações Personalizáveis

### Em `delta.py`

```python
# Reconhecimento de voz
PALAVRA_CHAVE = "delta"              # Palavra-chave para ativar
MODELO_LLM = "llama3.2:3b"           # Modelo de linguagem
TAXA = 16000                         # Taxa de amostragem (Hz)
TEMPO_SILENCIO = 2.0                 # Tempo de silêncio para finalizar (s)
TEMPO_MAXIMO_CAPTURA = 15.0          # Limite máximo de captura (s)
LIMIAR_RUIDO = 300                   # Limite de amplitude de ruído
```

### Em `hardware.py`

```python
INTERVALO_LEITURA_SENSORES = 2.0     # Intervalo de leitura (s)
VELOCIDADE_RAINBOW = 0.005           # Velocidade do efeito LED
```

---

## Métricas de Desempenho

O sistema exibe latência detalhada ao final de cada comando:

```
======================================================================
METRICAS DE LATENCIA
======================================================================
Captura de voz (keyword -> silencio):    3456.2 ms
Preparacao de prompt:                     12.5 ms
Processamento SLM:                      1234.8 ms
Execucao de ferramentas:                  45.2 ms
Geracao de resposta:                     123.4 ms
----------------------------------------------------------------------
LATENCIA TOTAL (keyword -> resposta):   4872.1 ms
Tempo total: 4.87 segundos
======================================================================
```

---


## Créditos e Agradecimentos

### Geração e Otimização de Código
- **Claude (Anthropic)**: Estruturação e refatoração de código, geração de partes das funções principais
- **Gemini (Google)**: Otimização de lógica, geração de logos e estratégia de desenvolvimento

### Bibliotecas e Ferramentas Utilizadas
- [Vosk](https://alphacephei.com/vosk/) - Reconhecimento de voz offline
- [Ollama](https://ollama.ai/) - Execução de LLMs locais
- [tinytuya](https://github.com/jasonacox/tinytuya) - Controle de dispositivos Tuya
- [gpiozero](https://gpiozero.readthedocs.io/) - Controle de GPIO simplificado
- [Adafruit CircuitPython](https://circuitpython.readthedocs.io/) - Bibliotecas de sensores

---

## Licença

Este projeto é fornecido "como está" para fins educacionais e pessoais.

---
