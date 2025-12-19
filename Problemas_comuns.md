---

## Problemas Comuns e Soluções

### 1. Erro: "Modelo de voz não encontrado"
```
[ERRO] Modelo de voz 'model' nao encontrado.
```
**Solução**: Baixe o modelo Vosk para o diretório `./model`:
```bash
wget https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip
unzip vosk-model-small-pt-0.3.zip
```

### 2. Erro: "Ollama connection refused"
```
ConnectionRefusedError: [Errno 111] Connection refused
```
**Solução**: Inicie o Ollama:
```bash
ollama serve
```

### 3. Erro: "Sensor DHT22 não responde"
```
[AVISO] DHT22 off: Permission error
```
**Solução**: Execute com privilégios sudo:
```bash
sudo python3 delta.py
```

### 4. Erro: "I2C device not found"
```
[AVISO] AHT20 off: No I2C devices found
```
**Solução**: Verifique conexão e ative I2C:
```bash
i2cdetect -y 1
sudo raspi-config  # Enable I2C
```

### 5. Erro: "Dispositivo Tuya não encontrado"
```
[ERRO] Falha ao conectar ao dispositivo AR
```
**Solução**: Verifique:
- IP do dispositivo na rede local
- Device ID e Local Key em `controle_tuya.py`
- Conectividade de rede (ping)

### 6. Latência Alta na Resposta de Voz
**Solução**:
- Use modelo SLM menor (e.g., `tinyllama:1.1b`)
- Aumente recursos de CPU/GPU
- Reduza `TEMPO_MAXIMO_CAPTURA` para processar mais rapidamente

### 7. Erro de Permissão no GPIO
```
PermissionError: No access to /dev/gpiomem
```
**Solução**: Adicione usuário ao grupo GPIO:
```bash
sudo usermod -a -G gpio $USER
newgrp gpio
```

---
