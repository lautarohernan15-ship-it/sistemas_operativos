from pathlib import Path
from modelos import Particion, validar_registro_proceso
from interfaz import renderizar_dashboard, mostrar_informe_estadistico


class Simulador:
    def __init__(self, archivo_procesos=None):
        self.tiempo_actual = 0
        self.procesos = []
        self.memoria_so = 100
        self.memoria_total_usuario = 450
        self.particiones = []

        self.cola_nuevo = []
        self.cola_listo = []
        self.cola_listo_suspendido = []
        self.cola_terminado = []
        self.proceso_ejecucion = None

        self.eventos_ciclo = []
        self.hubo_llegada = False
        self.hubo_fin = False

        self.modo_avance = "PASO"
        self.pid_objetivo = None

        if archivo_procesos is not None:
            self.cargar_procesos(archivo_procesos)
        self.particiones.append(Particion(1, self.memoria_so, self.memoria_total_usuario))

    def registrar_evento(self, categoria, mensaje):
        self.eventos_ciclo.append((categoria, mensaje))

    def cargar_procesos(self, ruta):
        ruta = Path(ruta)
        ids_vistos = set()
        procesos_validos = []
        errores = []
        with open(ruta, "r", encoding="utf-8-sig") as f:
            for numero_linea, linea in enumerate(f, start=1):
                linea = linea.strip()
                if not linea or linea.startswith("#"):
                    continue
                proceso, error = validar_registro_proceso(linea, ids_vistos)
                if error:
                    errores.append(f"Línea {numero_linea}: {error}.")
                else:
                    procesos_validos.append(proceso)

        for error in errores:
            print(f"[ERROR] {error}")
        if len(procesos_validos) > 10:
            descartados = ", ".join(p.pid for p in procesos_validos[10:])
            print(
                f"[AVISO] Se conservan los primeros 10 procesos válidos; "
                f"se descartan: {descartados}."
            )
        self.procesos = procesos_validos[:10]
        self.procesos.sort(key=lambda x: x.arribo)

    def grado_multiprogramacion_activo(self):
        ejec = 1 if self.proceso_ejecucion else 0
        return ejec + len(self.cola_listo) + len(self.cola_listo_suspendido)

    def asignar_memoria_best_fit(self, proceso):
        mejor_particion = None
        min_espacio_sobrante = float("inf")

        for p in self.particiones:
            if p.pid is None and p.tamano >= proceso.tamano:
                sobrante = p.tamano - proceso.tamano
                if sobrante < min_espacio_sobrante:
                    min_espacio_sobrante = sobrante
                    mejor_particion = p

        if mejor_particion:
            idx = self.particiones.index(mejor_particion)
            if min_espacio_sobrante > 0:
                nueva_libre = Particion(
                    max(part.id for part in self.particiones) + 1,
                    mejor_particion.inicio + proceso.tamano,
                    min_espacio_sobrante,
                )
                mejor_particion.tamano = proceso.tamano
                self.particiones.insert(idx + 1, nueva_libre)

            mejor_particion.pid = proceso.pid
            mejor_particion.fragmentacion_interna = 0
            return mejor_particion
        return None

    def liberar_memoria(self, pid):
        for p in self.particiones:
            if p.pid == pid:
                p.pid = None
                p.fragmentacion_interna = 0

        i = 0
        while i < len(self.particiones) - 1:
            if self.particiones[i].pid is None and self.particiones[i + 1].pid is None:
                self.particiones[i].tamano += self.particiones[i + 1].tamano
                self.particiones.pop(i + 1)
            else:
                i += 1

    def ejecutar_ciclo_completo(self):
        self.eventos_ciclo.clear()
        self.hubo_llegada = False
        self.hubo_fin = False

        # 1. Registrar llegadas en el tiempo actual
        for p in self.procesos:
            if (
                p.arribo == self.tiempo_actual
                and p.estado == "Nuevo"
                and p not in self.cola_nuevo
                and p not in self.cola_listo
                and p not in self.cola_listo_suspendido
                and p not in self.cola_terminado
                and p is not self.proceso_ejecucion
            ):
                self.cola_nuevo.append(p)
                self.hubo_llegada = True
                self.registrar_evento(
                    "LLEGADA",
                    f"{p.pid} ingresa al sistema (Tam: {p.tamano} KB, CPU: {p.irrupcion}) -> Cola NUEVO.",
                )

        # 2. Admisión desde NUEVO
        while self.cola_nuevo:
            if self.grado_multiprogramacion_activo() >= 5:
                self.registrar_evento(
                    "LÍMITE MP",
                    "Grado de multiprogramación al máximo (5/5). Restantes esperan en NUEVO.",
                )
                break

            proc = self.cola_nuevo[0]
            part_asignada = self.asignar_memoria_best_fit(proc)
            if part_asignada:
                self.cola_nuevo.pop(0)
                proc.estado = "Listo"
                self.cola_listo.append(proc)
                numero_particion = self.particiones.index(part_asignada) + 1
                self.registrar_evento(
                    "ADMISIÓN",
                    f"{proc.pid} obtiene RAM (Part. {numero_particion}: "
                    f"{part_asignada.inicio}-{part_asignada.fin}) por Best-Fit -> LISTOS.",
                )
            else:
                self.cola_nuevo.pop(0)
                proc.estado = "Listo/Suspendido"
                self.cola_listo_suspendido.append(proc)
                self.registrar_evento(
                    "SUSPENSIÓN",
                    f"{proc.pid} sale de NUEVO sin bloque contiguo de {proc.tamano} KB -> LISTOS/SUSPENDIDOS.",
                )

        # 2.1 Intentar reubicar suspendidos (SWAP-IN)
        i = 0
        while i < len(self.cola_listo_suspendido):
            proc = self.cola_listo_suspendido[i]
            part_asignada = self.asignar_memoria_best_fit(proc)
            if part_asignada:
                self.cola_listo_suspendido.pop(i)
                proc.estado = "Listo"
                self.cola_listo.append(proc)
                numero_particion = self.particiones.index(part_asignada) + 1
                self.registrar_evento(
                    "SWAP-IN",
                    f"{proc.pid} obtiene RAM en Part. {numero_particion} "
                    f"({part_asignada.inicio}-{part_asignada.fin}) -> Pasa a LISTOS.",
                )
            else:
                i += 1

        # 3. Planificación SRTF y Ejecución de 1 u.t.
        candidatos = self.cola_listo.copy()
        if self.proceso_ejecucion:
            candidatos.append(self.proceso_ejecucion)

        if candidatos:
            candidatos.sort(
                key=lambda x: (
                    x.restante,
                    x.arribo,
                    0 if x is self.proceso_ejecucion else 1,
                )
            )
            seleccionado = candidatos[0]

            if self.proceso_ejecucion and self.proceso_ejecucion.pid != seleccionado.pid:
                desalojado = self.proceso_ejecucion
                self.registrar_evento(
                    "DESALOJO",
                    f"{seleccionado.pid} (Rest: {seleccionado.restante}) expropia la CPU a {desalojado.pid} (Rest: {desalojado.restante}).",
                )
                desalojado.estado = "Listo"
                if desalojado not in self.cola_listo:
                    self.cola_listo.append(desalojado)
                self.cola_listo.remove(seleccionado)
                self.proceso_ejecucion = seleccionado
                self.proceso_ejecucion.estado = "Ejecución"

            elif not self.proceso_ejecucion:
                self.cola_listo.remove(seleccionado)
                self.proceso_ejecucion = seleccionado
                self.proceso_ejecucion.estado = "Ejecución"
                self.registrar_evento(
                    "CPU / SRTF",
                    f"CPU libre: ingresa {seleccionado.pid} desde LISTOS (Restante: {seleccionado.restante} u.t.).",
                )
            elif len(candidatos) > 1:
                self.registrar_evento(
                    "CPU / SRTF",
                    f"Continúa {seleccionado.pid} en CPU por tener menor tiempo restante ({seleccionado.restante} u.t.).",
                )
        else:
            self.registrar_evento("CPU IDLE", "No hay procesos en cola de LISTOS; procesador inactivo.")

        if self.proceso_ejecucion:
            if self.proceso_ejecucion.tiempo_comienzo == -1:
                self.proceso_ejecucion.tiempo_comienzo = self.tiempo_actual

            self.proceso_ejecucion.restante -= 1
            self.registrar_evento(
                "EJECUCIÓN",
                f"{self.proceso_ejecucion.pid} ejecuta 1 u.t. de ráfaga (Restante: {self.proceso_ejecucion.restante} u.t.).",
            )

        # 4. Finalización si la irrupción restante llega a 0
        if self.proceso_ejecucion and self.proceso_ejecucion.restante == 0:
            self.hubo_fin = True
            proceso = self.proceso_ejecucion
            proceso.estado = "Terminado"
            proceso.retorno = self.tiempo_actual + 1 - proceso.arribo
            proceso.espera = proceso.retorno - proceso.irrupcion
            self.registrar_evento(
                "FIN PROCESO",
                f"{proceso.pid} pasa a TERMINADOS y libera {proceso.tamano} KB.",
            )
            self.liberar_memoria(proceso.pid)
            self.cola_terminado.append(proceso)
            self.proceso_ejecucion = None

    def _debe_mostrar_pausa(self):
        if self.modo_avance == "COMPLETO":
            return False
        if self.modo_avance == "EVENTO":
            return self.hubo_llegada or self.hubo_fin
        if self.modo_avance == "PROCESO":
            en_cpu = self.proceso_ejecucion and self.proceso_ejecucion.pid.upper() == self.pid_objetivo
            en_eventos = any(self.pid_objetivo in msg.upper() for _, msg in self.eventos_ciclo)
            return en_cpu or en_eventos
        return True  # Modo PASO por defecto (avanza 1 unidad de tiempo T por Enter)

    def _pedir_comando_pausa(self):
        renderizar_dashboard(self, f"- CICLO T = {self.tiempo_actual}")
        pids_disponibles = {p.pid.upper(): p.pid for p in self.procesos}

        while True:
            cmd = input(
                "  [Enter] Siguiente T (+1) | [E] Próx. evento | [C] Completo | [PID ej: P1] Seguir proceso: "
            ).strip().upper()

            if cmd == "":
                self.modo_avance = "PASO"
                break
            if cmd == "E":
                self.modo_avance = "EVENTO"
                break
            if cmd == "C":
                self.modo_avance = "COMPLETO"
                break
            if cmd in pids_disponibles:
                proc_obj = next(p for p in self.procesos if p.pid.upper() == cmd)
                if proc_obj.estado == "Terminado":
                    print(f"  [AVISO] El proceso {proc_obj.pid} ya ha terminado.")
                    continue
                self.modo_avance = "PROCESO"
                self.pid_objetivo = cmd
                break

            print(f"  Comando inválido. Use Enter, E, C o un ID válido ({', '.join(pids_disponibles.values())}).")

    def iniciar_simulacion(self):
        if not self.procesos:
            print("No hay procesos cargados en el archivo seleccionado.")
            return False

        while len(self.cola_terminado) < len(self.procesos):
            # Ejecutamos el ciclo completo de la unidad de tiempo T de forma unificada y limpia
            self.ejecutar_ciclo_completo()

            if self._debe_mostrar_pausa():
                self._pedir_comando_pausa()

            self.tiempo_actual += 1

        if self.modo_avance == "COMPLETO":
            renderizar_dashboard(self, "- SIMULACIÓN COMPLETADA")

        mostrar_informe_estadistico(self)
        return True
