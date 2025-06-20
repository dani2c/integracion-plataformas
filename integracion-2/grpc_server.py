import sys
import os
from concurrent import futures
import grpc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- INICIO DE LA CORRECCIÓN DEFINITIVA ---
# Añadir el directorio raíz del proyecto al 'path' de Python.
# Esto es necesario para que se pueda hacer 'from models import Producto'.
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.append(PROJECT_ROOT)

# Añadir también el directorio 'grpc_files' al 'path'.
# Esto es crucial para que el 'import producto_pb2' que está dentro del
# archivo 'producto_pb2_grpc.py' generado automáticamente pueda encontrarlo.
GRPC_FILES_PATH = os.path.join(PROJECT_ROOT, 'grpc_files')
sys.path.append(GRPC_FILES_PATH)
# --- FIN DE LA CORRECCIÓN DEFINITIVA ---


# Ahora las importaciones de los archivos generados funcionarán correctamente
from grpc_files import producto_pb2
from grpc_files import producto_pb2_grpc

# Importar solo el modelo, no la instancia 'db' de Flask.
from models import Producto

# --- CONFIGURACIÓN DE LA BASE DE DATOS PARA EL SERVIDOR GRPC ---
# Este servidor es independiente de Flask, por lo que necesita su propia conexión.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'inventario_db.db')
engine = create_engine(f'sqlite:///{DATABASE_PATH}')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Esta es la clase que implementa la lógica del servidor.
class ProductoService(producto_pb2_grpc.ProductoServiceServicer):
    # Esta función se llama cuando el cliente invoca "IngresarProducto".
    def IngresarProducto(self, request, context):
        print("Servidor gRPC: Recibida petición para ingresar producto...")
        db_session = SessionLocal()
        try:
            # Validaciones de negocio
            if not request.nombre or request.precio <= 0:
                mensaje = "Error: Nombre y precio válido son requeridos."
                print(f"Servidor gRPC: {mensaje}")
                return producto_pb2.ProductoResponse(exito=False, mensaje=mensaje)

            # Crear el objeto del modelo con los datos recibidos
            nuevo_producto = Producto(
                nombre=request.nombre,
                descripcion=request.descripcion,
                precio=request.precio,
                stock=request.stock_inicial,
                foto=request.foto
            )
            
            # Guardar en la base de datos
            db_session.add(nuevo_producto)
            db_session.commit()
            
            mensaje = f"Producto '{request.nombre}' ingresado con éxito."
            print(f"Servidor gRPC: {mensaje}")
            return producto_pb2.ProductoResponse(exito=True, mensaje=mensaje)

        except Exception as e:
            db_session.rollback()
            error_msg = f"Error interno del servidor: {str(e)}"
            print(f"Servidor gRPC: {error_msg}")
            return producto_pb2.ProductoResponse(exito=False, mensaje=error_msg)
        finally:
            db_session.close()

# Función para poner en marcha el servidor
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    producto_pb2_grpc.add_ProductoServiceServicer_to_server(ProductoService(), server)
    port = "50051"  # Puerto estándar para gRPC
    server.add_insecure_port(f"[::]:{port}")
    
    print(f"Servidor gRPC iniciado y escuchando en el puerto {port}...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
