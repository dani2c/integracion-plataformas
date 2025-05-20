import os
import json
import traceback
import requests
from datetime import datetime
from flask import Flask, jsonify, request, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from transbank.common.options import Options as BaseOptions
from transbank.common.integration_type import IntegrationType
from transbank.webpay.webpay_plus.transaction import Transaction

# ======================================================
# CONFIGURACIÓN INICIAL DE FLASK
# ======================================================
app = Flask(__name__)

# Ruta absoluta a la base de datos en la carpeta 'instance'
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'inventario_db.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ======================================================
# MODELOS DE BASE DE DATOS
# ======================================================
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
    respuesta = db.Column(db.Text)

# ======================================================
# CONFIGURACIÓN TRANSBANK (MOCK O REAL)
# ======================================================
class MockTransaction:
    def create(self, buy_order, session_id, amount, return_url):
        data = request.get_json()
        sucursal_id = data.get('sucursal_id')
        cantidad = int(data.get('cantidad', 0))

        unique_token = f"mock_token_{buy_order}"

        transaccion = Transaccion(
            buy_order=buy_order,
            amount=amount,
            status='INICIADA',
            respuesta=json.dumps({
                "token": unique_token,
                "url": url_for('mock_pago_exitoso', token=unique_token, _external=True),
                "sucursal_id": sucursal_id,
                "cantidad": cantidad
            }),
            fecha=datetime.now()
        )
        db.session.add(transaccion)
        db.session.commit()

        return type('obj', (object,), {
            'token': unique_token,
            'url': url_for('mock_pago_exitoso', token=unique_token, _external=True)
        })

    def commit(self, token):
        transaccion = Transaccion.query.filter(Transaccion.respuesta.like(f'%{token}%')).first()

        if not transaccion:
            raise Exception(f"Transacción no encontrada con token: {token}")

        respuesta = json.loads(transaccion.respuesta)
        sucursal_id = respuesta.get('sucursal_id')
        cantidad = int(respuesta.get('cantidad', 0))

        try:
            if sucursal_id == "casa_matriz":
                casa_matriz = CasaMatriz.query.first()
                if casa_matriz.cantidad < cantidad:
                    raise Exception("Stock insuficiente en Casa Matriz")
                casa_matriz.cantidad -= cantidad
            else:
                sucursal = Sucursal.query.get(int(sucursal_id))
                if not sucursal or sucursal.cantidad < cantidad:
                    raise Exception("Stock insuficiente o sucursal inexistente")
                sucursal.cantidad -= cantidad

            transaccion.status = 'AUTHORIZED'
            transaccion.respuesta = json.dumps({
                "status": "AUTHORIZED",
                "amount": transaccion.amount,
                "authorization_code": "123456",
                "sucursal_id": sucursal_id,
                "cantidad": cantidad,
                "token": token
            })
            db.session.commit()

            return type('obj', (object,), {
                'status': 'AUTHORIZED',
                'url': url_for('venta_exitosa', token=token, _external=True)
            })

        except Exception as e:
            transaccion.status = 'RECHAZADA'
            transaccion.respuesta = json.dumps({
                "error": str(e),
                "status": "RECHAZADA"
            })
            db.session.commit()
            return type('obj', (object,), {
                'status': 'FAILED',
                'url': url_for('venta_fallida', error=str(e), _external=True)
            })

if os.getenv('MOCK_TRANSBANK', 'true').lower() == 'true':
    webpay_transaction = MockTransaction()
else:
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

# ======================================================
# CONFIGURACIÓN ADICIONAL
# ======================================================
with app.app_context():
    db.create_all()

app.jinja_env.filters['fromjson'] = lambda s: json.loads(s)

# ======================================================
# RUTAS DE LA APLICACIÓN
# ======================================================
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
    try:
        data = request.json
        precio_clp = data.get('precio_clp', 0)

        access_key = '0a917c2f60f2356c47d823fde09463f0'
        url = f'http://api.currencylayer.com/live?access_key={access_key}&currencies=CLP&source=USD&format=1'

        response = requests.get(url)
        response.raise_for_status()
        data_api = response.json()

        if not data_api.get("success"):
            raise ValueError(data_api.get("error", {}).get("info", "Error desconocido"))

        tasa_clp = data_api["quotes"]["USDCLP"]
        tasa_usd = round(1 / tasa_clp, 6)
        precio_usd = round(precio_clp * tasa_usd, 2)

        return jsonify({
            "precio_usd": precio_usd,
            "tasa_actual": tasa_usd
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vender', methods=['POST'])
def vender():
    try:
        data = request.json
        sucursal_id = data.get('sucursal_id')
        cantidad = int(data.get('cantidad', 0))

        if sucursal_id == "casa_matriz":
            casa_matriz = CasaMatriz.query.first()
            if casa_matriz.cantidad < cantidad:
                return jsonify({"error": "Stock insuficiente en Casa Matriz"}), 400
            casa_matriz.cantidad -= cantidad
        else:
            sucursal = Sucursal.query.get(int(sucursal_id))
            if not sucursal or sucursal.cantidad < cantidad:
                return jsonify({"error": "Stock insuficiente o sucursal inexistente"}), 400
            sucursal.cantidad -= cantidad

        db.session.commit()
        return jsonify({"mensaje": "Venta realizada"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ======================================================
# RUTAS TRANSBANK
# ======================================================
@app.route('/mock-pago-exitoso')
def mock_pago_exitoso():
    token = request.args.get('token', 'mock_token_123')
    return f'''
    <html>
        <body style="padding: 20px; font-family: Arial;">
            <h2>Procesando Pago...</h2>
            <script>
                window.location.href = "/webpay/confirmar?token_ws={token}";
            </script>
        </body>
    </html>
    '''

@app.route('/webpay/iniciar', methods=['POST'])
def webpay_iniciar():
    try:
        data = request.json
        amount = float(data.get('total'))
        sucursal_id = data.get('sucursal_id')
        cantidad = int(data.get('cantidad', 0))

        buy_order = str(int(datetime.now().timestamp()))
        session_id = "sesion_" + buy_order
        return_url = url_for('webpay_confirmar', _external=True)

        response = webpay_transaction.create(
            buy_order=buy_order,
            session_id=session_id,
            amount=amount,
            return_url=return_url
        )

        return jsonify({"url": response.url, "token": response.token})

    except Exception as e:
        traceback.print_exc()
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
    if not transaccion:
        return redirect(url_for('venta_fallida', error="Transacción no encontrada"))
    respuesta = json.loads(transaccion.respuesta)
    return render_template('exito.html', transaccion=transaccion, respuesta=respuesta)

@app.route('/venta-fallida')
def venta_fallida():
    error = request.args.get('error', 'Error desconocido')
    return render_template('error.html', error=error)

# ======================================================
# INICIO DE LA APLICACIÓN
# ======================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
