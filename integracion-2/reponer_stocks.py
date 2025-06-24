import os
from sqlalchemy import create_engine, text


NUEVO_STOCK_SUCURSAL = 999
NUEVO_STOCK_CASA_MATRIZ = 200

# --- Lógica del Script ---
print("Iniciando la reposición de stock...")

try:
    # Conectar a la base de datos
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'inventario_db.db')
    engine = create_engine(f'sqlite:///{db_path}')

    with engine.connect() as connection:
        # Iniciar una transacción
        trans = connection.begin()
        
        # Actualizar la tabla de sucursales
        print(f"Estableciendo stock de sucursales a {NUEVO_STOCK_SUCURSAL}...")
        connection.execute(text(f"UPDATE sucursal SET cantidad = {NUEVO_STOCK_SUCURSAL}"))

        # Actualizar la tabla de casa matriz
        print(f"Estableciendo stock de casa matriz a {NUEVO_STOCK_CASA_MATRIZ}...")
        connection.execute(text(f"UPDATE casa_matriz SET cantidad = {NUEVO_STOCK_CASA_MATRIZ}"))

        # Confirmar los cambios
        trans.commit()
        print("\n¡Stock repuesto con éxito!")

except Exception as e:
    print(f"\nOcurrió un error: {e}")

