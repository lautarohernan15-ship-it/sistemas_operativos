ANCHO_UI = 84


def _imprimir_cola_grilla(titulo, items, info_costado=None):
    ancho_lbl = 22
    top_lbl = f"  ╔{'═' * ancho_lbl}╗"
    mid_lbl = f"  ║{titulo:^{ancho_lbl}}║"
    bot_lbl = f"  ╚{'═' * ancho_lbl}╝"

    bloque_cpu = ["", "", ""]
    if info_costado:
        ancho_cpu = len(info_costado) + 4
        bloque_cpu = [
            f"   ╔{'═' * ancho_cpu}╗",
            f"   ║  {info_costado}  ║",
            f"   ╚{'═' * ancho_cpu}╝",
        ]

    if not items:
        str_vacia = " ──> [ Vacía ]"
        relleno = " " * max(1, 24 - len(str_vacia))
        print(f"{top_lbl}{' ' * 24}{bloque_cpu[0]}")
        print(f"{mid_lbl}{str_vacia}{relleno}{bloque_cpu[1]}")
        print(f"{bot_lbl}{' ' * 24}{bloque_cpu[2]}")
        return

    max_por_fila = 3 if info_costado else 4
    filas = [items[i:i + max_por_fila] for i in range(0, len(items), max_por_fila)]

    for idx_fila, fila in enumerate(filas):
        anchos = [len(texto) + 2 for texto in fila]
        top_boxes = " ".join(f"┌{'─' * a}┐" for a in anchos)
        bot_boxes = " ".join(f"└{'─' * a}┘" for a in anchos)

        celdas_medio = []
        for j, (texto, a) in enumerate(zip(fila, anchos)):
            borde_izq = "┤" if j == 0 else "│"
            celdas_medio.append(f"{borde_izq}{texto:^{a}}│")
        mid_boxes = " ".join(celdas_medio)

        if idx_fila == 0:
            print(f"{top_lbl}   {top_boxes}{bloque_cpu[0]}")
            print(f"{mid_lbl} ──{mid_boxes}{bloque_cpu[1]}")
            print(f"{bot_lbl}   {bot_boxes}{bloque_cpu[2]}")
        else:
            sangria = " " * (ancho_lbl + 4)
            print(f"{sangria}   {top_boxes}")
            print(f"{sangria} ↳─{mid_boxes}")
            print(f"{sangria}   {bot_boxes}")


def renderizar_dashboard(sim, fase=""):
    w = ANCHO_UI
    mp = sim.grado_multiprogramacion_activo()

    print("\n" + "═" * w)
    titulo = "SIMULADOR DE MEMORIA (MVT) Y PLANIFICACIÓN (SRTF)"
    print(f"{titulo:^{w}}")
    print("═" * w)

    info_tiempo = f"TIEMPO ACTUAL : T = {sim.tiempo_actual}"
    info_mp = f"MULTIPROGRAMACIÓN : {mp} / 5 procesos activos"
    print(f"  {info_tiempo:<38} {info_mp}")
    print("─" * w)

    c1, c2, c3, c4, c5, c6 = 6, 13, 13, 13, 16, 12
    print("\n  > MAPA DE PARTICIONES DE MEMORIA (MVT - Best Fit | SO: 100 KB + Usuario: 450 KB)")
    print(f"  ┌{'─'*c1}┬{'─'*c2}┬{'─'*c3}┬{'─'*c4}┬{'─'*c5}┬{'─'*c6}┐")
    print(f"  │{'ID':^{c1}}│{'Dir. Inicio':^{c2}}│{'Dir. Final':^{c3}}│{'Tamaño (KB)':^{c4}}│{'Estado / PID':^{c5}}│{'Frag. Int.':^{c6}}│")
    print(f"  ├{'─'*c1}┼{'─'*c2}┼{'─'*c3}┼{'─'*c4}┼{'─'*c5}┼{'─'*c6}┤")

    print(f"  │{'SO':^{c1}}│{0:^{c2}}│{sim.memoria_so - 1:^{c3}}│{sim.memoria_so:^{c4}}│{'SISTEMA OP.':^{c5}}│{'0 KB':^{c6}}│")

    for indice, part in enumerate(sim.particiones, start=1):
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

    print("\n  > ESTADO DE LAS COLAS Y CPU")
    if sim.proceso_ejecucion:
        p = sim.proceso_ejecucion
        texto_cpu = f"CPU: {p.pid} ({p.tamano}KB | Rest: {p.restante}/{p.irrupcion})"
    else:
        texto_cpu = "CPU: [ Inactivo / Idle ]"

    nodos_nuevos = [f"{p.pid} ({p.tamano}KB)" for p in sim.cola_nuevo]
    listos_ordenados = sorted(sim.cola_listo, key=lambda p: (p.restante, p.arribo))
    nodos_listos = [f"{p.pid} (Rest:{p.restante})" for p in listos_ordenados]
    nodos_susp = [f"{p.pid} ({p.tamano}KB)" for p in sim.cola_listo_suspendido]
    nodos_term = [f"{p.pid}" for p in sim.cola_terminado]

    _imprimir_cola_grilla("Cola de NUEVOS", nodos_nuevos, info_costado=texto_cpu)
    _imprimir_cola_grilla("Cola de LISTOS", nodos_listos)
    _imprimir_cola_grilla("LISTOS / SUSPENDIDOS", nodos_susp)
    _imprimir_cola_grilla("Cola de TERMINADOS", nodos_term)

    print(f"\n  > HISTORIAL DE MOVIMIENTOS DEL CICLO (T = {sim.tiempo_actual}) {fase}")
    total_ev = len(sim.eventos_ciclo)
    for idx, (tag, msg) in enumerate(sim.eventos_ciclo):
        conector = "└─" if idx == total_ev - 1 else "├─"
        tag_fmt = f"[{tag}]"
        print(f"   {conector} {tag_fmt:<14} {msg}")

    print("─" * w)


def mostrar_informe_estadistico(sim):
    w = ANCHO_UI
    c1, c2, c3, c4, c5 = 12, 16, 16, 16, 14

    print("\n" + "═" * w)
    print(f"{'INFORME ESTADÍSTICO FINAL DE LA SIMULACIÓN':^{w}}")
    print("═" * w)

    print(f"\n  ┌{'─'*c1}┬{'─'*c2}┬{'─'*c3}┬{'─'*c4}┬{'─'*c5}┐")
    print(f"  │{'Proceso':^{c1}}│{'T. Arribo':^{c2}}│{'T. Irrupción':^{c3}}│{'T. Retorno':^{c4}}│{'T. Espera':^{c5}}│")
    print(f"  ├{'─'*c1}┼{'─'*c2}┼{'─'*c3}┼{'─'*c4}┼{'─'*c5}┤")

    t_retorno_total = 0
    t_espera_total = 0

    for p in sim.cola_terminado:
        print(
            f"  │{p.pid:^{c1}}│{p.arribo:^{c2}}│{p.irrupcion:^{c3}}│"
            f"{p.retorno:^{c4}}│{p.espera:^{c5}}│"
        )
        t_retorno_total += p.retorno
        t_espera_total += p.espera

    print(f"  └{'─'*c1}┴{'─'*c2}┴{'─'*c3}┴{'─'*c4}┴{'─'*c5}┘")

    n = len(sim.procesos)
    prom_retorno = t_retorno_total / n
    prom_espera = t_espera_total / n
    rendimiento = n / sim.tiempo_actual

    print("\n  > MÉTRICAS GLOBALES DEL SISTEMA")
    print(f"   ├─ Tiempo Total Simulado             : {sim.tiempo_actual} unidades de tiempo")
    print(f"   ├─ Tiempo Promedio de Retorno (TAT)  : {prom_retorno:.2f} unidades de tiempo")
    print(f"   ├─ Tiempo Promedio de Espera (WT)    : {prom_espera:.2f} unidades de tiempo")
    print(f"   └─ Rendimiento (Throughput)          : {rendimiento:.4f} procesos / unidad de tiempo")
    print("═" * w + "\n")
