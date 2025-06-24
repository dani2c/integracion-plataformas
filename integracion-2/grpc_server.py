import sys
import os
from concurrent import futures
import grpc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.append(PROJECT_ROOT)


GRPC_FILES_PATH = os.path.join(PROJECT_ROOT, 'grpc_files')
sys.path.append(GRPC_FILES_PATH)




from grpc_files import producto_pb2
from grpc_files import producto_pb2_grpc


from models import Producto


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'inventario_db.db')
engine = create_engine(f'sqlite:///{DATABASE_PATH}')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ProductoService(producto_pb2_grpc.ProductoServiceServicer):
    
    def IngresarProducto(self, request, context):
        print("Servidor gRPC: Recibida petición para ingresar producto...")
        db_session = SessionLocal()
        try:
            
            if not request.nombre or request.precio <= 0:
                mensaje = "Error: Nombre y precio válido son requeridos."
                print(f"Servidor gRPC: {mensaje}")
                return producto_pb2.ProductoResponse(exito=False, mensaje=mensaje)

            
            nuevo_producto = Producto(
                nombre=request.nombre,
                descripcion=request.descripcion,
                precio=request.precio,
                stock=request.stock_inicial,
                foto=request.foto
            )
            
            
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


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    producto_pb2_grpc.add_ProductoServiceServicer_to_server(ProductoService(), server)
    port = "50051"  
    server.add_insecure_port(f"[::]:{port}")
    
    print(f"Servidor gRPC iniciado y escuchando en el puerto {port}...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
