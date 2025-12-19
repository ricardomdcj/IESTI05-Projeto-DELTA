import time
import board
import threading
import colorsys
import adafruit_dht
import adafruit_ahtx0
import adafruit_bmp280
from gpiozero import RGBLED

# --- CONFIGURACOES GERAIS ---
INTERVALO_LEITURA_SENSORES = 2.0  
PRESSAO_NIVEL_MAR = 1013.25       

# Ajuste Fino do LED
VELOCIDADE_RAINBOW = 0.005
PASSO_COR = 0.001

class GerenciadorLED:
    def __init__(self):
        try:
            self.led = RGBLED(red=13, green=19, blue=26, active_high=False)
            self.rodando = False
            self.thread = None
        except Exception as e:
            print(f"[ERRO] Falha ao iniciar LED: {e}")
            self.led = None

    def _efeito_rainbow(self):
        hue = 0
        while self.rodando:
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            if self.led:
                self.led.color = (r, g, b)
            
            hue += PASSO_COR
            if hue > 1.0: hue = 0
            
            time.sleep(VELOCIDADE_RAINBOW)

    def iniciar_rainbow(self):
        if self.led and not self.rodando:
            self.rodando = True
            self.thread = threading.Thread(target=self._efeito_rainbow)
            self.thread.daemon = True
            self.thread.start()
            print("[INFO] LED: Efeito Rainbow iniciado (Suave).")

    def parar(self):
        self.rodando = False
        if self.thread:
            self.thread.join()
        if self.led:
            self.led.off()

class Sensores:
    def __init__(self):
        self.i2c = board.I2C()
        self.dht = None
        self.aht = None
        self.bmp = None
        self._iniciar_hardware()

    def _iniciar_hardware(self):
        # 1. DHT22
        try:
            self.dht = adafruit_dht.DHT22(board.D4, use_pulseio=False)
        except Exception as e:
            print(f"[AVISO] DHT22 off: {e}")

        # 2. AHT20
        try:
            self.aht = adafruit_ahtx0.AHTx0(self.i2c)
        except Exception as e:
            print(f"[AVISO] AHT20 off: {e}")

        # 3. BMP280 (Tentativa Automatica)
        try:
            # Tenta sem endereco forçado (padrao 0x77)
            self.bmp = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c)
            self.bmp.sea_level_pressure = PRESSAO_NIVEL_MAR
        except ValueError:
            # Se falhar, tenta o endereco alternativo (0x76)
            try:
                self.bmp = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c, address=0x76)
                self.bmp.sea_level_pressure = PRESSAO_NIVEL_MAR
            except Exception as e:
                print(f"[AVISO] BMP280 off (0x76 falhou): {e}")
        except Exception as e:
            print(f"[AVISO] BMP280 off: {e}")

    def ler_todos(self):
        dados = {}
        # AHT20
        if self.aht:
            try:
                dados['AHT20'] = {'temp': self.aht.temperature, 'umid': self.aht.relative_humidity}
            except: pass
        
        # BMP280
        if self.bmp:
            try:
                dados['BMP280'] = {
                    'temp': self.bmp.temperature,
                    'pressao': self.bmp.pressure,
                    'altitude': self.bmp.altitude
                }
            except: pass

        # DHT22
        if self.dht:
            try:
                t = self.dht.temperature
                u = self.dht.humidity
                if t is not None: dados['DHT22'] = {'temp': t, 'umid': u}
            except RuntimeError: pass

        return dados

def main():
    print("--- MONITORAMENTO AMBIENTAL PRO ---")
    led = GerenciadorLED()
    sensores = Sensores()
    led.iniciar_rainbow()

    try:
        while True:
            leituras = sensores.ler_todos()
            print(f"\n[LEITURA] {time.strftime('%H:%M:%S')}")

            if 'AHT20' in leituras:
                d = leituras['AHT20']
                print(f"| AHT20  | {d['temp']:.1f}C | {d['umid']:.1f}%")
            
            if 'BMP280' in leituras:
                d = leituras['BMP280']
                print(f"| BMP280 | {d['temp']:.1f}C | {d['pressao']:.1f}hPa | Alt: {d['altitude']:.1f}m")
            
            if 'DHT22' in leituras:
                d = leituras['DHT22']
                print(f"| DHT22  | {d['temp']:.1f}C | {d['umid']:.1f}%")

            time.sleep(INTERVALO_LEITURA_SENSORES)
            
    except KeyboardInterrupt:
        print("\n[INFO] Parando...")
        led.parar()

if __name__ == "__main__":
    main()
