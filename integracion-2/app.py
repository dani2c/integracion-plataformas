import sys
import os
import json
import traceback
import queue
import grpc
import requests
from datetime import datetime


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.append(PROJECT_ROOT)
GRPC_FILES_PATH = os.path.join(PROJECT_ROOT, 'grpc_files')
sys.path.append(GRPC_FILES_PATH)


from flask import Flask, jsonify, request, render_template, url_for, redirect, Response, flash
from transbank.common.integration_type import IntegrationType
from transbank.common.options import Options as BaseOptions
from transbank.webpay.webpay_plus.transaction import Transaction

from models import db, Sucursal, CasaMatriz, Transaccion, Producto
from grpc_files import producto_pb2
from grpc_files import producto_pb2_grpc


app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'inventario_db.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'd47505ab14335c70e6e34498389441c9'

db.init_app(app)
notifications_queue = queue.Queue()


class MockTransaction:
    def create(self, buy_order, session_id, amount, return_url):
        data = request.get_json()
        sucursal_id, cantidad = data.get('sucursal_id'), int(data.get('cantidad', 0))
        unique_token = f"mock_token_{buy_order}"
        transaccion = Transaccion(
            buy_order=buy_order, amount=amount, status='INICIADA',
            respuesta=json.dumps({"token": unique_token, "url": url_for('mock_pago_exitoso', token=unique_token, _external=True), "sucursal_id": sucursal_id, "cantidad": cantidad}),
            fecha=datetime.now()
        )
        db.session.add(transaccion)
        db.session.commit()
        return type('obj', (object,), {'token': unique_token, 'url': url_for('mock_pago_exitoso', token=unique_token, _external=True)})

    def commit(self, token):
        transaccion = Transaccion.query.filter(Transaccion.respuesta.like(f'%{token}%')).first()
        if not transaccion: raise Exception(f"Transacción no encontrada: {token}")
        respuesta = json.loads(transaccion.respuesta)
        sucursal_id, cantidad = respuesta.get('sucursal_id'), int(respuesta.get('cantidad', 0))
        try:
            entidad = None
            if sucursal_id == "casa_matriz":
                entidad = CasaMatriz.query.first()
                if entidad.cantidad < cantidad: raise Exception("Stock insuficiente en Casa Matriz")
            else:
                entidad = Sucursal.query.get(int(sucursal_id))
                if not entidad or entidad.cantidad < cantidad: raise Exception("Stock insuficiente o sucursal inexistente")
            
            entidad.cantidad -= cantidad
            
            stock_afectado = {
                "id": f"sucursal_{entidad.id}" if sucursal_id != "casa_matriz" else "casa_matriz",
                "cantidad": entidad.cantidad,
                "nombre": entidad.nombre if sucursal_id != "casa_matriz" else "Casa Matriz"
            }
            
            transaccion.status = 'AUTHORIZED'
            transaccion.respuesta = json.dumps({"status": "AUTHORIZED", "amount": transaccion.amount, "authorization_code": "123456", "sucursal_id": sucursal_id, "cantidad": cantidad, "token": token})
            db.session.commit()
            

            if stock_afectado and stock_afectado['cantidad'] < 10:
                notifications_queue.put(stock_afectado)
                
            return type('obj', (object,), {'status': 'AUTHORIZED', 'url': url_for('venta_exitosa', token=token, _external=True)})
        except Exception as e:
            transaccion.status = 'RECHAZADA'
            transaccion.respuesta = json.dumps({"error": str(e), "status": "RECHAZADA"})
            db.session.commit()
            return type('obj', (object,), {'status': 'FAILED', 'url': url_for('venta_fallida', error=str(e), _external=True)})


if os.getenv('MOCK_TRANSBANK', 'true').lower() == 'true':
    webpay_transaction = MockTransaction()
else:
    pass
with app.app_context():
    db.create_all()
app.jinja_env.filters['fromjson'] = lambda s: json.loads(s)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ingresar-producto', methods=['GET', 'POST'])
def ingresar_producto():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            descripcion = request.form['descripcion']
            precio = float(request.form['precio'])
            stock_inicial = int(request.form['stock_inicial'])
            foto_file = request.files['foto']
            foto_bytes = foto_file.read()
            if not foto_bytes:
                flash('Error: Debes seleccionar un archivo de imagen.', 'danger')
                return redirect(request.url)
            with grpc.insecure_channel('localhost:50051') as channel:
                stub = producto_pb2_grpc.ProductoServiceStub(channel)
                peticion = producto_pb2.ProductoRequest(nombre=nombre, descripcion=descripcion, precio=precio, stock_inicial=stock_inicial, foto=foto_bytes)
                respuesta = stub.IngresarProducto(peticion)
                if respuesta.exito: flash(respuesta.mensaje, 'success')
                else: flash(f'Error desde gRPC: {respuesta.mensaje}', 'danger')
        except Exception as e:
            flash(f'Error en el cliente Flask: {str(e)}', 'danger')
        return redirect(url_for('ingresar_producto'))
    return render_template('ingresar_producto.html')

@app.route('/api/inventario', methods=['GET'])
def get_inventario():
    sucursales = Sucursal.query.all()
    casa_matriz = CasaMatriz.query.first()
    return jsonify({
        "sucursales": [{"id": s.id, "nombre": s.nombre, "cantidad": s.cantidad, "precio": s.precio} for s in sucursales],
        "casa_matriz": {"cantidad": casa_matriz.cantidad, "precio": casa_matriz.precio} if casa_matriz else {"cantidad": 0, "precio": 0}
    })

@app.route('/api/transformar_usd', methods=['POST'])
def transformar_usd():
    try:
        data = request.json
        precio_clp = data.get('precio_clp', 0)
        api_url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(api_url)
        response.raise_for_status()
        data_api = response.json()
        if data_api.get("result") == "success":
            valor_dolar = data_api.get("rates", {}).get("CLP")
            if valor_dolar is None: raise Exception("No se pudo obtener la tasa de cambio para CLP.")
            precio_usd = round(precio_clp / valor_dolar, 2)
            return jsonify({"precio_usd": precio_usd, "tasa_actual": valor_dolar})
        else:
            raise Exception("La API de conversión de moneda reportó un error.")
    except Exception as e:
        return jsonify({"error": str(e), "precio_usd": "Error"}), 500

@app.route('/api/stock-stream')
def stock_stream():
    def event_stream():
        while True:
            try:
                message = notifications_queue.get(timeout=25)
                yield f"data: {json.dumps(message)}\n\n"
            except queue.Empty:
                yield ": keep-alive\n\n"
    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/mock-pago-exitoso')
def mock_pago_exitoso():
    token = request.args.get('token', 'mock_token_123')
    return f'<html><body><h2>Procesando...</h2><script>window.location.href="/webpay/confirmar?token_ws={token}";</script></body></html>'

@app.route('/webpay/iniciar', methods=['POST'])
def webpay_iniciar():
    try:
        data = request.json
        amount = float(data.get('total'))
        buy_order = str(int(datetime.now().timestamp()))
        session_id = "sesion_" + buy_order
        return_url = url_for('webpay_confirmar', _external=True)
        response = webpay_transaction.create(buy_order=buy_order, session_id=session_id, amount=amount, return_url=return_url)
        return jsonify({"url": response.url, "token": response.token})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webpay/confirmar')
def webpay_confirmar():
    try:
        token = request.args.get('token_ws', 'mock_token_123')
        response = webpay_transaction.commit(token)
        return redirect(response.url)
    except Exception as e:
        return redirect(url_for('venta_fallida', error=str(e)))

@app.route('/venta-exitosa')
def venta_exitosa():
    token = request.args.get('token')
    transaccion = Transaccion.query.filter(Transaccion.respuesta.like(f'%{token}%')).first()
    if not transaccion: return redirect(url_for('venta_fallida', error="Transacción no encontrada"))
    respuesta = json.loads(transaccion.respuesta)
    return render_template('exito.html', transaccion=transaccion, respuesta=respuesta)

@app.route('/venta-fallida')
def venta_fallida():
    error = request.args.get('error', 'Error desconocido')
    return render_template('error.html', error=error)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

