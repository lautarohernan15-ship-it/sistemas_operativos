import os
import sys
from pathlib import Path


def carpeta_base():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def elegir_archivo_procesos():
    base = carpeta_base()
    opciones = []
    rutas_vistas = set()

    principal = base / "procesos.txt"
    if principal.is_file():
        opciones.append(("procesos.txt (archivo principal)", principal))
        rutas_vistas.add(os.path.normcase(str(principal.resolve())))

    for carpeta in (base, base / "ejemplos"):
        if carpeta.is_dir():
            archivos = sorted(
                (archivo for archivo in carpeta.glob("*.txt")
                 if archivo.stem.lower().startswith("ejemplo")),
                key=lambda archivo: archivo.name.lower()
            )
            for archivo in archivos:
                ruta_normalizada = os.path.normcase(str(archivo.resolve()))
                if ruta_normalizada not in rutas_vistas:
                    opciones.append((archivo.stem.replace("_", " "), archivo))
                    rutas_vistas.add(ruta_normalizada)

    while True:
        print("\n" + "═" * 60)
        print("  SELECCIÓN DE ARCHIVO DE PROCESOS")
        print("═" * 60)

        for i, (nombre, _) in enumerate(opciones, start=1):
            print(f"  [{i}] {nombre}")

        print("  [0] Volver al menú anterior")

        eleccion = input("\n  Seleccione un archivo: ").strip()
        if not eleccion.isdigit():
            print("  Opción inválida.")
            continue

        n = int(eleccion)
        if n == 0:
            return None
        if 1 <= n <= len(opciones):
            return opciones[n - 1][1].resolve()

        print("  Opción inválida.")


def solicitar_ruta_txt():
    base = carpeta_base()
    while True:
        ruta_ingresada = input(
            "  Ruta del archivo .txt (o 0 para volver): "
        ).strip()
        if ruta_ingresada == "0":
            return None
        if (
            len(ruta_ingresada) >= 2
            and ruta_ingresada[0] == ruta_ingresada[-1]
            and ruta_ingresada[0] in ("'", '"')
        ):
            ruta_ingresada = ruta_ingresada[1:-1]
        ruta = Path(ruta_ingresada).expanduser()
        if not ruta.is_absolute():
            ruta = base / ruta
        if ruta.suffix.lower() != ".txt":
            print("  [ERROR] El archivo debe tener extensión .txt.")
        elif not ruta.is_file():
            print(f"  [ERROR] No se encontró el archivo: {ruta}")
        else:
            return ruta.resolve()


class Proceso:
    def __init__(self, pid, tamano, arribo, irrupcion):
        self.pid = pid
        self.tamano = int(tamano)
        self.arribo = int(arribo)
        self.irrupcion = int(irrupcion)
        self.restante = int(irrupcion)
        self.estado = "Nuevo"  # Nuevo, Listo, Listo/Suspendido, Ejecución, Terminado
        self.espera = 0
        self.retorno = 0
        self.tiempo_comienzo = -1


def validar_registro_proceso(linea, ids_vistos):
    partes = [parte.strip() for parte in linea.split(",")]
    if len(partes) != 4:
        return None, "se esperaban cuatro campos separados por comas"

    pid = partes[0]
    if not pid:
        return None, "el identificador no puede estar vacío"
    if pid in ids_vistos:
        return None, f"el identificador {pid} está repetido"

    try:
        tamano, arribo, irrupcion = (int(valor) for valor in partes[1:])
    except ValueError:
        return None, "tamaño, arribo e irrupción deben ser números enteros"

    if not 1 <= tamano <= 450:
        return None, "el tamaño debe estar entre 1 y 450 KB"
    if arribo < 0:
        return None, "el tiempo de arribo no puede ser negativo"
    if irrupcion < 1:
        return None, "la irrupción debe ser de al menos 1 unidad"

    ids_vistos.add(pid)
    return Proceso(pid, tamano, arribo, irrupcion), None


class Particion:
    def __init__(self, id_particion, inicio, tamano, pid=None):
        self.id = id_particion
        self.inicio = int(inicio)
        self.tamano = int(tamano)
        self.pid = pid  # None si está libre, o el ID del proceso si está ocupada
        self.fragmentacion_interna = 0

    @property
    def fin(self):
        return self.inicio + self.tamano - 1


class Simulador:
    ANCHO_UI = 84

    def __init__(self, archivo_procesos=None):
        self.tiempo_actual = 0
        self.procesos = []
        self.memoria_so = 100
        self.memoria_total_usuario = 450
        self.particiones = []

        # Colas de estados
        self.cola_nuevo = []
        self.cola_listo = []
        self.cola_listo_suspendido = []
        self.cola_terminado = []
        self.proceso_ejecucion = None

        # Registro de eventos del ciclo actual
        self.eventos_ciclo = []
        self.hubo_llegada = False
        self.hubo_fin = False

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
                if not linea or linea.startswith('#'):
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
        min_espacio_sobrante = float('inf')

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
                    min_espacio_sobrante
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

        # Fusionar particiones libres adyacentes
        i = 0
        while i < len(self.particiones) - 1:
            if self.particiones[i].pid is None and self.particiones[i + 1].pid is None:
                self.particiones[i].tamano += self.particiones[i + 1].tamano
                self.particiones.pop(i + 1)
            else:
                i += 1

    def fase_llegadas(self):
        self.eventos_ciclo.clear()
        self.hubo_llegada = False

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
                    f"{p.pid} ingresa al sistema (Tam: {p.tamano} KB, CPU: {p.irrupcion}) -> Cola NUEVO."
                )

    def fase_admision(self):
        # 2. Admitir procesos en NUEVO
        while self.cola_nuevo:
            if self.grado_multiprogramacion_activo() >= 5:
                self.registrar_evento(
                    "LÍMITE MP",
                    "Grado de multiprogramación al máximo (5/5). Restantes esperan en NUEVO."
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
                    f"{part_asignada.inicio}-{part_asignada.fin}) por Best-Fit -> LISTOS."
                )
            else:
                self.cola_nuevo.pop(0)
                proc.estado = "Listo/Suspendido"
                self.cola_listo_suspendido.append(proc)
                self.registrar_evento(
                    "SUSPENSIÓN",
                    f"{proc.pid} sale de NUEVO sin bloque contiguo de {proc.tamano} KB -> LISTOS/SUSPENDIDOS."
                )

        # 2.1 Intentar reubicar suspendidos en RAM si hay espacio
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
                    f"({part_asignada.inicio}-{part_asignada.fin}) -> Pasa a LISTOS."
                )
            else:
                i += 1

    def fase_cpu(self):
        self.hubo_fin = False

        # 3. Planificación de Corto Plazo - SRTF
        candidatos = self.cola_listo.copy()
        if self.proceso_ejecucion:
            candidatos.append(self.proceso_ejecucion)

        if candidatos:
            candidatos.sort(
                key=lambda x: (
                    x.restante,
                    x.arribo,
                    0 if x is self.proceso_ejecucion else 1
                )
            )
            seleccionado = candidatos[0]

            if self.proceso_ejecucion and self.proceso_ejecucion.pid != seleccionado.pid:
                desalojado = self.proceso_ejecucion
                self.registrar_evento(
                    "DESALOJO",
                    f"{seleccionado.pid} (Rest: {seleccionado.restante}) expropia la CPU a {desalojado.pid} (Rest: {desalojado.restante})."
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
                    f"CPU libre: ingresa {seleccionado.pid} desde LISTOS (Restante: {seleccionado.restante} u.t.)."
                )
            elif len(candidatos) > 1:
                self.registrar_evento(
                    "CPU / SRTF",
                    f"Continúa {seleccionado.pid} en CPU por tener menor tiempo restante ({seleccionado.restante} u.t.)."
                )
        else:
            self.registrar_evento("CPU IDLE", "No hay procesos en cola de LISTOS; procesador inactivo.")

        # 4. Ejecución de 1 unidad de tiempo en CPU
        if self.proceso_ejecucion:
            if self.proceso_ejecucion.tiempo_comienzo == -1:
                self.proceso_ejecucion.tiempo_comienzo = self.tiempo_actual

            self.proceso_ejecucion.restante -= 1
            self.registrar_evento(
                "EJECUCIÓN",
                f"{self.proceso_ejecucion.pid} ejecuta 1 u.t. de ráfaga (Restante: {self.proceso_ejecucion.restante} u.t.)."
            )

        self.hubo_fin = bool(
            self.proceso_ejecucion and self.proceso_ejecucion.restante == 0
        )

    def fase_finalizacion(self):
        if not self.proceso_ejecucion or self.proceso_ejecucion.restante != 0:
            return

        proceso = self.proceso_ejecucion
        proceso.estado = "Terminado"
        proceso.retorno = self.tiempo_actual + 1 - proceso.arribo
        proceso.espera = proceso.retorno - proceso.irrupcion
        self.registrar_evento(
            "FIN PROCESO",
            f"{proceso.pid} pasa a TERMINADOS y libera {proceso.tamano} KB."
        )
        self.liberar_memoria(proceso.pid)
        self.cola_terminado.append(proceso)
        self.proceso_ejecucion = None

    # =========================================================================
    # INTERFAZ DE CONSOLA (GRILLA DE COLAS + TABLA CENTRADA)
    # =========================================================================
    def _imprimir_cola_grilla(self, titulo, items):
        """
        Dibuja la etiqueta de la cola con borde doble centrada y a su derecha
        los procesos en casilleros de grilla con borde simple.
        """
        ancho_lbl = 22
        top_lbl = f"  ╔{'═' * ancho_lbl}╗"
        mid_lbl = f"  ║{titulo:^{ancho_lbl}}║"
        bot_lbl = f"  ╚{'═' * ancho_lbl}╝"

        if not items:
            print(top_lbl)
            print(f"{mid_lbl} ──> [ Vacía ]")
            print(bot_lbl)
            return

        # Hasta 4 casilleros por fila para mantener el margen prolijo
        max_por_fila = 4
        filas = [items[i:i + max_por_fila] for i in range(0, len(items), max_por_fila)]

        for idx_fila, fila in enumerate(filas):
            # Cada casillero tiene el ancho del texto + 2 espacios internos
            anchos = [len(texto) + 2 for texto in fila]

            top_boxes = " ".join(f"┌{'─' * a}┐" for a in anchos)
            bot_boxes = " ".join(f"└{'─' * a}┘" for a in anchos)

            # El primer casillero recibe el conector "──┤", los siguientes tienen borde "│"
            celdas_medio = []
            for j, (texto, a) in enumerate(zip(fila, anchos)):
                borde_izq = "┤" if j == 0 else "│"
                celdas_medio.append(f"{borde_izq}{texto:^{a}}│")
            mid_boxes = " ".join(celdas_medio)

            if idx_fila == 0:
                print(f"{top_lbl}   {top_boxes}")
                print(f"{mid_lbl} ──{mid_boxes}")
                print(f"{bot_lbl}   {bot_boxes}")
            else:
                sangria = " " * (ancho_lbl + 4)
                print(f"{sangria}   {top_boxes}")
                print(f"{sangria} ↳─{mid_boxes}")
                print(f"{sangria}   {bot_boxes}")

    def renderizar_dashboard(self, fase=""):
        w = self.ANCHO_UI
        mp = self.grado_multiprogramacion_activo()

        # 1. ENCABEZADO LIMPIO Y ESTADO DEL PROCESADOR EN LÍNEA
        print("\n" + "═" * w)
        titulo = "SIMULADOR DE MEMORIA (MVT) Y PLANIFICACIÓN (SRTF)"
        print(f"{titulo:^{w}}")
        print("═" * w)

        info_tiempo = f"TIEMPO ACTUAL : T = {self.tiempo_actual}"
        info_mp = f"MULTIPROGRAMACIÓN : {mp} / 5 procesos activos"
        print(f"  {info_tiempo:<38} {info_mp}")

        if self.proceso_ejecucion:
            p = self.proceso_ejecucion
            estado_cpu = f"En ejecución -> {p.pid} (Tamaño: {p.tamano} KB | Restante: {p.restante} de {p.irrupcion} u.t.)"
        else:
            estado_cpu = "Inactivo (Idle) -> Sin procesos en ejecución"

        print(f"  ESTADO CPU    : {estado_cpu}")
        print("─" * w)

        # 2. TABLA DE PARTICIONES DE MEMORIA (Centrada con Dir. Inicio y Dir. Final)
        c1, c2, c3, c4, c5, c6 = 6, 13, 13, 13, 16, 12
        print("\n  > MAPA DE PARTICIONES DE MEMORIA (MVT - Best Fit | SO: 100 KB + Usuario: 450 KB)")
        print(f"  ┌{'─'*c1}┬{'─'*c2}┬{'─'*c3}┬{'─'*c4}┬{'─'*c5}┬{'─'*c6}┐")
        print(f"  │{'ID':^{c1}}│{'Dir. Inicio':^{c2}}│{'Dir. Final':^{c3}}│{'Tamaño (KB)':^{c4}}│{'Estado / PID':^{c5}}│{'Frag. Int.':^{c6}}│")
        print(f"  ├{'─'*c1}┼{'─'*c2}┼{'─'*c3}┼{'─'*c4}┼{'─'*c5}┼{'─'*c6}┤")

        # Fila del Sistema Operativo (0 a 99)
        print(f"  │{'SO':^{c1}}│{0:^{c2}}│{self.memoria_so - 1:^{c3}}│{self.memoria_so:^{c4}}│{'SISTEMA OP.':^{c5}}│{'0 KB':^{c6}}│")

        for indice, part in enumerate(self.particiones, start=1):
            if part.pid is None:
                estado_str = "LIBRE"
                frag_str = "---"
            else:
                estado_str = f"Ocupado ({part.pid})"
                frag_str = f"{part.fragmentacion_interna} KB"

            print(
                f"  │{indice:^{c1}}│{part.inicio:^{c2}}│{part.fin:^{c3}}│"
                f"{part.tamano:^{c4}}│{estado_str:^{c5}}│{frag_str:^{c6}}│"
            )
        print(f"  └{'─'*c1}┴{'─'*c2}┴{'─'*c3}┴{'─'*c4}┴{'─'*c5}┴{'─'*c6}┘")

        # 3. ESTADO DE LAS COLAS DE PROCESOS (Variante B - Grilla con etiquetas diferenciadas)
        print("\n  > ESTADO DE LAS COLAS DE PROCESOS")
        nodos_nuevos = [f"{p.pid} ({p.tamano}KB)" for p in self.cola_nuevo]
        listos_ordenados = sorted(
            self.cola_listo, key=lambda p: (p.restante, p.arribo)
        )
        nodos_listos = [f"{p.pid} (Rest:{p.restante})" for p in listos_ordenados]
        nodos_susp = [f"{p.pid} ({p.tamano}KB)" for p in self.cola_listo_suspendido]
        nodos_term = [f"{p.pid}" for p in self.cola_terminado]

        self._imprimir_cola_grilla("Cola de NUEVOS", nodos_nuevos)
        self._imprimir_cola_grilla("Cola de LISTOS", nodos_listos)
        self._imprimir_cola_grilla("LISTOS / SUSPENDIDOS", nodos_susp)
        self._imprimir_cola_grilla("Cola de TERMINADOS", nodos_term)

        # 4. HISTORIAL DE MOVIMIENTOS DEL CICLO
        print(f"\n  > HISTORIAL DE MOVIMIENTOS DEL CICLO (T = {self.tiempo_actual}) {fase}")
        total_ev = len(self.eventos_ciclo)
        for idx, (tag, msg) in enumerate(self.eventos_ciclo):
            conector = "└─" if idx == total_ev - 1 else "├─"
            tag_fmt = f"[{tag}]"
            print(f"   {conector} {tag_fmt:<14} {msg}")

        print("─" * w)

    def iniciar_simulacion(self):
        if not self.procesos:
            print("No hay procesos cargados en el archivo seleccionado.")
            return False

        print("═" * self.ANCHO_UI)
        print("  MODO DE EJECUCIÓN DEL SIMULADOR")
        print("═" * self.ANCHO_UI)
        print("  [1] Se ejecuta paso a paso en cada unidad de tiempo (T= 0, 1, 2...)")
        print("  [2] Se pausa solo en llegadas o finalizaciones de procesos")
        print("  [0] Volver al menú principal")
        while True:
            opcion = input(
                "\n  Seleccione una opción (Enter para [1]): "
            ).strip()
            if opcion in ("", "1", "2", "0"):
                break
            print("  Opción inválida. Seleccione 1, 2 o 0.")
        if opcion == "0":
            return False
        solo_eventos_guia = (opcion == "2")

        while len(self.cola_terminado) < len(self.procesos):
            # FASE 1: registrar llegadas y mostrar NUEVO
            self.fase_llegadas()

            if self.hubo_llegada:
                self.renderizar_dashboard("- FASE 1: LLEGADA A NUEVO")
                input("  Presione [Enter] para continuar con la admisión y ejecución...")

            # FASE 2: admisión y SWAP-IN
            n_previos = len(self.eventos_ciclo)
            self.fase_admision()

            hubo_movimiento = any(
                tag in ("ADMISIÓN", "SUSPENSIÓN", "SWAP-IN")
                for tag, _ in self.eventos_ciclo[n_previos:]
            )
            hubo_swap_in = any(
                tag == "SWAP-IN" for tag, _ in self.eventos_ciclo[n_previos:]
            )
            if hubo_movimiento and (
                not solo_eventos_guia or self.hubo_llegada or hubo_swap_in
            ):
                self.renderizar_dashboard("- FASE 2: ADMISIÓN (NUEVO -> LISTOS)")
                input("  Presione [Enter] para continuar con la planificación y ejecución...")

            # FASE 3: planificación SRTF y ejecución de una unidad
            self.fase_cpu()

            if (not solo_eventos_guia) or self.hubo_fin or self.tiempo_actual == 0:
                self.renderizar_dashboard("- FASE 3: CPU (SRTF Y EJECUCIÓN)")
                input("  Presione [Enter] para avanzar al siguiente ciclo...")

            # FASE 4: finalización después de mostrar la ráfaga en cero
            if self.hubo_fin:
                self.fase_finalizacion()
                self.renderizar_dashboard("- FASE 4: FINALIZACIÓN")
                input("  Presione [Enter] para continuar...")

            self.tiempo_actual += 1

        self.mostrar_informe_estadistico()
        return True

    def mostrar_informe_estadistico(self):
        w = self.ANCHO_UI
        c1, c2, c3, c4, c5 = 12, 16, 16, 16, 14

        print("\n" + "═" * w)
        print(f"{'INFORME ESTADÍSTICO FINAL DE LA SIMULACIÓN':^{w}}")
        print("═" * w)

        print(f"\n  ┌{'─'*c1}┬{'─'*c2}┬{'─'*c3}┬{'─'*c4}┬{'─'*c5}┐")
        print(f"  │{'Proceso':^{c1}}│{'T. Arribo':^{c2}}│{'T. Irrupción':^{c3}}│{'T. Retorno':^{c4}}│{'T. Espera':^{c5}}│")
        print(f"  ├{'─'*c1}┼{'─'*c2}┼{'─'*c3}┼{'─'*c4}┼{'─'*c5}┤")

        t_retorno_total = 0
        t_espera_total = 0

        for p in self.cola_terminado:
            print(
                f"  │{p.pid:^{c1}}│{p.arribo:^{c2}}│{p.irrupcion:^{c3}}│"
                f"{p.retorno:^{c4}}│{p.espera:^{c5}}│"
            )
            t_retorno_total += p.retorno
            t_espera_total += p.espera

        print(f"  └{'─'*c1}┴{'─'*c2}┴{'─'*c3}┴{'─'*c4}┴{'─'*c5}┘")

        n = len(self.procesos)
        prom_retorno = t_retorno_total / n
        prom_espera = t_espera_total / n
        rendimiento = n / self.tiempo_actual

        print("\n  > MÉTRICAS GLOBALES DEL SISTEMA")
        print(f"   ├─ Tiempo Total Simulado             : {self.tiempo_actual} unidades de tiempo")
        print(f"   ├─ Tiempo Promedio de Retorno (TAT)  : {prom_retorno:.2f} unidades de tiempo")
        print(f"   ├─ Tiempo Promedio de Espera (WT)    : {prom_espera:.2f} unidades de tiempo")
        print(f"   └─ Rendimiento (Throughput)          : {rendimiento:.4f} procesos / unidad de tiempo")
        print("═" * w + "\n")


def cargar_procesos_manualmente():
    print("\n  Ingrese un proceso por línea: ID, tamaño, arribo, irrupción")
    print("  Escriba 'fin' para terminar o 'cancelar' para volver.")
    procesos = []
    ids_vistos = set()

    while len(procesos) < 10:
        linea = input(f"  Proceso {len(procesos) + 1}: ").strip()
        if linea.lower() in ("cancelar", "0"):
            return None
        if linea.lower() in ("fin", "listo") or not linea:
            break
        proceso, error = validar_registro_proceso(linea, ids_vistos)
        if error:
            print(f"  [ERROR] {error}. Intente nuevamente.")
            continue
        procesos.append(proceso)

    if len(procesos) == 10:
        print("  Se alcanzó el máximo de 10 procesos.")
    procesos.sort(key=lambda proceso: proceso.arribo)
    return procesos


def guardar_procesos(procesos):
    carpeta = carpeta_base() / "ejemplos"
    try:
        carpeta.mkdir(exist_ok=True)
        numero = 0
        while True:
            nombre = "procesos.txt" if numero == 0 else f"procesos_{numero}.txt"
            ruta = carpeta / nombre
            try:
                with open(ruta, "x", encoding="utf-8", newline="\n") as archivo:
                    archivo.write(
                        "# PID, tamaño_KB, tiempo_arribo, irrupcion_CPU\n"
                    )
                    for proceso in procesos:
                        archivo.write(
                            f"{proceso.pid},{proceso.tamano},"
                            f"{proceso.arribo},{proceso.irrupcion}\n"
                        )
                print(f"  Archivo guardado en: {ruta}")
                return ruta
            except FileExistsError:
                numero += 1
    except OSError as error:
        print(f"  [ERROR] No se pudo guardar el archivo: {error}")
        return None


def cargar_simulador(ruta=None, procesos=None):
    try:
        simulador = Simulador(ruta)
    except (OSError, UnicodeError) as error:
        print(f"  [ERROR] No se pudo leer el archivo: {error}")
        return None

    if procesos is not None:
        simulador.procesos = procesos
    if not simulador.procesos:
        print("  [ERROR] No se encontraron procesos válidos.")
        return None
    return simulador


def cargar_archivo_nuevo():
    while True:
        print("\n  CARGA DE ARCHIVO NUEVO")
        print("  [1] Ingresar procesos manualmente")
        print("  [2] Indicar la ruta de un archivo .txt")
        print("  [0] Volver al menú anterior")
        opcion = input("\n  Seleccione una opción: ").strip()

        if opcion == "0":
            return None
        if opcion == "1":
            procesos = cargar_procesos_manualmente()
            if procesos is None:
                return None
            simulador = cargar_simulador(procesos=procesos)
        elif opcion == "2":
            ruta = solicitar_ruta_txt()
            if ruta is None:
                return None
            simulador = cargar_simulador(ruta=ruta)
        else:
            print("  Opción inválida.")
            continue

        if simulador is None:
            continue
        guardar = input("  ¿Desea guardar los procesos en ejemplos/? [s/N]: ")
        if guardar.strip().lower() in ("s", "si", "sí"):
            guardar_procesos(simulador.procesos)
        return simulador


def comenzar_simulacion():
    while True:
        print("\n  COMENZAR")
        print("  [1] Utilizar archivos guardados")
        print("  [2] Cargar un archivo nuevo")
        print("  [0] Volver al menú principal")
        opcion = input("\n  Seleccione una opción: ").strip()

        if opcion == "0":
            return
        if opcion == "1":
            ruta = elegir_archivo_procesos()
            if ruta is None:
                continue
            simulador = cargar_simulador(ruta=ruta)
        elif opcion == "2":
            simulador = cargar_archivo_nuevo()
        else:
            print("  Opción inválida.")
            continue

        if simulador is None:
            continue
        if simulador.iniciar_simulacion():
            input(
                "\n  [Enter] Salir de la simulación y volver al menú principal..."
            )
        return


def mostrar_indicaciones():
    lineas = [
        "INDICACIONES / FUNCIONAMIENTO",
        "",
        "EJECUCIÓN Y MENÚS",
        "• Ejecute el programa con: python simulador.py",
        "• En el menú principal, consulte estas indicaciones, comience o salga.",
        "• En Comenzar, elija archivos guardados o cargue un archivo nuevo.",
        "• La carga nueva acepta procesos manuales o la ruta de un archivo .txt.",
        "• Use 0 para volver al menú anterior; las opciones inválidas se repiten.",
        "• Al terminar, pulse Enter para volver al menú principal.",
        "",
        "CARGA DE PROCESOS",
        "• Formato: ID, tamaño_KB, tiempo_arribo, irrupcion_CPU",
        "• Ejemplo: P1,80,0,5. Se ignoran líneas vacías y comentarios con #.",
        "• El ID no se repite; tamaño: 1-450 KB; arribo: >= 0; CPU: >= 1.",
        "• Se conservan los primeros 10 registros válidos y luego se ordenan",
        "  por arribo; los empates conservan el orden del archivo.",
        "• En carga manual, escriba 'fin' para terminar o 'cancelar' para volver.",
        "• Puede escribir rutas con espacios, con o sin comillas.",
        "• Si guarda, se usa ejemplos/ y nunca se reemplaza un archivo existente.",
        "",
        "MEMORIA MVT Y BEST-FIT",
        "• El SO ocupa 100 KB; los procesos usan una memoria dinámica de 450 KB.",
        "• Best-Fit asigna el hueco libre más pequeño que alcance para el proceso.",
        "• La asignación es contigua: huecos separados no se suman.",
        "• Si no hay un bloque suficiente, el proceso pasa a LISTOS/SUSPENDIDOS.",
        "• Al liberar memoria, los huecos libres adyacentes se fusionan.",
        "• SWAP-IN reubica suspendidos cuando existe un hueco contiguo disponible.",
        "",
        "PLANIFICACIÓN Y MULTIPROGRAMACIÓN",
        "• SRTF ejecuta el proceso con menor tiempo de CPU restante.",
        "• Un proceso más corto puede desalojar al que ocupa la CPU.",
        "• En empate, se prioriza el menor tiempo de arribo.",
        "• Cada ciclo ejecuta una unidad de tiempo; T avanza una sola vez.",
        "• El máximo activo es 5: CPU, LISTOS y LISTOS/SUSPENDIDOS.",
        "• NUEVOS no cuentan hasta ser admitidos.",
        "",
        "DASHBOARD E HISTORIAL",
        "• Encabezado: tiempo actual, multiprogramación y estado de la CPU.",
        "• Mapa: particiones de usuario, direcciones, tamaño y estado.",
        "• Colas: NUEVOS, LISTOS, LISTOS/SUSPENDIDOS y TERMINADOS.",
        "• LISTOS se ordena solo para mostrar: restante y luego arribo.",
        "• El historial acumula los eventos del ciclo y sus fases.",
        "• [LLEGADA]/[ADMISIÓN]: ingreso y asignación de memoria.",
        "• [SUSPENSIÓN]/[SWAP-IN]: espera por memoria y reingreso a RAM.",
        "• [LÍMITE MP]: se alcanzó el máximo de procesos activos.",
        "• [CPU / SRTF]: selección o continuidad; [CPU IDLE]: procesador inactivo.",
        "• [DESALOJO]: cambio de CPU por SRTF; [EJECUCIÓN]: 1 unidad de CPU.",
        "• [FIN PROCESO]: liberación de memoria y paso a TERMINADOS.",
        "• Las fases muestran NUEVO, admisión, CPU incluso con restante 0, y fin.",
        "",
        "MÉTRICAS",
        "• Retorno (TAT): finalización menos tiempo de arribo.",
        "• Espera (WT): retorno menos duración total de CPU.",
        "• Los promedios resumen TAT y WT de todos los procesos terminados.",
        "• Tiempo total: duración de la simulación desde T=0 hasta el último fin.",
        "• Rendimiento: procesos terminados dividido tiempo total simulado.",
    ]
    print("\n" + "═" * Simulador.ANCHO_UI)
    for linea in lineas:
        print(linea)
    print("═" * Simulador.ANCHO_UI)


def menu_principal():
    while True:
        print("\n" + "═" * Simulador.ANCHO_UI)
        print("  SIMULADOR MVT + BEST-FIT + SRTF")
        print("  [1] Indicaciones / Funcionamiento")
        print("  [2] Comenzar")
        print("  [3] Salir del programa")
        opcion = input("\n  Seleccione una opción: ").strip()

        if opcion == "1":
            mostrar_indicaciones()
        elif opcion == "2":
            comenzar_simulacion()
        elif opcion == "3":
            print("  Hasta luego.")
            return
        else:
            print("  Opción inválida.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    menu_principal()