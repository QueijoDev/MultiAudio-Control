import sys
import os
import subprocess
import time
def check_dependencies():
    """Verifica e tenta instalar dependências do pacote necessárias para o PyQt6 no Linux."""
    if sys.platform.startswith('linux'):
        import shutil
        if shutil.which("apt-get"):
            # Verifica se libxcb-cursor0 está instalado (Debian/Ubuntu)
            res = subprocess.run(["dpkg", "-s", "libxcb-cursor0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                print("Dependência 'libxcb-cursor0' não encontrada. Solicitando instalação...")
                if shutil.which("pkexec"):
                    try:
                        # Abre pedirha e instala
                        subprocess.run(["pkexec", "apt-get", "install", "-y", "libxcb-cursor0"], check=True)
                    except subprocess.CalledProcessError:
                        print("Falha na instalação ou cancelamento. O aplicativo pode não iniciar corretamente.")

check_dependencies()

from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QLabel, QCheckBox, QPushButton, QMessageBox, 
                             QFrame, QSlider)
from PyQt6.QtCore import Qt

class MultiAudioControl(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiAudio Control - Linux")
        self.setMinimumSize(550, 500)
        
        self.checkboxes = {}
        # Lista para armazenar apenas os IDs dos módulos que ESTE aplicativo criar
        self.loaded_modules = [] 
        
        self.init_ui()

    def decodificar_nome(self, nome_tecnico, descricao_sistema):
        """Converte nomes técnicos em nomes amigáveis, aproveitando a descrição do sistema como fallback."""
        tecnico = nome_tecnico.lower() + " " + descricao_sistema.lower()
        
        # Mantém seus ícones e nomes personalizados se encontrar suas placas específicas
        if "matisse" in tecnico or "pci-0000_09" in tecnico:
            return "🎧 Headset P2 (Analog Output)"
        if "g435" in tecnico:
            return "🎮 Logitech G435 (Wireless)"
        if "fifine" in tecnico:
            return "🎙️ Microfone Fifine"
        if "hdmi" in tecnico or "ga102" in tecnico:
            return "📺 Saída HDMI (Monitor/TV)"
            
        # Caso seja uma placa nova, genérica ou de outro PC, usa o nome de exibição nativo do próprio PulseAudio
        return f"🔈 {descricao_sistema}"

    def init_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        
        # Estilo Dark Pro
        self.setStyleSheet("""
            QMainWindow { background-color: #0f0f0f; }
            QLabel { color: white; font-family: 'Segoe UI'; }
            QFrame#Card { 
                background-color: #1e1e1e; 
                border-radius: 12px; 
                padding: 15px; 
                border: 1px solid #333;
            }
            QPushButton#Ativar { 
                background-color: #0078d4; color: white; padding: 15px; 
                border-radius: 8px; font-weight: bold; font-size: 14px;
            }
            QPushButton#Ativar:hover { background-color: #1086e5; }
            QPushButton#Reset { 
                background-color: #2b2b2b; color: #888; padding: 10px; border-radius: 8px; margin-top: 5px;
            }
            QSlider::handle:horizontal { background: #0078d4; width: 16px; border-radius: 8px; }
        """)

        header = QLabel("MultiAudio Control")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        self.layout.addWidget(header)
        
        subheader = QLabel("Selecione os dispositivos para saída simultânea")
        subheader.setStyleSheet("color: #888; margin-bottom: 10px;")
        self.layout.addWidget(subheader)
        
        self.device_container = QVBoxLayout()
        self.layout.addLayout(self.device_container)
        
        self.atualizar_lista()

        self.btn_ativar = QPushButton("⚡ ATIVAR ÁUDIO SIMULTÂNEO")
        self.btn_ativar.setObjectName("Ativar")
        self.btn_ativar.clicked.connect(self.ativar_multi_audio)
        self.layout.addWidget(self.btn_ativar)

        self.btn_reset = QPushButton("Resetar Configurações de Áudio")
        self.btn_reset.setObjectName("Reset")
        self.btn_reset.clicked.connect(self.resetar_sistema)
        self.layout.addWidget(self.btn_reset)

    def obter_dispositivos(self):
        """Usa o comando pactl para retornar os dispositivos de áudio com as descrições reais dadas pelo sistema."""
        dispositivos = []
        try:
            cmd = ["pactl", "list", "sinks"]
            
            # Força o idioma para inglês (C) para evitar erro no parsing em sistemas configurados em Português (Destino / Descrição)
            env_vars = os.environ.copy()
            env_vars["LC_ALL"] = "C"
            
            resultado = subprocess.check_output(cmd, text=True, env=env_vars)
            
            # Divide a saída em blocos de Sink (evita usar grep com pipe)
            blocos = resultado.split("Sink #")[1:]
            for bloco in blocos:
                nome = ""
                desc = ""
                for linha in bloco.splitlines():
                    linha = linha.strip()
                    if linha.startswith("Name:"):
                        nome = linha.split("Name:", 1)[1].strip()
                    elif linha.startswith("Description:"):
                        desc = linha.split("Description:", 1)[1].strip()
                if nome:
                    dispositivos.append((nome, desc))
        except Exception as e:
            print(f"Erro ao listar dispositivos com pactl: {e}")
        return dispositivos

    def atualizar_lista(self):
        """Lista os sinks ativos ignorando os virtuais criados pelo próprio app."""
        # BUGFIX: Limpar a variável de estado ao regerar a lista para não vazar memória / causar falhas
        self.checkboxes.clear()

        # Limpar widgets visuais antigos
        for i in reversed(range(self.device_container.count())): 
            widget_to_remove = self.device_container.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        sinks = self.obter_dispositivos()

        for s_name, s_desc in sinks:
            if "combined" in s_name or "MultiOut" in s_name or "virtual" in s_name: 
                continue
                
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)

            # Usa o nome com emojis e tratamento (fallback para a descrição do host)
            nome_amigavel = self.decodificar_nome(s_name, s_desc)
            
            cb = QCheckBox(nome_amigavel)
            cb.setStyleSheet("font-weight: bold; font-size: 14px;")
            card_layout.addWidget(cb)
            
            # Guarda pelo nome técnico
            self.checkboxes[s_name] = cb 

            vol_layout = QHBoxLayout()
            vol_icon = QLabel("🔈")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(80) 
            
            # BUGFIX DE PERFORMANCE CRÍTICA: Executar mudança de volume apenas ao *SOLTAR* a barra, não durante o drag.
            # Além de usar subprocess.run ao invés de os.system(string_formatada) que é mais seguro e rápido.
            slider.sliderReleased.connect(
                lambda s=slider, name=s_name: subprocess.run(
                    ["pactl", "set-sink-volume", name, f"{s.value()}%"], check=False
                )
            )
            
            vol_layout.addWidget(vol_icon)
            vol_layout.addWidget(slider)
            card_layout.addLayout(vol_layout)

            self.device_container.addWidget(card)

    def ativar_multi_audio(self):
        selecionados = [name for name, cb in self.checkboxes.items() if cb.isChecked()]
        
        if len(selecionados) < 2:
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos 2 saídas para sincronizar.")
            return

        try:
            self.resetar_sistema(mostrar_msg=False)
            time.sleep(0.3)

            # Cria Null-Sink e rastreia o ID gerado do módulo rodando o comando isolado!
            # Pactl load-module retorna o index (ex: 24)
            cmd_null = ["pactl", "load-module", "module-null-sink", 
                        "sink_name=MultiOut", 
                        "sink_properties=device.description=MultiAudio-Virtual", 
                        "rate=48000"]
            out_null = subprocess.check_output(cmd_null, text=True).strip()
            
            if out_null.isdigit():
                self.loaded_modules.append(out_null)
            
            for s in selecionados:
                # PipeWire lida com sincronização de tempo de forma nativa e muitas vezes briga com "adjust_time"
                # Aumentamos um pouco a margem de latência inicial (buffer) para evitar engasgos (crackles/robotic)
                latencia = 60 if "pci" in s else 40 
                cmd_loopback = ["pactl", "load-module", "module-loopback", 
                                "source=MultiOut.monitor", 
                                f"sink={s}", 
                                f"latency_msec={latencia}"]
                
                out_loop = subprocess.check_output(cmd_loopback, text=True).strip()
                if out_loop.isdigit():
                    self.loaded_modules.append(out_loop)
            
            # Define como saída principal do SO
            subprocess.run(["pactl", "set-default-sink", "MultiOut"], check=False)
            
            QMessageBox.information(self, "Sucesso", "MultiAudio Control ativado com sucesso!")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro no Pipewire/Pulseaudio: {str(e)}")

    def resetar_sistema(self, mostrar_msg=True):
        if not self.loaded_modules:
            if mostrar_msg:
                QMessageBox.information(self, "Info", "Não há nenhuma fusão de áudio rodando (criada por este app) para remover.")
            return

        # Limpeza Direcionada: Remove APENAS os ids de módulos que o programa em si ativou! (Isso não quebra o OBS do usuário)
        for module_id in self.loaded_modules:
            subprocess.run(["pactl", "unload-module", module_id], check=False)
            
        self.loaded_modules.clear()
        
        if mostrar_msg:
            QMessageBox.information(self, "Reset", "Os dispositivos virtuais isolados por esse app foram removidos e redefinidos.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MultiAudioControl()
    window.show()
    sys.exit(app.exec())