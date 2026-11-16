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
