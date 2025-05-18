import traceback
from flask import Flask, jsonify, request, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, JSON
from datetime import datetime
# Corrección de imports (versión 6.x)
from transbank.common.options import Options as BaseOptions
from transbank.common.integration_type import IntegrationType
from transbank.webpay.webpay_plus.transaction import Transaction
import os
from unittest.mock import Mock  
import sqlite3
import json


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///D:\\proyecto\\integracion\\inventario_db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

webpay_transaction = None

def configurar_transbank():
    global webpay_transaction
    
    if os.getenv('MOCK_TRANSBANK', 'false').lower() == 'true':
        # Mock
        class MockTransaction:
            def create(self, buy_order, session_id, amount, return_url):
                return type('obj', (object,), {
                    'token': 'mock_token_123',
                    'url': url_for('mock_pago_exitoso', _external=True)
                })
            
            def commit(self, token):
                return type('obj', (object,), {
                    'status': 'AUTHORIZED',
                    'buy_order': 'mock_order_123',
                    # ... (otros campos mock)
                })
        
        webpay_transaction = MockTransaction()
        print("\n--- MODO MOCK ACTIVADO ---\n")
    
    else:
        # Configuración real
        from transbank.common.options import Options as BaseOptions
        from transbank.common.integration_type import IntegrationType
        from transbank.webpay.webpay_plus.transaction import Transaction

        class WebpayOptions(BaseOptions):
            def header_api_key_name(self):
                return "Tbk-Api-Key-Secret"
            
            def header_commerce_code_name(self):
                return "Tbk-Api-Key-Id"

        webpay_options = WebpayOptions(
            commerce_code="597055555532",
            api_key="579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C",
            integration_type=IntegrationType.TEST
        )
        webpay_transaction = Transaction(webpay_options)
        print("\n--- MODO REAL g ACTIVADO ---\n")
        
configurar_transbank()


# Modelos de la base de datos (mantener igual)
class Sucursal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Integer, nullable=False)

class CasaMatriz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Integer, nullable=False)

class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buy_order = db.Column(db.String(40), unique=True)
    amount = db.Column(db.Float)
    status = db.Column(db.String(20))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    respuesta = db.Column(db.Text)  # Usar JSON de SQLAlchemy
    


# Crear tablas si no existen
with app.app_context():
    db.create_all()
    
@app.route('/mock-pago-exitoso')
def mock_pago_exitoso():
    return '''
    <html>
        <body style="padding: 20px; font-family: Arial;">
            <h2>Pago Simulado Exitoso</h2>
            <p>¡Transacción completada correctamente!</p>
            <p>Token: mock_token_123</p>
            <p><a href="/venta-exitosa?token=mock_token_123">Continuar</a></p>
        </body>
    </html>
    '''

# Rutas principales (mantener igual hasta webpay)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/inventario', methods=['GET'])
def get_inventario():
    sucursales = Sucursal.query.all()
    casa_matriz = CasaMatriz.query.first()
    return jsonify({
        "sucursales": [{
            "id": s.id,
            "nombre": s.nombre,
            "cantidad": s.cantidad,
            "precio": s.precio
        } for s in sucursales],
        "casa_matriz": {
            "cantidad": casa_matriz.cantidad,
            "precio": casa_matriz.precio
        } if casa_matriz else {"cantidad": 0, "precio": 0}
    })

@app.route('/api/transformar_usd', methods=['POST'])
def transformar_usd():
    data = request.json
    precio_clp = data.get('precio_clp', 0)
    tasa = 900
    precio_usd = round(precio_clp / tasa, 2)
    return jsonify({"precio_usd": precio_usd})

@app.route('/api/vender', methods=['POST'])
def vender():
    data = request.json
    sucursal_id = data.get('sucursal_id')
    cantidad = data.get('cantidad')

    try:
        if sucursal_id == "casa_matriz":
            casa_matriz = CasaMatriz.query.first()
            if casa_matriz.cantidad < cantidad:
                return jsonify({"error": "Stock insuficiente en Casa Matriz"}), 400
            casa_matriz.cantidad -= cantidad
        else:
            sucursal = Sucursal.query.get(sucursal_id)
            if not sucursal:
                return jsonify({"error": "Sucursal no encontrada"}), 404
            if sucursal.cantidad < cantidad:
                return jsonify({"error": "Stock insuficiente en sucursal"}), 400
            sucursal.cantidad -= cantidad
        
        db.session.commit()
        return jsonify({
            "mensaje": "Venta realizada",
            "stock_restante": casa_matriz.cantidad if sucursal_id == "casa_matriz" else sucursal.cantidad
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Nuevas rutas Webpay (actualizadas para SDK 6.x)
@app.route('/webpay/iniciar', methods=['POST'])
def webpay_iniciar():
    try:
        if not request.is_json:
            return jsonify({"error": "Solicitud debe ser JSON"}), 400

        data = request.get_json()
        amount = float(data.get('total', 0))

        if amount <= 0:
            return jsonify({"error": "Monto inválido"}), 400

        buy_order = str(int(datetime.now().timestamp()))
        session_id = f"sesion_{buy_order}"
        return_url = url_for('webpay_confirmar', _external=True, _scheme='http')

        # Solo debug en modo real
        if os.getenv('MOCK_TRANSBANK', 'false').lower() != 'true':
            print("\n--- Parámetros enviados a Transbank ---")
            print(f"Commerce Code: {webpay_options.commerce_code}")
            print(f"API Key: {webpay_options.api_key}")
            print(f"Amount: {amount}")
            print(f"Return URL: {return_url}\n")

        response = webpay_transaction.create(
            buy_order=buy_order,
            session_id=session_id,
            amount=amount,
            return_url=return_url
        )

        # Guardar en base de datos
        transaccion = Transaccion(
            buy_order=buy_order,
            amount=amount,
            status='INICIADA',
            respuesta=json.dumps({  # Serializa el diccionario
                "token": "mock_token_123",
                "url": url_for('mock_pago_exitoso', _external=True)
            }),
            fecha=datetime.now()
        )
        db.session.add(transaccion)
        db.session.commit()

        return jsonify({
            "url": response.url,
            "token": response.token
        })

    except Exception as e:
        print("\n--- Error detallado ---")
        print("Tipo:", type(e))
        print("Mensaje:", str(e))
        print("Traceback:", traceback.format_exc())
        return jsonify({"error": "Error al procesar la transacción"}), 500




@app.route('/webpay/confirmar', methods=['GET'])
def webpay_confirmar():
    token = request.args.get('token_ws')
    try:
        response = webpay_transaction.commit(token)
        
        transaccion = Transaccion.query.filter_by(buy_order=response.buy_order).first()
        if transaccion:
            transaccion.status = response.status
            transaccion.respuesta = {
                "vci": response.vci,
                "amount": response.amount,
                "status": response.status,
                "buy_order": response.buy_order,
                "session_id": response.session_id,
                "card_number": response.card_detail.card_number if response.card_detail else None,
                "authorization_code": response.authorization_code
            }
            db.session.commit()

        return redirect(url_for('venta_exitosa', token=token))

    except Exception as e:
        return redirect(url_for('venta_fallida', error=str(e)))

@app.route('/venta-exitosa')
def venta_exitosa():
    token = request.args.get('token')
    
    # Consulta usando JSON_EXTRACT de SQLite
    transacciones = Transaccion.query.all()
    for t in transacciones:
        respuesta = json.loads(t.respuesta)  # Deserializa
        if respuesta.get('token') == token:
            return render_template('exito.html', transaccion=t, respuesta=respuesta)
    
    return redirect(url_for('venta_fallida', error="Transacción no encontrada"))

@app.route('/venta-fallida')
def venta_fallida():
    error = request.args.get('error', 'Error desconocido')
    return render_template('error.html', error=error)

if __name__ == '__main__':
    app.run(debug=True)

class MockTransaction:
    def create(self, buy_order, session_id, amount, return_url):
        # Crear transacción con estructura realista
        transaccion = Transaccion(
            buy_order=buy_order,
            amount=amount,
            status='INICIADA',
            respuesta=json.dumps({
                "token": "mock_token_123",
                "url": url_for('mock_pago_exitoso', _external=True)
            }),
            fecha=datetime.now()
        )
        db.session.add(transaccion)
        db.session.commit()
        
        return type('obj', (object,), {
            'token': 'mock_token_123',
            'url': url_for('mock_pago_exitoso', _external=True)
        })
    
    def commit(self, token):
        # Actualizar transacción mock como exitosa
        transaccion = Transaccion.query.filter_by(respuesta={'token': 'mock_token_123'}).first()
        transaccion.status = 'AUTHORIZED'
        transaccion.respuesta = {
            "status": "AUTHORIZED",
            "amount": transaccion.amount,
            "authorization_code": "123456"
        }
        db.session.commit()
        
        return type('obj', (object,), {
            'status': 'AUTHORIZED',
            'amount': transaccion.amount,
            'authorization_code': '123456'
        })

# Selección automática del mock según variable de entorno
if os.getenv('MOCK_TRANSBANK', 'false').lower() == 'true':
    webpay_transaction = MockTransaction()
    print("\n--- MODO MOCK TRANSBANK ACTIVADO ---\n")
else:
    # Aquí iría la configuración real de Transbank (cuando la red funcione)
    from transbank.common.options import Options as BaseOptions
    from transbank.common.integration_type import IntegrationType
    from transbank.webpay.webpay_plus.transaction import Transaction

    class WebpayOptions(BaseOptions):
        def header_api_key_name(self):
            return "Tbk-Api-Key-Secret"
        def header_commerce_code_name(self):
            return "Tbk-Api-Key-Id"

    webpay_options = WebpayOptions(
        commerce_code="597055555532",
        api_key="579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C",
        integration_type=IntegrationType.TEST
    )
    webpay_transaction = Transaction(webpay_options)


