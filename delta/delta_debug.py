import os
import sys
import pyaudio
import json
import time
import audioop
from ctypes import *
from vosk import Model, KaldiRecognizer
import ollama
from device_tools import set_ac_state, set_fan_state, set_lamp_state, set_ceiling_lamp_state
from hardware import Sensores, GerenciadorLED

# --- 1. SUPRESSÃO DE ERROS (ALSA & C-LIBS) ---
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
except OSError:
    pass

# --- 2. SUPRESSÃO DE STDERR (SISTEMA) ---
class SuppressErrorOutput:
    def __enter__(self):
        self._original_stderr = os.dup(sys.stderr.fileno())
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stderr.fileno())
        os.close(devnull)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self._original_stderr, sys.stderr.fileno())
        os.close(self._original_stderr)

# --- CONFIGURAÇÕES ---
PALAVRA_CHAVE = "delta"
MODELO_PATH = "model"
MODELO_LLM = "llama3.2:3b"

# Configuração de Áudio e VAD
TAXA = 16000
BUFFER = 8000
LIMIAR_RUIDO = 300
TEMPO_SILENCIO = 2.0
TEMPO_MAXIMO_CAPTURA = 15.0

sensores = Sensores()
led = GerenciadorLED()

SYSTEM_PROMPT = """
Você é Delta, uma IA residencial brasileira.
Respostas: breves, objetivas, sem Markdown. Máximo 2 frases.

Regras:
1. AC e Ventilador NUNCA ligam juntos. Se T>23°C prefira AC.
2. AC: 16-30°C (ideal 23°C).
3. Ventilador: escolha velocidade 1-5 baseado na necessidade.
4. Lâmpadas: use "dia" para trabalho, "noite" para relaxar.

IMPORTANTE - Ações:
- LIGAR/LIGA/ACENDE/ATIVA = power: true
- DESLIGAR/DESLIGA/APAGA/DESATIVA = power: false
Nunca confunda essas ações!
""".strip()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_ac_state",
            "description": "Controla o Ar-Condicionado Split (parede).",
            "parameters": {
                "type": "object",
                "properties": {
                    "power": {"type": "boolean", "description": "Ligar/Desligar AC"},
                    "target_temp_c": {"type": "integer", "description": "Temp alvo (16-30)"},
                    "mode": {"type": "string", "enum": ["cold", "wet", "wind", "auto"]},
                    "wind": {"type": "string", "enum": ["auto", "mute", "low", "mid", "high"]},
                    "swing": {"type": "boolean", "description": "Oscilar aletas"},
                    "eco": {"type": "boolean", "description": "Modo economia"},
                    "sleep": {"type": "boolean", "description": "Modo noturno"}
                },
                "required": ["power"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_fan_state",
            "description": "Controla Ventilador de Teto. Use APENAS se AC desligado. Escolha speed 1-5 baseado no contexto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "power": {"type": "boolean", "description": "Ligar/Desligar"},
                    "speed": {"type": "integer", "description": "Velocidade 1-5 (opcional, escolha baseado na necessidade)", "minimum": 1, "maximum": 5}
                },
                "required": ["power"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_ceiling_lamp_state",
            "description": "Liga/desliga lâmpada simples do teto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "power": {"type": "boolean"}
                },
                "required": ["power"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_lamp_state",
            "description": "Controla Lâmpada RGB. Modos: 'dia' (trabalho/leitura) ou 'noite' (relaxar).",
            "parameters": {
                "type": "object",
                "properties": {
                    "power": {"type": "boolean"},
                    "mode": {"type": "string", "enum": ["dia", "noite", "day", "night", "white", "warm"]},
                    "brightness": {"type": "integer", "description": "Brilho 1-100%", "minimum": 1, "maximum": 100},
                    "temperature": {"type": "string", "enum": ["quente", "frio", "warm", "cold"]}
                },
            },
        },
    },
]

# --- CLASSE PARA MÉTRICAS DE LATÊNCIA ---
class Metricas:
    def __init__(self):
        self.reset()

    def reset(self):
        self.t_keyword = None
        self.t_comando_inicio = None
        self.t_comando_fim = None
        self.t_slm_inicio = None
        self.t_slm_fim = None
        self.t_tools_inicio = None
        self.t_tools_fim = None
        self.t_resposta_fim = None

    def marcar_keyword(self):
        self.t_keyword = time.time()

    def marcar_comando_inicio(self):
        self.t_comando_inicio = time.time()

    def marcar_comando_fim(self):
        self.t_comando_fim = time.time()

    def marcar_slm_inicio(self):
        self.t_slm_inicio = time.time()

    def marcar_slm_fim(self):
        self.t_slm_fim = time.time()

    def marcar_tools_inicio(self):
        self.t_tools_inicio = time.time()

    def marcar_tools_fim(self):
        self.t_tools_fim = time.time()

    def marcar_resposta_fim(self):
        self.t_resposta_fim = time.time()

    def imprimir(self):
        """Imprime métricas formatadas"""
        print("\n" + "="*70)
        print("⏱️  MÉTRICAS DE LATÊNCIA")
        print("="*70)

        if self.t_keyword and self.t_comando_fim:
            latencia_voz = (self.t_comando_fim - self.t_keyword) * 1000
            print(f"🎤 Captura de voz (keyword → silêncio):  {latencia_voz:>7.1f} ms")

        if self.t_comando_fim and self.t_slm_inicio:
            prep_slm = (self.t_slm_inicio - self.t_comando_fim) * 1000
            print(f"📝 Preparação prompt:                    {prep_slm:>7.1f} ms")

        if self.t_slm_inicio and self.t_slm_fim:
            latencia_slm = (self.t_slm_fim - self.t_slm_inicio) * 1000
            print(f"🧠 Processamento SLM:                    {latencia_slm:>7.1f} ms")

        if self.t_tools_inicio and self.t_tools_fim:
            latencia_tools = (self.t_tools_fim - self.t_tools_inicio) * 1000
            print(f"🔧 Execução de tools:                    {latencia_tools:>7.1f} ms")

        if self.t_slm_fim and self.t_resposta_fim:
            latencia_resposta = (self.t_resposta_fim - self.t_slm_fim) * 1000
            print(f"💬 Geração de resposta:                  {latencia_resposta:>7.1f} ms")

        print("-"*70)

        if self.t_keyword and self.t_resposta_fim:
            latencia_total = (self.t_resposta_fim - self.t_keyword) * 1000
            print(f"⏰ LATÊNCIA TOTAL (keyword → resposta):  {latencia_total:>7.1f} ms")
            print(f"   = {latencia_total/1000:.2f} segundos")

        print("="*70 + "\n")

# Instância global de métricas
metricas = Metricas()


def ler_sensores():
    """Lê DHT22, AHT20 e BMP280 via classe Sensores e calcula a média de temperatura."""
    leituras = sensores.ler_todos()
    temps = []
    for nome, dados in leituras.items():
        t = dados.get("temp")
        if t is not None:
            temps.append(float(t))
    media = sum(temps) / len(temps) if temps else None
    return {
        "media_temp_c": media,
        "leituras": leituras,
    }


def interpretar_clima(temp_media: float | None, umidade_media: float | None) -> str:
    """Gera uma interpretação simples do conforto térmico."""
    if temp_media is None:
        return "não foi possível determinar a sensação térmica"

    if temp_media < 18:
        faixa_temp = "frio"
    elif 18 <= temp_media < 24:
        faixa_temp = "confortável"
    elif 24 <= temp_media < 28:
        faixa_temp = "um pouco quente"
    else:
        faixa_temp = "quente"

    if umidade_media is None:
        return faixa_temp

    if umidade_media < 30:
        faixa_umid = "ambiente seco"
    elif 30 <= umidade_media <= 60:
        faixa_umid = "umidade confortável"
    else:
        faixa_umid = "ambiente úmido ou abafado"

    return f"{faixa_temp}, com {faixa_umid}"


def responder_clima_atual():
    """Responde consultas sobre clima atual usando sensores."""
    dados = ler_sensores()
    media_temp = dados["media_temp_c"]
    leituras = dados["leituras"]

    if media_temp is None:
        print("[DELTA] Não consegui ler os sensores agora.")
        return

    umids = []
    linhas = []
    for nome, d in leituras.items():
        t = d.get("temp")
        u = d.get("umid")
        p = d.get("pressao")
        alt = d.get("altitude")
        if u is not None:
            umids.append(float(u))
        linha = f"{nome}: "
        if t is not None:
            linha += f"{t:.1f} °C"
        if u is not None:
            linha += f", {u:.1f}% umidade"
        if p is not None:
            linha += f", {p:.1f} hPa"
        if alt is not None:
            linha += f", altitude {alt:.1f} m"
        linhas.append(linha)

    texto_sensores = "\n".join(linhas)
    umidade_media = sum(umids) / len(umids) if umids else None
    interpretacao = interpretar_clima(media_temp, umidade_media)

    prompt = f"""
[DADOS REAIS]
{texto_sensores}
Média: {media_temp:.1f}°C ({interpretacao}).

[TAREFA]
Responda ao usuário como está o clima interno agora. Seja natural e curto.
""".strip()

    if led:
        led.estado_processando_slm()

    metricas.marcar_slm_inicio()
    resp = ollama.chat(
        model=MODELO_LLM,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    metricas.marcar_slm_fim()

    resposta = resp["message"]["content"].strip()
    if led:
        led.estado_respondendo()
    print(f"[DELTA] {resposta}")

    metricas.marcar_resposta_fim()
    metricas.imprimir()

    if led:
        led.estado_ouvindo_keyword()


def processar_comando_voz(comando: str):
    """Roteia o comando de voz para o handler apropriado."""
    texto_lower = comando.lower()

    print(f"[DEBUG] Comando recebido: '{comando}'")
    print(f"[DEBUG] Texto lower: '{texto_lower}'")

    # 1) Perguntas sobre clima/ambiente (consulta, não ajuste)
    palavras_consulta_clima = [
        "clima atual", "como está o clima", "como está o tempo",
        "qual o clima", "como está o ambiente", "qual a temperatura",
        "temperatura agora", "quantos graus"
    ]

    if any(p in texto_lower for p in palavras_consulta_clima):
        print("[DEBUG] → Rota: responder_clima_atual()")
        metricas.marcar_comando_fim()
        responder_clima_atual()
        return

    # 2) Detecção de dispositivos ou ações de controle
    # Palavras que indicam controle de dispositivos
    palavras_dispositivos = [
        "ar", "ar-condicionado", "ar condicionado", "ac",
        "ventilador", "ventoinha",
        "luz", "lâmpada", "lampada", "iluminação", "iluminacao",
        "teto", "lamp"
    ]

    palavras_acoes = [
        "liga", "ligar", "lig", "ligue",
        "desliga", "desligar", "deslig", "desligue",
        "acende", "acender", "acend",
        "apaga", "apagar",
        "ajusta", "ajustar", "ajuste",
        "regula", "regular", "regule",
        "configura", "configurar", "configure",
        "controla", "controlar", "controle",
        "deixa", "deixe",
        "coloca", "colocar", "coloque",
        "esfria", "esfriar", "esfrie",
        "refresca", "refrescar", "refres",
        "aumenta", "aumentar", "aumente",
        "diminui", "diminuir", "diminua",
        "ativa", "ativar", "ative",
        "desativa", "desativar", "desative"
    ]

    tem_dispositivo = any(p in texto_lower for p in palavras_dispositivos)
    tem_acao = any(p in texto_lower for p in palavras_acoes)

    print(f"[DEBUG] tem_dispositivo: {tem_dispositivo}")
    print(f"[DEBUG] tem_acao: {tem_acao}")

    # Se menciona dispositivo OU ação de controle, usa function calling
    if tem_dispositivo or tem_acao:
        print("[DEBUG] → Rota: processar_com_function_calling()")
        metricas.marcar_comando_fim()
        processar_com_function_calling(comando)
        return

    # 3) Conversa geral (sem tools)
    print("[DEBUG] → Rota: conversa_geral()")
    metricas.marcar_comando_fim()
    conversa_geral(comando)


def processar_com_function_calling(comando: str):
    """
    Processa comandos que devem usar function calling.
    Unifica controle de clima e iluminação.
    """
    print("[DEBUG] Entrando em processar_com_function_calling()")

    dados = ler_sensores()
    media = dados["media_temp_c"]

    if media is not None:
        sensacao = "Frio" if media < 20 else "Agradável" if media < 25 else "Quente"
        context_temp = f"Temperatura atual: {media:.1f}°C ({sensacao})"
    else:
        context_temp = "Temperatura: sensor indisponível"

    prompt_usuario = f"""
[CONTEXTO]
{context_temp}

[COMANDO DO USUÁRIO]
{comando}

[INSTRUÇÃO]
Você DEVE usar uma das tools disponíveis para executar este comando.
Analise o comando e escolha a tool correta:
- "ar" ou "ar-condicionado" → set_ac_state
- "ventilador" → set_fan_state  
- "luz" ou "lâmpada" → set_lamp_state ou set_ceiling_lamp_state

REGRAS IMPORTANTES:
- LIGAR/ACENDER → power: true
- DESLIGAR/APAGAR → power: false
- AC e Ventilador NUNCA juntos
""".strip()

    print(f"[DEBUG] Prompt enviado para SLM:")
    print(prompt_usuario)
    print("[DEBUG] Chamando ollama.chat() com tools...")

    if led:
        led.estado_processando_slm()

    metricas.marcar_slm_inicio()
    resp = ollama.chat(
        model=MODELO_LLM,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_usuario},
        ],
        tools=TOOLS,
    )
    metricas.marcar_slm_fim()

    print(f"[DEBUG] Resposta da SLM: {resp}")

    tool_calls = resp["message"].get("tool_calls") or resp["message"].get("toolcalls")

    print(f"[DEBUG] tool_calls: {tool_calls}")

    if tool_calls:
        print(f"[DEBUG] SLM chamou {len(tool_calls)} tool(s)")
        metricas.marcar_tools_inicio()
        resultados = []

        for call in tool_calls:
            fname = call["function"]["name"]
            args = call["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)

            print(f"[DEBUG] Executando tool: {fname} com args: {args}")

            if fname == "set_ac_state":
                if "target_temp_c" in args and args["target_temp_c"] is not None:
                    args["target_temp_c"] = float(args["target_temp_c"])
                result = set_ac_state(**args)
                estado = "ligado" if args.get("power") else "desligado"
                temp = f" em {args.get('target_temp_c'):.0f}°C" if args.get("target_temp_c") else ""
                resultados.append(f"AC {estado}{temp}")
                print(f"[DELTA][AC] {result}")

            elif fname == "set_fan_state":
                result = set_fan_state(**args)
                estado = "ligado" if args.get("power") else "desligado"
                speed = f" velocidade {args.get('speed')}" if args.get("speed") else ""
                resultados.append(f"Ventilador {estado}{speed}")
                print(f"[DELTA][FAN] {result}")

            elif fname == "set_ceiling_lamp_state":
                result = set_ceiling_lamp_state(**args)
                estado = "ligada" if args.get("power") else "desligada"
                resultados.append(f"Lâmpada teto {estado}")
                print(f"[DELTA][LAMP_TETO] {result}")

            elif fname == "set_lamp_state":
                result = set_lamp_state(**args)
                detalhes = []
                if args.get("power") is not None:
                    detalhes.append("ligada" if args["power"] else "desligada")
                if args.get("mode"):
                    detalhes.append(f"modo {args['mode']}")
                if args.get("brightness"):
                    detalhes.append(f"{args['brightness']}%")
                resultados.append(f"Lâmpada RGB {' '.join(detalhes)}")
                print(f"[DELTA][LAMP_RGB] {result}")

        metricas.marcar_tools_fim()

        msg = ". ".join(resultados) + "."
        if led:
            led.estado_respondendo()
        print(f"[DELTA] {msg}")
    else:
        print("[DEBUG] SLM NÃO chamou tools! Respondeu com texto:")
        resposta = resp["message"].get("content", "").strip()
        print(f"[DEBUG] Resposta texto: '{resposta}'")
        if resposta:
            if led:
                led.estado_respondendo()
            print(f"[DELTA] {resposta}")
        else:
            print("[DELTA] Comando processado.")

    metricas.marcar_resposta_fim()
    metricas.imprimir()

    if led:
        led.estado_ouvindo_keyword()


def conversa_geral(prompt):
    """Conversa geral sem function calling."""
    metricas.marcar_slm_inicio()
    sys.stdout.write("[DELTA] ")
    sys.stdout.flush()

    try:
        stream = ollama.chat(
            model=MODELO_LLM,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ],
            options={'num_predict': 60, 'temperature': 0.1, 'top_k': 20},
            stream=True,
        )
        texto_full = ""
        for chunk in stream:
            pedaco = chunk['message']['content'].replace('\n', ' ')
            sys.stdout.write(pedaco)
            sys.stdout.flush()
            texto_full += pedaco
        sys.stdout.write("\n")

        metricas.marcar_slm_fim()
        metricas.marcar_resposta_fim()
        metricas.imprimir()

        return texto_full
    except Exception as e:
        print(f"\n[ERRO] {e}")
        return None


def main():
    if not os.path.exists(MODELO_PATH):
        print(f"[ERRO] Modelo de voz '{MODELO_PATH}' não encontrado.")
        return

    os.system("clear")
    print("--- SISTEMA DELTA INICIADO ---")
    print("💡 Métricas de latência: ATIVADAS")
    print("🔧 Function calling: ATIVADO")
    print(f"⏱️  Limite captura áudio: {TEMPO_MAXIMO_CAPTURA}s")
    print("🐛 Modo DEBUG: ATIVADO")

    with SuppressErrorOutput():
        modelo_vosk = Model(MODELO_PATH)
        reconhecedor = KaldiRecognizer(modelo_vosk, TAXA)
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=TAXA,
            input=True,
            frames_per_buffer=BUFFER,
        )

    stream.start_stream()
    print(f"[STATUS] Aguardando palavra-chave: '{PALAVRA_CHAVE}'")
    if led:
        led.estado_ouvindo_keyword()

    ouvindo_comando = False
    ultimo_tempo_voz = 0.0
    tempo_inicio_captura = 0.0

    try:
        while True:
            dados = stream.read(4000, exception_on_overflow=False)

            if not ouvindo_comando:
                if reconhecedor.AcceptWaveform(dados):
                    resultado = json.loads(reconhecedor.Result())
                    texto = resultado.get("text", "").lower()
                    if PALAVRA_CHAVE in texto:
                        print("[STATUS] Palavra-chave detectada. Fale o comando...")
                        metricas.reset()
                        metricas.marcar_keyword()
                        ouvindo_comando = True
                        ultimo_tempo_voz = time.time()
                        tempo_inicio_captura = time.time()
                        reconhecedor.Reset()
                        if led:
                            led.estado_keyword_detectada()
                continue

            reconhecedor.AcceptWaveform(dados)

            if audioop.rms(dados, 2) > LIMIAR_RUIDO:
                ultimo_tempo_voz = time.time()

            tempo_decorrido = time.time() - tempo_inicio_captura
            if tempo_decorrido > TEMPO_MAXIMO_CAPTURA:
                print(f"[INFO] Limite de {TEMPO_MAXIMO_CAPTURA}s atingido. Processando comando...")
                resultado_final = json.loads(reconhecedor.FinalResult())
                comando = resultado_final.get("text", "").strip()

                if comando:
                    print(f"[USER] {comando}")
                    stream.stop_stream()

                    if led:
                        led.estado_processando_slm()

                    processar_comando_voz(comando)

                    if led:
                        led.estado_ouvindo_keyword()
                    stream.start_stream()
                else:
                    print("[INFO] Nenhum comando detectado após limite de tempo.")
                    print("-" * 40)
                    if led:
                        led.estado_ouvindo_keyword()

                ouvindo_comando = False
                reconhecedor.Reset()
                print(f"[STATUS] Aguardando palavra-chave: '{PALAVRA_CHAVE}'")
                continue

            if (time.time() - ultimo_tempo_voz) > TEMPO_SILENCIO:
                resultado_final = json.loads(reconhecedor.FinalResult())
                comando = resultado_final.get("text", "").strip()

                if comando:
                    print(f"[USER] {comando}")
                    stream.stop_stream()

                    if led:
                        led.estado_processando_slm()

                    processar_comando_voz(comando)

                    if led:
                        led.estado_ouvindo_keyword()
                    stream.start_stream()
                else:
                    print("[INFO] Nenhum comando detectado. Cancelando.")
                    print("-" * 40)
                    if led:
                        led.estado_ouvindo_keyword()

                ouvindo_comando = False
                reconhecedor.Reset()
                print(f"[STATUS] Aguardando palavra-chave: '{PALAVRA_CHAVE}'")

    except KeyboardInterrupt:
        print("\n[INFO] Encerrando Delta por Ctrl+C.")
    finally:
        with SuppressErrorOutput():
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            try:
                audio.terminate()
            except Exception:
                pass

        if led:
            led.parar()
        print("[INFO] Sistema finalizado.")


if __name__ == "__main__":
    main()
