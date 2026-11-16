import os
import sys
from pathlib import Path
from modelos import validar_registro_proceso
from interfaz import ANCHO_UI
from simulador import Simulador


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
                 if archivo.stem.lower().startswith("ejemplo") or archivo.stem.lower().startswith("lote")),
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
        ruta_ingresada = input("  Ruta del archivo .txt (o 0 para volver): ").strip()
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
            nombre = "procesos.txt" if numero == 0 else f"ejemplo_{numero}.txt"
            ruta = carpeta / nombre
            try:
                with open(ruta, "x", encoding="utf-8", newline="\n") as archivo:
                    archivo.write("# PID, tamaño_KB, tiempo_arribo, irrupcion_CPU\n")
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


def iniciar_proceso_simulacion():
    while True:
        print("\n  SELECCIÓN DE ORIGEN DE PROCESOS")
        print("  [1] Utilizar archivos guardados")
        print("  [2] Cargar un archivo nuevo (manual o .txt)")
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
            input("\n  [Enter] Salir de la simulación y volver al menú principal...")
        return


def mostrar_indicaciones():
    lineas = [
        "INDICACIONES / FUNCIONAMIENTO",
        "",
        "CONTROLES DURANTE LA SIMULACIÓN",
        "• [Enter] : Avanza a la siguiente unidad de tiempo (+1 u.t.).",
        "• [E]     : Salta hasta el próximo evento (llegada o finalización).",
        "• [C]     : Completa la corrida y muestra el resultado final.",
        "• [PID]   : Escriba el ID de un proceso (ej. P1) para saltar hasta su turno.",
        "",
        "MEMORIA MVT Y PLANIFICACIÓN SRTF",
        "• Memoria: 100 KB para SO y 450 KB para Usuario con política Best-Fit.",
        "• Multiprogramación máxima de 5 procesos activos.",
        "• Planificación apropiativa SRTF por menor tiempo restante.",
    ]
    print("\n" + "═" * ANCHO_UI)
    for linea in lineas:
        print("  " + linea)
    print("═" * ANCHO_UI)


def menu_principal():
    while True:
        print("\n" + "═" * ANCHO_UI)
        print("  SIMULADOR MVT + BEST-FIT + SRTF (GRUPO 14)")
        print("  [1] Utilizar archivos guardados")
        print("  [2] Cargar un archivo nuevo")
        print("  [3] Indicaciones / Funcionamiento")
        print("  [0] Salir del programa")
        opcion = input("\n  Seleccione una opción: ").strip()

        if opcion == "1":
            ruta = elegir_archivo_procesos()
            if ruta is not None:
                simulador = cargar_simulador(ruta=ruta)
                if simulador is not None:
                    if simulador.iniciar_simulacion():
                        input("\n  [Enter] Salir de la simulación y volver al menú principal...")
        elif opcion == "2":
            simulador = cargar_archivo_nuevo()
            if simulador is not None:
                if simulador.iniciar_simulacion():
                    input("\n  [Enter] Salir de la simulación y volver al menú principal...")
        elif opcion == "3":
            mostrar_indicaciones()
        elif opcion == "0":
            print("  Hasta luego.")
            return
        else:
            print("  Opción inválida.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    menu_principal()
