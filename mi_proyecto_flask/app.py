from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

# Datos simulados de inventario
inventario = {
    "sucursales": [
        {"id": 1, "nombre": "Sucursal 1", "cantidad": 31, "precio": 333},
        {"id": 2, "nombre": "Sucursal 2", "cantidad": 23, "precio": 222},
        {"id": 3, "nombre": "Sucursal 3", "cantidad": 100, "precio": 1111}
    ],
    "casa_matriz": {"cantidad": 101, "precio": 999}
}

# Ruta principal - frontend
@app.route('/')
def index():
    return render_template('index.html')

# Endpoint para obtener inventario
@app.route('/api/inventario', methods=['GET'])
def get_inventario():
    return jsonify(inventario)

# Endpoint para transformar a USD (simulación, 1 USD = 900 CLP)
@app.route('/api/transformar_usd', methods=['POST'])
def transformar_usd():
    data = request.json
    precio_clp = data.get('precio_clp', 0)
    tasa = 900
    precio_usd = round(precio_clp / tasa, 2)
    return jsonify({"precio_usd": precio_usd})

# Endpoint para disminuir stock
@app.route('/api/vender', methods=['POST'])
def vender():
    data = request.json
    sucursal_id = data.get('sucursal_id')
    cantidad = data.get('cantidad')

    # Buscar sucursal
    sucursal = next((s for s in inventario['sucursales'] if s['id'] == sucursal_id), None)
    if not sucursal:
        return jsonify({"error": "Sucursal no encontrada"}), 404

    if sucursal['cantidad'] < cantidad:
        return jsonify({"error": "No hay suficiente stock"}), 400

    sucursal['cantidad'] -= cantidad
    return jsonify({"mensaje": "Venta realizada correctamente", "stock_restante": sucursal['cantidad']})

if __name__ == '__main__':
    app.run(debug=True)
