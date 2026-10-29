Historial de Cambios 2026-10-29

### Añadido 

* **Partición del Sistema Operativo visible:** Se agregó una fila en la tabla de particiones para representar visualmente el espacio reservado para el Sistema Operativo (Direcciones 0 a 99, Tamaño 100 KB), Como pide la guia.
* **Columnas de Dirección Final y Fragmentación Interna:** La tabla de memoria ahora muestra dónde termina cada partición y la fragmentación interna, La guia lo pedia.
* **Menú de Modos de Simulación:** Permite elegir entre correr el simulador ciclo a ciclo o detenerse únicamente ante llegadas o finalizaciones de procesos (criterio estricto de la guía).
* **Buffer de Eventos (`eventos_ciclo`):** Se implementó un sistema de registro de eventos que almacena los movimientos de cada ciclo (`[LLEGADA]`, `[ADMISIÓN]`, `[SRTF]`) en lugar de imprimirlos en tiempo real, permitiendo renderizarlos todos juntos y ordenados al final del dashboard.
* **Control de Límite de Procesos:** Se añadió una validación al cargar `procesos.txt` para advertir si excede los 10 procesos, respetando el tope máximo de la consigna.

### Modificado
* **Interfaz Gráfica en Consola (Dashboard):** Se eliminaron los `print()` sueltos y desordenados para reemplazarlos por una interfaz centralizada, limpia y elegante utilizando caracteres de bordes Unicode de línea simple y doble.
* **Visualización de Colas:** Se reemplazó la impresión cruda de listas de Python (ej. `['P1', 'P6']`) por una vista de "Grilla de Nodos". Ahora cada proceso se dibuja en su propia celda (ej. `┌────────────┐`) e incluye información contextual vital para el seguimiento:
  * Cola de NUEVOS y SUSPENDIDOS: Muestra el tamaño en KB del proceso.
  * Cola de LISTOS: Muestra el tiempo restante de ráfaga de CPU para validar visualmente las decisiones del SRTF.
* **Estado de CPU:** El estado del procesador pasó de ocupar un gran bloque solitario a ser una línea condensada e informativa (`ESTADO CPU : En ejecución -> P1 (...)`), lo que ahorra espacio vertical y reduce la fatiga visual.
* **Formato del Informe Final:** Se transformó el informe estadístico en una tabla prolija y autocentrada, mejorando enormemente la legibilidad del Tiempo de Retorno (TAT), Tiempo de Espera (WT) y Throughput.

### Solucionado 
* **Lógica de Swap-In (Reingreso de Suspendidos):** Se eliminó la restricción `self.grado_multiprogramacion_activo() < 5` en el bucle que evalúa a los procesos `Listo/Suspendido`. Como estos procesos *ya forman parte* de los 5 procesos admitidos por el sistema, validar el límite nuevamente impedía que recuperaran memoria y pasaran a `Listo` en ciertos escenarios de congestión.
* **Cálculo de Direcciones:** Se resolvió la ambigüedad en los límites de particiones mediante la propiedad `fin` (inicio + tamaño - 1), evitando superposiciones conceptuales entre el fin de un bloque y el inicio del siguiente (ej. 0-99 y 100-149, en lugar de 0-100 y 100-150).