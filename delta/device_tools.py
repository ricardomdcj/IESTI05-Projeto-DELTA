import time
from controle_tuya import conectar_dispositivo, DPS_MAP 

# Modos e velocidades que realmente afetam o ar
VALID_MODES = {"cold", "wet", "wind", "auto"}
VALID_WIND  = {"auto", "mute", "low", "mid", "high"}

# Velocidades válidas para o ventilador de teto
VALID_FAN_SPEEDS = {"level_1", "level_2", "level_3", "level_4", "level_5"}

def set_ac_state(
    power: bool = True,
    target_temp_c = None,
    mode: str | None = None,
    wind: str | None = None,
    eco: bool | None = None,
    sleep: bool | None = None,
    swing: bool | None = None,
    health: bool | None = None,
) -> dict:
    """
    Controla o ar-condicionado de forma geral.
    Só aplica os parâmetros que forem diferentes de None.
    """
    dev = conectar_dispositivo("ar")
    changes: dict = {}

    # Liga/desliga
    if power is not None:
        p = bool(power)
        dev.set_value(int(DPS_MAP["ar"]["switch"]), p)
        changes["power"] = p
        
        if p is True:
            time.sleep(1.5)

    # Temperatura alvo (16–30 °C, protocolo usa valor*10)
    if target_temp_c is not None:
        t = float(target_temp_c)
        t = round(t)
        if t < 16:
            t = 16
        if t > 30:
            t = 30
        dev.set_value(int(DPS_MAP["ar"]["temp"]), t * 10)
        changes["target_temp_c"] = t

    # Modo de operação
    if mode is not None:
        m = str(mode).lower()
        if m in VALID_MODES:
            dev.set_value(int(DPS_MAP["ar"]["mode"]), m)
            changes["mode"] = m

    # Velocidade do vento
    if wind is not None:
        w = str(wind).lower()
        if w in VALID_WIND:
            dev.set_value(int(DPS_MAP["ar"]["wind"]), w)
            changes["wind"] = w

    # Booleanos auxiliares
    def _set_bool(dps_key: str, value, field: str):
        if value is None:
            return
        b = bool(value)
        dev.set_value(int(DPS_MAP["ar"][dps_key]), b)
        changes[field] = b

    _set_bool("eco",    eco,    "eco")
    _set_bool("sleep",  sleep,  "sleep")
    _set_bool("swing",  swing,  "swing")
    _set_bool("health", health, "health")

    return changes

def set_fan_state(power: bool = True, speed: str | int | None = None) -> dict:
    """
    Liga/desliga o ventilador de teto (interruptor Tuya) e opcionalmente ajusta a velocidade.

    Args:
        power: True para ligar, False para desligar
        speed: Velocidade do ventilador (1-5, "level_1"-"level_5", ou strings como "baixo", "medio", "alto")

    Returns:
        dict com as mudanças aplicadas
    """
    dev = conectar_dispositivo("interruptor")
    changes: dict = {}

    # Liga/desliga o ventilador
    if power is not None:
        p = bool(power)
        dev.set_value(int(DPS_MAP["interruptor"]["ventilador"]), p)
        changes["power"] = p

        # Aguarda um pouco se estiver ligando para garantir que o comando seja processado
        if p is True and speed is not None:
            time.sleep(0.5)

    # Ajusta a velocidade se fornecida
    if speed is not None:
        # Mapeamento de valores para os níveis válidos
        speed_map = {
            # Números
            1: "level_1", "1": "level_1",
            2: "level_2", "2": "level_2",
            3: "level_3", "3": "level_3",
            4: "level_4", "4": "level_4",
            5: "level_5", "5": "level_5",
            # Strings descritivas em português
            "baixo": "level_1", "low": "level_1",
            "medio_baixo": "level_2",
            "medio": "level_3", "middle": "level_3",
            "medio_alto": "level_4",
            "alto": "level_5", "high": "level_5",
            # Já no formato correto
            "level_1": "level_1",
            "level_2": "level_2",
            "level_3": "level_3",
            "level_4": "level_4",
            "level_5": "level_5",
        }

        # Converte para string se for int
        speed_key = speed if isinstance(speed, str) else speed
        speed_str = str(speed_key).lower()

        if speed_str in speed_map:
            final_speed = speed_map[speed_str]
            dev.set_value(int(DPS_MAP["interruptor"]["speed"]), final_speed)
            changes["speed"] = final_speed
        elif speed_str in VALID_FAN_SPEEDS:
            dev.set_value(int(DPS_MAP["interruptor"]["speed"]), speed_str)
            changes["speed"] = speed_str

    return changes
    
def set_ceiling_lamp_state(power: bool) -> dict:
    """
    Liga/desliga a lâmpada do ventilador de teto (luminária).
    Esta é a lâmpada simples controlada pelo interruptor (DPS 5).

    Args:
        power: True para ligar, False para desligar

    Returns:
        dict com as mudanças aplicadas
    """
    dev = conectar_dispositivo("interruptor")
    changes: dict = {}

    if power is not None:
        p = bool(power)
        dev.set_value(int(DPS_MAP["interruptor"]["lamp"]), p)
        changes["power"] = p

    return changes

def set_lamp_state(
    power: bool | None = None,
    mode: str | None = None,
    brightness: int | None = None,
    temperature: int | str | None = None,
) -> dict:
    """
    Controla a lâmpada RGB inteligente (dispositivo lampada).

    IMPORTANTE: Para que a lâmpada funcione, ela precisa estar com alimentação ligada.
    Use set_ceiling_lamp_state(True) no interruptor antes, se necessário.

    Args:
        power: True para ligar, False para desligar (controla via interruptor)
        mode: Modo pré-configurado ("dia", "noite", "white", "day", "night", "warm")
        brightness: Brilho de 1-100 (%) ou 10-1000 (escala direta)
        temperature: Temperatura de cor 0-1000 ou strings ("quente", "frio", "warm", "cold", "branco", "amarelo")
                    0=amarelo quente (2700K), 1000=branco frio (6500K)

    Returns:
        dict com as mudanças aplicadas
    """
    changes: dict = {}

    # Primeiro, controla a alimentação via interruptor se necessário
    if power is not None:
        interruptor_dev = conectar_dispositivo("interruptor")
        p = bool(power)
        interruptor_dev.set_value(int(DPS_MAP["interruptor"]["lamp"]), p)
        changes["power"] = p

        # Aguarda para garantir que a lâmpada esteja energizada
        if p is True:
            time.sleep(0.8)

    # Agora controla os parâmetros da lâmpada RGB
    dev = conectar_dispositivo("lampada")

    # Modo pré-configurado
    if mode is not None:
        mode_str = str(mode).lower()

        # Modos pré-definidos
        if mode_str in ("dia", "day", "branco", "white"):
            # Modo dia: branco frio máximo
            dev.set_value(21, "white")
            dev.set_value(22, 1000)
            dev.set_value(23, 1000)
            changes["mode"] = "dia"
            changes["brightness"] = 1000
            changes["temperature"] = 1000

        elif mode_str in ("noite", "night", "amarelo", "laranja", "warm"):
            # Modo noite: amarelo médio
            dev.set_value(21, "white")
            dev.set_value(22, 450)
            dev.set_value(23, 100)
            changes["mode"] = "noite"
            changes["brightness"] = 450
            changes["temperature"] = 100

    # Brilho individual
    if brightness is not None:
        b = int(brightness)

        # Se valor entre 1-100, considera porcentagem e multiplica por 10
        if 1 <= b <= 100:
            b = b * 10

        # Valida range 10-1000
        if b < 10:
            b = 10
        if b > 1000:
            b = 1000

        # Define work_mode como white se não estiver setado
        if "mode" not in changes:
            dev.set_value(21, "white")

        dev.set_value(22, b)
        changes["brightness"] = b

    # Temperatura de cor
    if temperature is not None:
        temp_map = {
            "quente": 0,
            "warm": 0,
            "amarelo": 0,
            "frio": 1000,
            "cold": 1000,
            "branco": 1000,
        }

        if isinstance(temperature, str):
            temp_str = temperature.lower()
            if temp_str in temp_map:
                t = temp_map[temp_str]
            else:
                try:
                    t = int(temperature)
                except ValueError:
                    t = None
        else:
            t = int(temperature)

        if t is not None:
            # Valida range 0-1000
            if t < 0:
                t = 0
            if t > 1000:
                t = 1000

            # Define work_mode como white se não estiver setado
            if "mode" not in changes:
                dev.set_value(21, "white")

            dev.set_value(23, t)
            changes["temperature"] = t

    return changes