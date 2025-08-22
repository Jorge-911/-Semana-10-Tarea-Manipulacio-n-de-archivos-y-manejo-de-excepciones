"""
Sistema de Gestión de Inventarios (archivo único, comentarios detallados)

Extensión: Persistencia en archivo de texto + manejo robusto de excepciones.

Formato del archivo: CSV UTF-8 con encabezado (id,nombre,cantidad,precio)
- Se crea automáticamente si no existe.
- Las operaciones que modifican el inventario (agregar/actualizar/eliminar)
  intentan guardar de inmediato y reportan al usuario si se guardó o no.
- Durante la carga se ignoran líneas corruptas y se informa cuántas hubo.

NOTA: Seguimos cumpliendo el requisito de usar LISTA como estructura principal
      en la clase Inventario. El archivo es solo un medio de persistencia.
"""

from __future__ import annotations
from typing import List, Optional, Tuple
import csv
import os


class Producto:
    """
    Representa un producto del inventario.

    Atributos:
      - id (str): identificador único NO vacío.
      - nombre (str): nombre NO vacío.
      - cantidad (int): unidades en stock, entero ≥ 0.
      - precio (float): precio unitario, número ≥ 0.

    Por qué getters/setters:
      - El enunciado lo requiere. Además, permiten validar y normalizar cuando se actualiza.
    """

    def __init__(self, id_: str, nombre: str, cantidad: int, precio: float):
        # Guardamos “protegido” con _ prefijo para forzar el uso de getters/setters si hiciera falta.
        self._id = str(id_).strip()
        self._nombre = str(nombre).strip()

        # Convertimos y validamos cantidad como entero no negativo
        try:
            self._cantidad = int(cantidad)
        except (TypeError, ValueError):
            raise ValueError("La cantidad debe ser un entero.")
        if self._cantidad < 0:
            raise ValueError("La cantidad no puede ser negativa.")

        # Precio: aceptamos coma decimal por comodidad de entrada
        try:
            self._precio = float(str(precio).replace(",", "."))
        except (TypeError, ValueError):
            raise ValueError("El precio debe ser un número.")
        if self._precio < 0:
            raise ValueError("El precio no puede ser negativo.")

        # Validaciones de campos de texto
        if not self._id:
            raise ValueError("El ID no puede estar vacío.")
        if not self._nombre:
            raise ValueError("El nombre no puede estar vacío.")

    # --- Getters (cumplen requisito) ---
    def get_id(self) -> str:
        return self._id

    def get_nombre(self) -> str:
        return self._nombre

    def get_cantidad(self) -> int:
        return self._cantidad

    def get_precio(self) -> float:
        return self._precio

    # --- Setters con validaciones (cumplen requisito) ---
    def set_nombre(self, nuevo_nombre: str) -> None:
        nuevo_nombre = str(nuevo_nombre).strip()
        if not nuevo_nombre:
            raise ValueError("El nombre no puede estar vacío.")
        self._nombre = nuevo_nombre

    def set_cantidad(self, nueva_cantidad: int) -> None:
        try:
            nueva_cantidad = int(nueva_cantidad)
        except (TypeError, ValueError):
            raise ValueError("La cantidad debe ser un entero.")
        if nueva_cantidad < 0:
            raise ValueError("La cantidad no puede ser negativa.")
        self._cantidad = nueva_cantidad

    def set_precio(self, nuevo_precio: float) -> None:
        try:
            nuevo_precio = float(str(nuevo_precio).replace(",", "."))
        except (TypeError, ValueError):
            raise ValueError("El precio debe ser un número.")
        if nuevo_precio < 0:
            raise ValueError("El precio no puede ser negativo.")
        self._precio = nuevo_precio

    def __str__(self) -> str:
        return f"ID: {self._id} | Nombre: {self._nombre} | Cant.: {self._cantidad} | Precio: ${self._precio:,.2f}"

    # --- Serialización a/desde CSV (para persistencia en texto) ---
    def to_csv_row(self) -> List[str]:
        """Devuelve la fila CSV en orden [id, nombre, cantidad, precio]."""
        return [self._id, self._nombre, str(self._cantidad), f"{self._precio:.2f}"]

    @staticmethod
    def from_csv_row(row: List[str]) -> "Producto":
        """
        Crea un Producto desde una fila CSV [id, nombre, cantidad, precio].
        Lanza ValueError si la fila es inválida.
        """
        if len(row) != 4:
            raise ValueError("Fila CSV inválida (número de columnas distinto de 4).")
        id_, nombre, cantidad, precio = row
        return Producto(id_, nombre, int(cantidad), float(precio))


class Inventario:
    """
    Gestiona una colección de productos usando una LISTA (requisito) y
    persiste los cambios en un archivo CSV.

    Métodos de modificación (agregar/eliminar/actualizar) guardan al archivo
    inmediatamente y retornan una tupla (ok: bool, msg: str) para que la UI
    informe el resultado tanto lógico como de persistencia.
    """

    ENCABEZADO = ["id", "nombre", "cantidad", "precio"]

    def __init__(self, ruta_archivo: str = "inventario.txt"):
        self.productos: List[Producto] = []
        self.ruta_archivo = ruta_archivo
        creado, msg = self._asegurar_archivo()
        cargados, corruptas, msg_carga = self._cargar_desde_archivo()
        # Mensajes informativos para la UI (se exponen vía propiedades)
        self.info_inicio = {
            "archivo_creado": creado,
            "mensaje_archivo": msg,
            "cargados": cargados,
            "corruptas": corruptas,
            "mensaje_carga": msg_carga,
        }

    # -------- API pública requerida --------
    def agregar_producto(self, producto: Producto) -> Tuple[bool, str]:
        if self._existe_id(producto.get_id()):
            return False, f"Ya existe un producto con ID '{producto.get_id()}'."
        self.productos.append(producto)
        ok, msg = self._guardar_a_archivo()
        return ok, msg if ok else f"Agregado en memoria, pero no se pudo guardar: {msg}"

    def eliminar_por_id(self, id_producto: str) -> Tuple[bool, str]:
        id_producto = str(id_producto).strip()
        for i, p in enumerate(self.productos):
            if p.get_id() == id_producto:
                del self.productos[i]
                ok, msg = self._guardar_a_archivo()
                return (ok, msg) if ok else (True, f"Eliminado en memoria, pero no se pudo guardar: {msg}")
        return False, "No se encontró un producto con ese ID."

    def actualizar(
        self,
        id_producto: str,
        cantidad: Optional[int] = None,
        precio: Optional[float] = None,
    ) -> Tuple[bool, str]:
        prod = self._buscar_por_id(id_producto)
        if not prod:
            return False, "No se encontró un producto con ese ID."
        try:
            if cantidad is not None:
                prod.set_cantidad(cantidad)
            if precio is not None:
                prod.set_precio(precio)
        except Exception as e:
            return False, f"Validación fallida: {e}"
        ok, msg = self._guardar_a_archivo()
        return (ok, msg) if ok else (True, f"Actualizado en memoria, pero no se pudo guardar: {msg}")

    def buscar_por_nombre(self, termino: str) -> List[Producto]:
        termino = str(termino).strip().lower()
        if not termino:
            return []
        return [p for p in self.productos if termino in p.get_nombre().lower()]

    def mostrar_todos(self) -> List[Producto]:
        return list(self.productos)

    # -------- Persistencia y utilitarios internos --------
    def _asegurar_archivo(self) -> Tuple[bool, str]:
        """
        Garantiza que el archivo exista y tenga encabezado. Si no existe, lo crea.
        Devuelve (creado, mensaje).
        """
        try:
            if not os.path.exists(self.ruta_archivo):
                with open(self.ruta_archivo, mode="w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.ENCABEZADO)
                return True, f"Archivo '{self.ruta_archivo}' creado."
            # Si existe pero está vacío, escribimos encabezado
            if os.path.getsize(self.ruta_archivo) == 0:
                with open(self.ruta_archivo, mode="w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.ENCABEZADO)
                return True, f"Archivo '{self.ruta_archivo}' estaba vacío. Se escribió el encabezado."
            return False, f"Archivo '{self.ruta_archivo}' listo."
        except PermissionError:
            return False, f"Permiso denegado para crear/escribir '{self.ruta_archivo}'."
        except OSError as e:
            return False, f"Error de E/S al preparar el archivo: {e}"

    def _cargar_desde_archivo(self) -> Tuple[int, int, str]:
        """
        Carga el inventario desde el archivo. Ignora líneas corruptas pero las cuenta.
        Devuelve (cargados_ok, lineas_corruptas, mensaje).
        """
        cargados = 0
        corruptas = 0
        if not os.path.exists(self.ruta_archivo):
            return 0, 0, "Archivo no encontrado; se creará al guardar por primera vez."
        try:
            with open(self.ruta_archivo, mode="r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                # Validamos encabezado si existe
                first = next(reader, None)
                if first is None:
                    return 0, 0, "Archivo vacío; no hay datos que cargar."
                header = [h.strip().lower() for h in first]
                if header != self.ENCABEZADO:
                    # Si no hay encabezado válido, consideramos la primera fila como dato e intentamos parsearla
                    try:
                        prod = Producto.from_csv_row(first)
                        self.productos.append(prod)
                        cargados += 1
                    except Exception:
                        corruptas += 1
                for row in reader:
                    try:
                        prod = Producto.from_csv_row(row)
                        # Evitamos duplicados por ID durante la carga
                        if not self._existe_id(prod.get_id()):
                            self.productos.append(prod)
                            cargados += 1
                    except Exception:
                        corruptas += 1
            msg = f"Cargados: {cargados}. Líneas corruptas: {corruptas}."
            return cargados, corruptas, msg
        except FileNotFoundError:
            return 0, 0, "Archivo no encontrado; se creará al guardar por primera vez."
        except PermissionError:
            return 0, 0, f"Permiso denegado para leer '{self.ruta_archivo}'."
        except OSError as e:
            return 0, 0, f"Error de E/S al leer: {e}"

    def _guardar_a_archivo(self) -> Tuple[bool, str]:
        """
        Escribe TODO el inventario actual al archivo (sobrescritura segura).
        Devuelve (ok, mensaje). Si falla, la lista en memoria se mantiene.
        """
        try:
            with open(self.ruta_archivo, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.ENCABEZADO)
                for p in self.productos:
                    writer.writerow(p.to_csv_row())
            return True, f"Inventario guardado en '{self.ruta_archivo}'."
        except PermissionError:
            return False, f"Permiso denegado para escribir en '{self.ruta_archivo}'."
        except OSError as e:
            return False, f"Error de E/S al guardar: {e}"

    def _existe_id(self, id_producto: str) -> bool:
        return any(p.get_id() == id_producto for p in self.productos)

    def _buscar_por_id(self, id_producto: str) -> Optional[Producto]:
        id_producto = str(id_producto).strip()
        for p in self.productos:
            if p.get_id() == id_producto:
                return p
        return None


# ============================
# Interfaz de Usuario (Consola)
# ============================

def _mostrar_menu():
    print(
        """
========== MENÚ INVENTARIO ==========
1) Añadir producto
2) Eliminar producto por ID
3) Actualizar cantidad o precio por ID
4) Buscar producto(s) por nombre
5) Mostrar todos los productos
6) Salir
=====================================
"""
    )


def _pedir_float(msg: str) -> float:
    while True:
        try:
            return float(input(msg).replace(",", "."))
        except ValueError:
            print("Entrada inválida. Intente de nuevo.")


def _pedir_int(msg: str) -> int:
    while True:
        try:
            return int(input(msg))
        except ValueError:
            print("Entrada inválida. Intente de nuevo.")


def main():
    """
    Bucle principal del programa (CLI) con persistencia:
      - Crea un Inventario que carga desde archivo (si existe) y reporta estado de carga.
      - Tras cada operación que modifica datos, intenta guardar al archivo y notifica resultado.
    """
    inventario = Inventario()

    # Mensajes de arranque relacionados con archivo
    info = inventario.info_inicio
    print(f"[INFO] {info['mensaje_archivo']}")
    print(f"[INFO] {info['mensaje_carga']}")

    # Datos de ejemplo (descomentar si se quiere iniciar con algo en el primer uso):
    # if not inventario.mostrar_todos():
    #     ok, msg = inventario.agregar_producto(Producto("A001", "Agua 600ml", 20, 0.6))
    #     print(f"[ARRANQUE] {msg}")

    while True:
        _mostrar_menu()
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            # --- Añadir producto ---
            print("-- Añadir nuevo producto --")
            idp = input("ID: ").strip()
            nombre = input("Nombre: ").strip()
            cantidad = _pedir_int("Cantidad: ")
            precio = _pedir_float("Precio (USD): ")
            try:
                prod = Producto(idp, nombre, cantidad, precio)
                ok, msg = inventario.agregar_producto(prod)
                estado = "OK" if ok else "FALLO"
                print(f"[{estado}] {msg}\n")
            except Exception as e:
                print(f"[FALLO] Error: {e}\n")

        elif opcion == "2":
            # --- Eliminar por ID ---
            print("-- Eliminar producto --")
            idp = input("ID del producto a eliminar: ").strip()
            ok, msg = inventario.eliminar_por_id(idp)
            estado = "OK" if ok else "FALLO"
            print(f"[{estado}] {msg}\n")

        elif opcion == "3":
            # --- Actualizar (cantidad y/o precio) ---
            print("-- Actualizar producto --")
            idp = input("ID del producto a actualizar: ").strip()
            print("Deje vacío si NO desea cambiar ese campo.")
            cant_str = input("Nueva cantidad: ").strip()
            prec_str = input("Nuevo precio (USD): ").strip()

            try:
                cantidad = None
                precio = None
                if cant_str != "":
                    cantidad = int(cant_str)
                if prec_str != "":
                    precio = float(prec_str.replace(",", "."))
                ok, msg = inventario.actualizar(idp, cantidad=cantidad, precio=precio)
                estado = "OK" if ok else "FALLO"
                print(f"[{estado}] {msg}\n")
            except ValueError as e:
                print(f"[FALLO] Error: {e}\n")
            except Exception as e:
                print(f"[FALLO] Error inesperado: {e}\n")

        elif opcion == "4":
            # --- Buscar por nombre ---
            print("-- Buscar productos --")
            termino = input("Buscar por nombre: ").strip()
            resultados = inventario.buscar_por_nombre(termino)
            if resultados:
                print("Resultados:")
                for p in resultados:
                    print("  ", p)
            else:
                print("No se encontraron productos que coincidan.")
            print()

        elif opcion == "5":
            # --- Listar todos ---
            print("-- Inventario actual --")
            productos = inventario.mostrar_todos()
            if not productos:
                print("(vacío)\n")
            else:
                for p in productos:
                    print("  ", p)
                print()

        elif opcion == "6":
            print("Saliendo... ¡Hasta luego!")
            break

        else:
            print("Opción inválida. Intente nuevamente.\n")


# Punto de entrada del script
if __name__ == "__main__":
    main()

"""
Ideas de pruebas manuales (rápidas):
1) Ejecutar por primera vez: debe crear 'inventario.txt' con encabezado y mostrar [INFO].
2) Añadir un producto y verificar que se guarda (abrir el archivo y ver la fila escrita).
3) Cerrar y volver a abrir el programa: debe cargar el/los productos previamente guardados.
4) Ingresar cantidad/precio inválidos: la UI debe mostrar [FALLO] con mensaje claro.
5) Editar el archivo a mano y corromper una línea (p. ej., borrar una columna):
   - El programa debe ignorar esa línea y reportar 'Líneas corruptas: N'.
6) Simular permiso denegado (en Unix: 'chmod -w inventario.txt') y luego intentar agregar:
   - La operación debe indicar 'Actualizado/Agregado en memoria, pero no se pudo guardar: Permiso denegado...'.
7) Duplicar ID: al intentar agregar, debe avisar que el ID ya existe.
"""
