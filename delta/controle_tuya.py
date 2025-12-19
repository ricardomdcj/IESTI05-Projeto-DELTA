import sys
import tinytuya

# Precisa editar os devices com os valores dos seus dispositivos
# Exemplo:
#     "interruptor": {
#        "id": "ebe1219e5ab27c71e29pmz",
#        "ip": "192.168.0.174",
#        "key": "5m.S[8a>(Et#)L=.",
#        "version": 3.3,
#    }

DEVICES = {
    "interruptor": {
        "id": "id_here",
        "ip": "ip_here",
        "key": "key_here",
        "version": 3.4,
    },
    "ar": {
        "id": "id_here",
        "ip": "ip_here",
        "key": "key_here",
        "version": 3.3,
    },
    "lampada": {
        "id": "id_here",
        "ip": "ip_here",
        "key": "key_here"~)",
        "version": 3.5,
    },
}

DPS_MAP = {
    "interruptor": {
        "ventilador": "1",
        "speed": "3",
        "lamp": "5",
    },
    "ar": {
        "switch": "1",
        "temp": "2",
        "mode": "4",
        "wind": "5",
        "eco": "8",
        "light": "13",
        "lock": "14",
        "unit": "19",
        "swing": "33",
        "sleep": "102",
        "health": "106",
    },
    "lampada": {
        "modo": "multi",
        "brilho": "22",
        "temp": "23",
    },
}


def conectar_dispositivo(nome):
    cfg = DEVICES[nome]
    dev = tinytuya.OutletDevice(cfg["id"], cfg["ip"], cfg["key"])
    dev.set_version(cfg["version"])
    return dev


def parse_on_off(valor):
    if valor in ("on", "ligar", "true", "1"):
        return True
    if valor in ("off", "desligar", "false", "0"):
        return False
    return None


def processar_interruptor(comando, valor):
    if comando in ("ventilador", "lamp"):
        b = parse_on_off(valor)
        if b is None:
            print("Erro: use on/off.")
        return b

    if comando == "speed":
        if valor in ("level_1", "level_2", "level_3", "level_4", "level_5"):
            return valor
        mapa = {
            "1": "level_1",
            "baixo": "level_1",
            "low": "level_1",
            "2": "level_2",
            "medio_baixo": "level_2",
            "3": "level_3",
            "medio": "level_3",
            "middle": "level_3",
            "4": "level_4",
            "medio_alto": "level_4",
            "5": "level_5",
            "alto": "level_5",
            "high": "level_5",
        }
        if valor in mapa:
            return mapa[valor]
        print("Erro: velocidade inválida. Use 1-5.")
        return None

    print("Comando inválido para interruptor.")
    return None


def processar_ar(comando, valor):
    if comando in ("switch", "eco", "light", "lock", "swing", "sleep", "health"):
        b = parse_on_off(valor)
        if b is None:
            print("Erro: use on/off.")
        return b

    if comando == "temp":
        try:
            t = int(valor)
        except ValueError:
            print("Erro: temperatura inválida.")
            return None
        if 16 <= t <= 30:
            return t * 10
        print("Erro: temperatura deve estar entre 16 e 30 °C.")
        return None

    if comando == "mode":
        modos = {
            "frio": "cold",
            "cold": "cold",
            "cool": "cold",
            "seco": "wet",
            "wet": "wet",
            "dry": "wet",
            "ventilar": "wind",
            "wind": "wind",
            "fan": "wind",
            "auto": "auto",
            "automatico": "auto",
        }
        if valor in modos:
            return modos[valor]
        print("Erro: modos válidos: cold, wet, wind, auto.")
        return None

    if comando == "wind":
        velocidades = {
            "auto": "auto",
            "automatico": "auto",
            "mute": "mute",
            "off": "mute",
            "silencioso": "mute",
            "quieto": "mute",
            "low": "low",
            "baixo": "low",
            "mid": "mid",
            "medio": "mid",
            "high": "high",
            "alto": "high",
            "turbo": "high",
            "maximo": "high",
            "0": "mute",
            "1": "low",
            "2": "mid",
            "3": "high",
            "4": "high",
        }
        if valor in velocidades:
            if valor == "off":
                print("ar wind off -> mute (silencioso).")
            if valor in ("turbo", "maximo", "4"):
                print("Aviso: turbo no app equivale a high no protocolo local.")
            return velocidades[valor]
        print("Erro: use auto/mute/low/mid/high/off.")
        return None

    if comando == "unit":
        if valor in ("c", "celsius"):
            return "C"
        if valor in ("f", "fahrenheit"):
            return "F"
        print("Erro: use C ou F.")
        return None

    print("Comando inválido para ar.")
    return None


def processar_lampada(comando, valor):
    if comando == "modo":
        if valor in ("dia", "day", "branco", "white"):
            return {
                "21": "white",
                "22": 1000,
                "23": 1000,
            }
        if valor in ("noite", "night", "amarelo", "laranja", "warm"):
            return {
                "21": "white",
                "22": 450,
                "23": 100,
            }
        print("Erro: modos válidos para lâmpada: dia, noite.")
        return None

    if comando == "brilho":
        try:
            v = int(valor)
        except ValueError:
            print("Erro: brilho inválido.")
            return None
        if 1 <= v <= 100:
            v *= 10
        if not 10 <= v <= 1000:
            print("Erro: brilho deve estar entre 10-1000 ou 1-100%.")
            return None
        return v

    if comando == "temp":
        if valor in ("quente", "warm", "amarelo"):
            return 0
        if valor in ("frio", "cold", "branco"):
            return 1000
        try:
            v = int(valor)
        except ValueError:
            print("Erro: use 0-1000 ou quente/frio.")
            return None
        if not 0 <= v <= 1000:
            print("Erro: temperatura deve estar entre 0-1000.")
            return None
        return v

    print("Comando inválido para lâmpada.")
    return None


def mostrar_ajuda():
    print("=" * 70)
    print("CONTROLE TUYA - INTERRUPTOR / AR / LÂMPADA")
    print("=" * 70)
    print("\nInterruptor (ventilador + lâmpada de teto)")
    print("  python controle_tuya.py interruptor ventilador on/off")
    print("  python controle_tuya.py interruptor speed 1-5")
    print("  python controle_tuya.py interruptor lamp on/off")
    print("\nAr-condicionado")
    print("  python controle_tuya.py ar switch on/off")
    print("  python controle_tuya.py ar temp 24")
    print("  python controle_tuya.py ar mode cold")
    print("  python controle_tuya.py ar wind off       # equivale a mute")
    print("  python controle_tuya.py ar wind high")
    print("  python controle_tuya.py ar eco on/off")
    print("  python controle_tuya.py ar light on/off")
    print("  python controle_tuya.py ar swing on/off")
    print("  python controle_tuya.py ar sleep on/off")
    print("  python controle_tuya.py ar health on/off")
    print("  python controle_tuya.py ar lock on/off")
    print("\nLâmpada (ID eb5190d6da3b29f59bmm7b)")
    print("  python controle_tuya.py lampada modo dia")
    print("  python controle_tuya.py lampada modo noite")
    print("  python controle_tuya.py lampada brilho 60")
    print("  python controle_tuya.py lampada temp quente")
    print("\nStatus")
    print("  python controle_tuya.py <interruptor|ar|lampada> status")
    print("=" * 70)


def consultar_status(nome):
    dev = conectar_dispositivo(nome)
    resp = dev.status()
    dps = resp.get("dps")

    if not isinstance(dps, dict):
        print("Resposta bruta:", resp)
        return

    print(f"\n=== STATUS {nome.upper()} ===")
    if nome == "ar":
        for k, v in sorted(dps.items(), key=lambda x: int(x[0])):
            if k in ("2", "3") and isinstance(v, int):
                v = f"{v / 10:.1f}°C"
            print(f"  DPS {k:>3} = {v}")
    elif nome == "lampada":
        for k, v in sorted(dps.items(), key=lambda x: int(x[0])):
            if k == "22" and isinstance(v, int):
                v = f"{v} ({v / 10:.0f}%)"
            elif k == "23" and isinstance(v, int):
                if v < 300:
                    tom = "quente"
                elif v > 700:
                    tom = "frio"
                else:
                    tom = "neutro"
                v = f"{v} ({tom})"
            print(f"  DPS {k:>3} = {v}")
    else:
        for k, v in sorted(dps.items(), key=lambda x: int(x[0])):
            print(f"  DPS {k:>3} = {v}")


def main():
    if len(sys.argv) < 2:
        mostrar_ajuda()
        return

    nome = sys.argv[1].lower()
    if nome not in DEVICES:
        print("Dispositivo inválido. Use: interruptor, ar, lampada.")
        return

    if len(sys.argv) == 3 and sys.argv[2].lower() == "status":
        consultar_status(nome)
        return

    if len(sys.argv) < 4:
        mostrar_ajuda()
        return

    comando = sys.argv[2].lower()
    valor = sys.argv[3].lower()

    if comando not in DPS_MAP[nome]:
        print(f"Comando '{comando}' não disponível para {nome}.")
        print("Comandos válidos:", list(DPS_MAP[nome].keys()))
        return

    if nome == "interruptor":
        valor_final = processar_interruptor(comando, valor)
    elif nome == "ar":
        valor_final = processar_ar(comando, valor)
    else:
        valor_final = processar_lampada(comando, valor)

    if valor_final is None:
        return

    dev = conectar_dispositivo(nome)

    if nome == "lampada" and isinstance(valor_final, dict):
        for dps_id, v in valor_final.items():
            print(f"Enviando: DPS {dps_id} -> {v}")
            dev.set_value(int(dps_id), v)
        print("Comando concluído.")
        return

    dps_id = DPS_MAP[nome][comando]
    print(f"Enviando: DPS {dps_id} -> {valor_final}")
    dev.set_value(int(dps_id), valor_final)
    print("Comando concluído.")


if __name__ == "__main__":
    main()
